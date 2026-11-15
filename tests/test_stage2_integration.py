"""Actual Stage 2 SQL + Flask requests; each test rolls back an outer transaction.

The test adapter gives each application transaction a PostgreSQL savepoint.
Production commit/rollback is separately covered by transaction tests. SERIAL
sequences can advance; they are never reset. No existing records are erased.
"""
from contextlib import contextmanager
import os
import re
import uuid
import psycopg
from psycopg.rows import dict_row
import pytest
from werkzeug.security import generate_password_hash,check_password_hash
from app import db, sql

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_RAW_SQL_INTEGRATION')!='1',reason='Explicit database integration opt-in required.')]
PASSWORD='integration test passphrase'


@pytest.fixture
def pg(app,monkeypatch):
    c=app.config
    assert c['DB_NAME']=='university_events_raw'
    conn=psycopg.connect(dbname=c['DB_NAME'],host=c['DB_HOST'],port=c['DB_PORT'],user=c['DB_USER'],password=c['DB_PASSWORD'],connect_timeout=5,row_factory=dict_row,options='-c search_path=public -c statement_timeout=5000')
    conn.execute('SELECT 1')
    @contextmanager
    def isolated(*,readonly=True):
        assert app.config['DB_NAME']=='university_events_raw'
        try:
            with conn.transaction(): yield conn
        except psycopg.IntegrityError:
            raise db.Conflict('Those details conflict with an existing record.') from None
    monkeypatch.setattr(db,'transaction',isolated)
    try:
        yield app,conn,uuid.uuid4().hex[:12]
    finally:
        conn.rollback()
        conn.close()


def token(client,path='/auth/login'):
    response=client.get(path)
    assert response.status_code in (200,302)
    with client.session_transaction() as session:
        if '_csrf_token' in session: return session['_csrf_token']
    response=client.get('/')
    match=re.search(rb'name="csrf_token" value="([a-f0-9]+)"',response.data)
    assert match
    return match.group(1).decode()


def post(client,path,data=None):
    return client.post(path,data=dict(data or {},csrf_token=token(client)))


def account(conn,tag,role='student'):
    user=sql.execute(conn,'auth.create_admin_user',(f'Test {tag}',f'{tag}@example.invalid',generate_password_hash(PASSWORD,method='scrypt'),role),one=True)
    sid=None
    if role=='student': sid=sql.execute(conn,'students.create',(user['user_id'],f'S{tag}','CSE','2026'),one=True)['student_id']
    return user['user_id'],sid


def login(client,tag):
    response=post(client,'/auth/login',{'email':f'{tag}@example.invalid','password':PASSWORD})
    assert response.status_code==302


def club(conn,tag,active=True):
    cid=sql.execute(conn,'clubs.create',(f'Club {tag}','Test description'),one=True)['club_id']
    if not active: sql.execute(conn,'clubs.status',(False,cid),one=True)
    return cid


def register_data(tag):
    return dict(full_name='New Student',email=f'{tag}@example.invalid',student_number=f'R{tag}',department='CSE',batch='2026',password=PASSWORD,confirm_password=PASSWORD)


def test_registration_login_logout_profile_and_role_escalation(pg):
    app,conn,tag=pg
    client=app.test_client()
    result=post(client,'/auth/register',dict(register_data(tag),role='system_admin',user_id='1'))
    assert result.status_code==302
    row=sql.execute(conn,'auth.by_email',(f'{tag}@example.invalid',),one=True)
    assert row['role']=='student' and row['password_hash'].startswith('scrypt:')
    assert check_password_hash(row['password_hash'],PASSWORD)
    profile=sql.execute(conn,'students.by_user',(row['user_id'],),one=True)
    assert profile['student_number']==f'R{tag}'
    assert post(client,'/auth/login',{'email':f'{tag}@example.invalid','password':'wrong'}).status_code==401
    login(client,tag)
    assert client.get('/dashboard',follow_redirects=True).status_code==200
    assert client.get('/profile').status_code==200
    result=post(client,'/profile/edit',dict(full_name='Changed Student',department='EEE',batch='2027',role='system_admin',student_number='HACK',email='hack@example.invalid',user_id=1))
    assert result.status_code==302
    profile=sql.execute(conn,'students.by_user',(row['user_id'],),one=True)
    assert profile['full_name']=='Changed Student' and profile['department']=='EEE'
    assert profile['student_number']==f'R{tag}' and profile['email']==f'{tag}@example.invalid'
    assert client.get('/venues/new').status_code==403
    assert client.get('/clubs/new').status_code==403
    assert client.get('/students').status_code==403
    assert client.get('/dashboard/system-admin').status_code==403
    assert client.get('/auth/logout').status_code==405
    assert post(client,'/auth/logout').status_code==302
    assert client.get('/profile').status_code==302


