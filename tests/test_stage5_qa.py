from unittest.mock import patch
import pytest


def test_homepage_has_offline_assets_and_accessible_navigation(app):
    client=app.test_client()
    with patch('app.db.psycopg.connect') as connect:
        response=client.get('/')
    assert response.status_code==200
    assert b'cdn.jsdelivr.net' not in response.data
    assert b'Skip to content' in response.data and b'aria-label="Main navigation"' in response.data
    connect.assert_not_called()
    assert client.get('/static/vendor/bootstrap.min.css').status_code==200
    assert client.get('/static/favicon.svg').status_code==200
    assert "style-src 'self';" in response.headers['Content-Security-Policy']


def test_seed_default_is_plan_without_db_connection(app):
    with patch('app.db.psycopg.connect') as connect:
        result=app.test_cli_runner().invoke(args=['seed-demo'])
    assert result.exit_code==0 and '"persistent_changes": false' in result.output
    connect.assert_not_called()


def test_seed_requires_confirmation_and_consistent_options(app):
    with patch('app.db.psycopg.connect') as connect:
        denied=app.test_cli_runner().invoke(args=['seed-demo','--apply'],input='n\n')
        invalid=app.test_cli_runner().invoke(args=['seed-demo','--check','--apply'])
    assert denied.exit_code!=0 and invalid.exit_code!=0
    connect.assert_not_called()


def test_error_pages_have_recovery_and_no_technical_details(app):
    response=app.test_client().get('/no-such-page')
    assert response.status_code==404 and b'Return home' in response.data
    assert b'Traceback' not in response.data
