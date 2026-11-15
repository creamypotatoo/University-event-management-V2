from unittest.mock import MagicMock, patch
import pytest
import psycopg
from app import create_app, db
from app.routes import CLUBS_SQL


def test_factory(app):
    assert app.testing
    assert 'main.index' in app.view_functions


def test_home_without_database(app):
    with patch('app.db.psycopg.connect') as connect:
        response = app.test_client().get('/')
    assert response.status_code == 200
    assert b'University Event' in response.data
    connect.assert_not_called()


def test_environment(monkeypatch):
    monkeypatch.setenv('PGDATABASE', 'university_events_raw')
    monkeypatch.setenv('PGPORT', '5440')
    monkeypatch.setenv('PGPASSWORD', 'test-only')
    app = create_app()
    assert app.config['DB_PORT'] == 5440
    assert app.config['DB_PASSWORD'] == 'test-only'


def test_original_database_rejected():
    with pytest.raises(ValueError):
        create_app({'DB_NAME': 'university_events'})


def test_guard_before_connect(app):
    app.config['DB_NAME'] = 'university_events'
    with app.app_context(), patch('app.db.psycopg.connect') as connect:
        with pytest.raises(db.DatabaseUnavailable):
            db.check_connection()
    connect.assert_not_called()


def mock_connection():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = [{'database': 'university_events_raw', 'ok': 1}]
    return conn, cursor


def test_connection_and_commit(app):
    conn, cursor = mock_connection()
    with app.app_context(), patch('app.db.psycopg.connect', return_value=conn) as connect:
        assert db.check_connection()['ok'] == 1
    assert connect.call_args.kwargs['dbname'] == 'university_events_raw'
    assert connect.call_args.kwargs['autocommit'] is False
    assert conn.read_only is True
    assert 'default_transaction_read_only=on' in connect.call_args.kwargs['options']
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once()
    cursor.execute.assert_called_once_with('SELECT current_database() AS database, 1 AS ok', ())


def test_parameters_are_not_interpolated(app):
    conn, cursor = mock_connection()
    payload = "x'; DROP TABLE clubs; --"
    with app.app_context(), patch('app.db.psycopg.connect', return_value=conn):
        db.fetch_all('SELECT club_name FROM public.clubs WHERE club_name = %s', (payload,))
    cursor.execute.assert_called_once_with('SELECT club_name FROM public.clubs WHERE club_name = %s', (payload,))


def test_database_error_rolls_back(app):
    conn, cursor = mock_connection()
    cursor.execute.side_effect = psycopg.OperationalError('secret detail')
    with app.app_context(), patch('app.db.psycopg.connect', return_value=conn):
        with pytest.raises(db.DatabaseUnavailable, match='Database unavailable') as error:
            db.check_connection()
    assert 'secret detail' not in str(error.value)
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()


def test_python_error_also_rolls_back(app):
    conn, cursor = mock_connection()
    with app.app_context(), patch('app.db.psycopg.connect', return_value=conn):
        with pytest.raises(RuntimeError):
            with db.transaction():
                raise RuntimeError('stop')
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_connection_failure(app):
    with app.app_context(), patch('app.db.psycopg.connect', side_effect=psycopg.OperationalError('private')):
        with pytest.raises(db.DatabaseUnavailable):
            db.check_connection()


def test_clubs_read_only_and_escaped(app):
    with patch('app.routes.db.fetch_all', return_value=[{'club_id': 1, 'club_name': '<script>x</script>', 'description': 'Example', 'is_active': True}]) as fetch:
        response = app.test_client().get('/clubs?limit=7')
    assert response.status_code == 200
    assert b'&lt;script&gt;' in response.data
    fetch.assert_called_once_with(CLUBS_SQL, (7,))
    assert app.test_client().post('/clubs').status_code == 405


@pytest.mark.parametrize('limit', ['0', '101', 'abc', "1;DELETE FROM clubs"])
def test_invalid_limits(app, limit):
    with patch('app.routes.db.fetch_all') as fetch:
        assert app.test_client().get('/clubs', query_string={'limit': limit}).status_code == 400
    fetch.assert_not_called()


def test_empty_clubs(app):
    with patch('app.routes.db.fetch_all', return_value=[]):
        assert b'No clubs yet' in app.test_client().get('/clubs').data


def test_health_success(app):
    with patch('app.routes.db.check_connection', return_value={'ok': 1}):
        assert app.test_client().get('/health/db').json['status'] == 'ok'


def test_friendly_database_errors(app):
    with patch('app.routes.db.check_connection', side_effect=db.DatabaseUnavailable('private')):
        result = app.test_client().get('/health/db')
        assert result.status_code == 503
        assert result.json == {'status': 'unavailable'}
    with patch('app.routes.db.fetch_all', side_effect=db.DatabaseUnavailable('private')):
        result = app.test_client().get('/clubs')
        assert result.status_code == 503
        assert b'private' not in result.data
    assert app.test_client().get('/missing').status_code == 404


def test_cli_success_and_failure(app):
    with patch('app.db.check_connection', return_value={'database': 'university_events_raw'}):
        result = app.test_cli_runner().invoke(args=['db-check'])
        assert result.exit_code == 0
        assert 'read-only' in result.output
    with patch('app.db.check_connection', side_effect=db.DatabaseUnavailable('Unavailable')):
        result = app.test_cli_runner().invoke(args=['db-check'])
        assert result.exit_code == 1
