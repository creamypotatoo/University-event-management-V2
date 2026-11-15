from unittest.mock import MagicMock, patch
import time
import pytest
from werkzeug.security import generate_password_hash
from app import db, sql
from app.auth import User, safe_next, load_user
from app.validation import registration, valid_password, valid_email


def test_sql_loader_runtime_and_unknown_name():
    statements=sql.statements()
    assert {'auth.by_email','students.create','clubs.create','memberships.join','venues.edit'}<=set(statements)
    with pytest.raises(KeyError): sql.load('../../.env')
    conn=MagicMock()
    cur=conn.cursor.return_value.__enter__.return_value
    cur.description=[('user_id',)]
    cur.fetchone.return_value={'user_id':1}
    payload="x' OR 1=1 --"
    assert sql.execute(conn,'auth.by_email',(payload,),one=True)=={'user_id':1}
    cur.execute.assert_called_once_with(sql.load('auth.by_email'),(payload,))


@pytest.mark.parametrize('target',['https://evil.test','//evil.test','/\\evil.test','/%2fevil.test','/ path','/path\n','javascript:alert(1)'])
def test_unsafe_redirect_rejected(target):
    assert safe_next(target) is None


def test_safe_redirect_and_hash():
    assert safe_next('/clubs/1')=='/clubs/1'
    hashed=generate_password_hash('long test passphrase',method='scrypt')
    user=User(dict(user_id=1,full_name='Test',email='test@example.invalid',role='student',password_hash=hashed))
    assert hashed!='long test passphrase' and hashed.startswith('scrypt:')
    assert user.check_password('long test passphrase')
    assert not user.check_password('wrong')
    user.password_hash='broken hash'
    assert not user.check_password('anything')


@pytest.mark.parametrize('identifier',['-1','0','9999999999999999','abc','1;SELECT 1','?'])
def test_invalid_session_ids_do_not_query(identifier):
    with patch('app.auth.sql.read') as read:
        assert load_user(identifier) is None
    read.assert_not_called()


@pytest.mark.parametrize('password',['short',' '*20,'x'*129,'validbut\nnewline'])
def test_invalid_passwords(password):
    assert not valid_password(password)


@pytest.mark.parametrize('email',['not-an-email','..x@example.com','.x@example.com','x.@example.com','x@-bad.com','x@localhost'])
def test_invalid_email(email):
    assert not valid_email(email)


def test_registration_ignores_role_and_does_not_return_password():
    data,errors=registration(dict(full_name=' Student ',email='USER@EXAMPLE.COM',student_number='S001',department='CSE',batch='2026',password='long test passphrase',confirm_password='long test passphrase',role='system_admin'))
    assert not errors and data['email']=='user@example.com'
    assert 'role' not in data and 'password' not in data


def test_csrf_missing_wrong_expired_and_headers(app):
    client=app.test_client()
    assert client.get('/auth/register').status_code==200
    with client.session_transaction() as session:
        token=session['_csrf_token']
    assert client.post('/auth/register',data={}).status_code==400
    assert client.post('/auth/register',data={'csrf_token':'x'*64}).status_code==400
    with client.session_transaction() as session:
        session['_csrf_time']=time.time()-4000
    assert client.post('/auth/register',data={'csrf_token':token}).status_code==400
    response=client.get('/')
    assert response.headers['X-Frame-Options']=='DENY'
    assert response.headers['Cache-Control']=='no-store'
    assert 'HttpOnly' in response.headers.get('Set-Cookie','') or app.config['SESSION_COOKIE_HTTPONLY']
    assert app.config['SESSION_COOKIE_SAMESITE']=='Lax'


@pytest.mark.parametrize('path',['/profile','/profile/edit','/memberships','/students','/clubs/new','/venues/new','/dashboard','/dashboard/student','/dashboard/club-admin','/dashboard/system-admin','/clubs/1/edit','/clubs/1/members'])
def test_anonymous_protected_routes(app,path):
    response=app.test_client().get(path)
    assert response.status_code==302 and '/auth/login' in response.location


def test_write_transaction_commit_and_integrity_rollback(app):
    conn=MagicMock()
    with app.app_context(), patch('app.db.psycopg.connect',return_value=conn) as connect:
        with db.transaction(readonly=False): pass
    assert conn.read_only is False
    assert 'default_transaction_read_only=off' in connect.call_args.kwargs['options']
    conn.commit.assert_called_once()
    conn.close.assert_called_once()
    import psycopg
    conn.reset_mock()
    with app.app_context(), patch('app.db.psycopg.connect',return_value=conn):
        with pytest.raises(db.Conflict):
            with db.transaction(readonly=False): raise psycopg.errors.UniqueViolation('private')
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    conn.close.assert_called_once()


def test_authenticated_database_failure_is_friendly(app):
    client=app.test_client()
    client.get('/auth/login')
    with client.session_transaction() as session:
        token=session['_csrf_token']
    row=dict(user_id=1,full_name='Test',email='test@example.invalid',role='student',password_hash=generate_password_hash('long test passphrase',method='scrypt'))
    with patch('app.auth.sql.read',return_value=row):
        assert client.post('/auth/login',data={'email':'test@example.invalid','password':'long test passphrase','csrf_token':token}).status_code==302
    with patch('app.auth.sql.read',side_effect=db.DatabaseUnavailable('private')):
        response=client.get('/profile')
    assert response.status_code==503
    assert b'private' not in response.data