@pytest.mark.parametrize('duplicate',['email','student_number'])
def test_duplicate_registration_atomicity(pg,duplicate):
    app,conn,tag=pg
    client=app.test_client()
    assert post(client,'/auth/register',register_data(tag)).status_code==302
    other=register_data(tag+'b')
    other[duplicate]=register_data(tag)[duplicate]
    assert post(client,'/auth/register',other).status_code==400
    if duplicate=='student_number':
        assert sql.execute(conn,'auth.by_email',(other['email'],),one=True) is None
    assert conn.execute('SELECT count(*) AS n FROM public.students WHERE student_number=%s',(f'R{tag}',)).fetchone()['n']==1


def test_cross_student_ownership_and_invalid_input(pg):
    app,conn,tag=pg
    uid,sid=account(conn,tag)
    _,other_sid=account(conn,tag+'b')
    client=app.test_client();login(client,tag)
    assert client.get(f'/students/{sid}').status_code==200
    assert client.get(f'/students/{other_sid}').status_code==403
    assert post(client,'/profile/edit',{'full_name':'','department':'x','batch':'x'}).status_code==400
    assert sql.execute(conn,'students.by_user',(uid,),one=True)['full_name']==f'Test {tag}'


def test_admin_club_venue_creation_edit_and_duplicate_names(pg):
    app,conn,tag=pg
    account(conn,tag,'system_admin')
    client=app.test_client();login(client,tag)
    assert client.get('/dashboard',follow_redirects=True).status_code==200
    assert client.get('/students').status_code==200
    result=post(client,'/clubs/new',{'club_name':f'Club {tag}','description':'Description'})
    assert result.status_code==302
    cid=int(result.location.rsplit('/',1)[1])
    assert post(client,'/clubs/new',{'club_name':f'Club {tag}','description':'Again'}).status_code==400
    assert post(client,f'/clubs/{cid}/edit',{'club_name':f'Edited {tag}','description':'Updated','is_active':'false'}).status_code==302
    assert sql.execute(conn,'clubs.detail',(cid,),one=True)['is_active'] is True
    assert post(client,f'/clubs/{cid}/status',{'status':'inactive'}).status_code==302
    assert not sql.execute(conn,'clubs.detail',(cid,),one=True)['is_active']
    assert post(client,f'/clubs/{cid}/status',{'status':'active'}).status_code==302
    assert post(client,'/venues/new',{'venue_name':f'Venue {tag}','location':'North','capacity':'100'}).status_code==302
    vid=conn.execute('SELECT venue_id FROM public.venues WHERE venue_name=%s',(f'Venue {tag}',)).fetchone()['venue_id']
    assert post(client,f'/venues/{vid}/edit',{'venue_name':f'Edited {tag}','location':'South','capacity':'200'}).status_code==302
    assert sql.execute(conn,'venues.detail',(vid,),one=True)['capacity']==200
    assert post(client,'/venues/new',{'venue_name':f'Edited {tag}','location':'Elsewhere','capacity':'1'}).status_code==400
    assert client.get('/venues').status_code==200


@pytest.mark.parametrize('capacity',['0','-1','1.5','2147483648','abc',"1;DROP TABLE venues"])
def test_venue_capacity_validation(pg,capacity):
    app,conn,tag=pg
    account(conn,tag,'system_admin')
    client=app.test_client();login(client,tag)
    assert post(client,'/venues/new',{'venue_name':f'Venue {tag}','location':'North','capacity':capacity}).status_code==400
    assert conn.execute('SELECT count(*) AS n FROM public.venues WHERE venue_name=%s',(f'Venue {tag}',)).fetchone()['n']==0


def test_membership_rejoin_preserves_lifetime_row_and_timestamp(pg):
    app,conn,tag=pg
    _,sid=account(conn,tag)
    cid=club(conn,tag)
    client=app.test_client();login(client,tag)
    assert post(client,f'/clubs/{cid}/leave').status_code==302
    assert sql.execute(conn,'memberships.mine_one',(cid,sid),one=True) is None
    assert post(client,f'/clubs/{cid}/join').status_code==302
    initial=sql.execute(conn,'memberships.mine_one',(cid,sid),one=True)
    assert post(client,f'/clubs/{cid}/join').status_code==302
    assert post(client,f'/clubs/{cid}/leave').status_code==302
    assert post(client,f'/clubs/{cid}/join').status_code==302
    final=sql.execute(conn,'memberships.mine_one',(cid,sid),one=True)
    assert final==initial
    assert client.get('/memberships').status_code==200
    assert client.get(f'/clubs/{cid}').status_code==200


def test_inactive_club_blocks_join_but_allows_leave(pg):
    app,conn,tag=pg
    _,sid=account(conn,tag)
    cid=club(conn,tag)
    client=app.test_client();login(client,tag)
    assert post(client,f'/clubs/{cid}/join').status_code==302
    sql.execute(conn,'clubs.status',(False,cid),one=True)
    assert post(client,f'/clubs/{cid}/join').status_code==409
    assert post(client,f'/clubs/{cid}/leave').status_code==302
    assert sql.execute(conn,'memberships.mine_one',(cid,sid),one=True)['status']=='cancelled'


def test_assignments_scope_membership_admin_and_removal(pg):
    app,conn,tag=pg
    account(conn,tag,'system_admin')
    admin_id,_=account(conn,tag+'a','club_admin')
    _,sid=account(conn,tag+'s')
    cid=club(conn,tag)
    other=club(conn,tag+'other')
    mid=sql.execute(conn,'memberships.join',(cid,sid),one=True)['membership_id']
    admin=app.test_client();login(admin,tag)
    scoped=app.test_client();login(scoped,tag+'a')
    assert scoped.get(f'/clubs/{cid}/edit').status_code==403
    assert post(admin,f'/clubs/{cid}/admins',{'email':f'{tag}a@example.invalid'}).status_code==302
    assert post(admin,f'/clubs/{cid}/admins',{'email':f'{tag}a@example.invalid'}).status_code==302
    assert scoped.get('/dashboard',follow_redirects=True).status_code==200
    assert scoped.get(f'/clubs/{cid}/edit').status_code==200
    assert scoped.get(f'/clubs/{other}/edit').status_code==403
    assert scoped.get('/venues/new').status_code==403
    assert post(scoped,f'/clubs/{cid}/status',{'status':'inactive'}).status_code==403
    assert post(scoped,f'/clubs/{cid}/admins',{'email':f'{tag}s@example.invalid'}).status_code==403
    assert post(admin,f'/clubs/{cid}/admins',{'email':f'{tag}s@example.invalid'}).status_code==400
    assert post(scoped,f'/clubs/{cid}/edit',{'club_name':f'Edited {tag}','description':'Scoped edit'}).status_code==302
    assert scoped.get(f'/clubs/{cid}/members').status_code==200
    assert post(scoped,f'/clubs/{cid}/members/{mid}/status',{'status':'cancelled'}).status_code==302
    assert post(scoped,f'/clubs/{other}/members/{mid}/status',{'status':'active'}).status_code==403
    assert post(admin,f'/clubs/{cid}/status',{'status':'inactive'}).status_code==302
    assert post(scoped,f'/clubs/{cid}/members/{mid}/status',{'status':'active'}).status_code==409
    assert post(admin,f'/clubs/{cid}/status',{'status':'active'}).status_code==302
    assert post(scoped,f'/clubs/{cid}/members/{mid}/status',{'status':'active'}).status_code==302
    assert post(admin,f'/clubs/{cid}/admins/{admin_id}/remove').status_code==302
    assert scoped.get(f'/clubs/{cid}/edit').status_code==403


def test_sql_injection_and_html_escaping(pg):
    app,conn,tag=pg
    client=app.test_client()
    assert post(client,'/auth/login',{'email':"x' OR 1=1 --",'password':PASSWORD}).status_code==401
    assert client.get('/profile').status_code==302
    assert client.get('/clubs',query_string={'q':"x'; DROP TABLE clubs; --"}).status_code==200
    account(conn,tag,'system_admin');login(client,tag)
    name=f"<script>x</script> {tag}'"
    result=post(client,'/clubs/new',{'club_name':name,'description':"x'); DROP TABLE clubs; --"})
    assert result.status_code==302
    detail=client.get(result.location)
    assert b'&lt;script&gt;' in detail.data and b'<script>x</script>' not in detail.data
    assert conn.execute('SELECT count(*) AS n FROM public.clubs WHERE club_name=%s',(name,)).fetchone()['n']==1


def test_safe_login_redirect_and_csrf_session_rotation(pg):
    app,conn,tag=pg
    account(conn,tag)
    client=app.test_client()
    old=token(client)
    response=client.post('/auth/login',data={'email':f'{tag}@example.invalid','password':PASSWORD,'csrf_token':old,'next':'//evil.example'})
    assert response.status_code==302 and response.location=='/dashboard'
    assert client.post('/auth/logout',data={'csrf_token':old}).status_code==400
    assert post(client,'/auth/logout').status_code==302


def test_club_admin_cli_uses_hidden_password_and_atomic_unique_email(pg):
    app,conn,tag=pg
    details=f'CLI Admin\n{tag}@example.invalid\n{PASSWORD}\n{PASSWORD}\n'
    result=app.test_cli_runner().invoke(args=['create-club-admin'],input=details)
    assert result.exit_code==0
    assert PASSWORD not in result.output
    assert sql.execute(conn,'auth.by_email',(f'{tag}@example.invalid',),one=True)['role']=='club_admin'
    result=app.test_cli_runner().invoke(args=['create-club-admin'],input=details)
    assert result.exit_code!=0 and PASSWORD not in result.output


def test_venue_capacity_guard_existing_event(pg):
    app,conn,tag=pg
    account(conn,tag,'system_admin')
    cid=club(conn,tag)
    vid=sql.execute(conn,'venues.create',(f'Venue {tag}','North',100),one=True)['venue_id']
    conn.execute("INSERT INTO public.events (club_id,venue_id,title,description,start_time,end_time,capacity) VALUES (%s,%s,'Fixture','Test','2040-01-01T10:00Z','2040-01-01T11:00Z',80)",(cid,vid))
    client=app.test_client();login(client,tag)
    assert post(client,f'/venues/{vid}/edit',{'venue_name':f'Venue {tag}','location':'North','capacity':'79'}).status_code==409
    assert sql.execute(conn,'venues.detail',(vid,),one=True)['capacity']==100


def test_initial_system_admin_cli_refuses_second_bootstrap(pg):
    app,conn,tag=pg
    details=f'CLI System Admin\n{tag}@example.invalid\n{PASSWORD}\n{PASSWORD}\n'
    existing=sql.execute(conn,'auth.existing_admin',one=True)
    result=app.test_cli_runner().invoke(args=['create-admin'],input=details)
    assert PASSWORD not in result.output
    if existing:
        assert result.exit_code!=0
        assert sql.execute(conn,'auth.by_email',(f'{tag}@example.invalid',),one=True) is None
    else:
        assert result.exit_code==0
        assert sql.execute(conn,'auth.by_email',(f'{tag}@example.invalid',),one=True)['role']=='system_admin'
        second=app.test_cli_runner().invoke(args=['create-admin'],input=details)
        assert second.exit_code!=0 and 'already exists' in second.output


def test_membership_object_must_belong_to_scoped_club(pg):
    app,conn,tag=pg
    uid,_=account(conn,tag,'club_admin')
    _,sid=account(conn,tag+'s')
    cid=club(conn,tag)
    other=club(conn,tag+'other')
    sql.execute(conn,'clubs.assign',(cid,uid))
    mid=sql.execute(conn,'memberships.join',(other,sid),one=True)['membership_id']
    client=app.test_client();login(client,tag)
    assert post(client,f'/clubs/{cid}/members/{mid}/status',{'status':'cancelled'}).status_code==404
    assert sql.execute(conn,'memberships.mine_one',(other,sid),one=True)['status']=='active'
