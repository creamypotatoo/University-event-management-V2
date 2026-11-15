"""Stage 4 local HTTP workflow verification with rollback-only fixtures.

Run: python -m scripts.verify_stage4_http
Uses only university_events_raw. Does not commit fixture rows or change schema.
SERIAL counters may advance and are deliberately never reset.
"""
from contextlib import contextmanager
import csv
from io import StringIO
from datetime import datetime,timedelta,timezone
from urllib.error import HTTPError
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import secrets
import threading
import uuid
import urllib.parse
import urllib.request

import psycopg
from psycopg import sql as pgsql
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash
from werkzeug.serving import make_server,WSGIRequestHandler
from app import create_app, db, sql, event_services as service

class QuietHandler(WSGIRequestHandler):
    def log_request(self,*args,**kwargs):
        pass


def run(output_name='STAGE4_HTTP_VALIDATION.json'):
    app=create_app()
    c=app.config
    assert c['DB_NAME']=='university_events_raw'
    conn=psycopg.connect(dbname=c['DB_NAME'],host=c['DB_HOST'],port=c['DB_PORT'],user=c['DB_USER'],password=c['DB_PASSWORD'],connect_timeout=5,row_factory=dict_row,options='-c search_path=public -c statement_timeout=5000')
    tables=['users','students','clubs','club_memberships','club_admins','venues','events','registrations','event_expenses']
    def counts():
        return {name:conn.execute(pgsql.SQL('SELECT count(*) AS n FROM public.{}').format(pgsql.Identifier(name))).fetchone()['n'] for name in tables}
    before=counts()
    original=db.transaction
    original_clock=service.now_utc
    @contextmanager
    def isolated(*,readonly=True):
        try:
            with conn.transaction(): yield conn
        except psycopg.IntegrityError:
            raise db.Conflict('Fixture operation violated a database rule.') from None
    db.transaction=isolated
    server=None
    thread=None
    evidence={'database':'university_events_raw','isolation':'outer PostgreSQL transaction, per-operation savepoints, final rollback','checks':[]}
    try:
        tag=uuid.uuid4().hex[:12]
        password=secrets.token_urlsafe(24)
        for suffix,role in [('admin','system_admin'),('scoped','club_admin')]:
            sql.execute(conn,'auth.create_admin_user',(f'HTTP {suffix}',f'{tag}{suffix}@example.invalid',generate_password_hash(password,method='scrypt'),role),one=True)
        server=make_server('127.0.0.1',0,app,request_handler=QuietHandler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def browser():
            return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        def get(client,path):
            with client.open(base+path,timeout=10) as response:
                assert response.status==200
                return response.read().decode('utf-8'),response.url
        def post(client,path,data,page='/auth/login'):
            body,_=get(client,page)
            token=re.search(r'name="csrf_token" value="([a-f0-9]{64})"',body).group(1)
            payload=urllib.parse.urlencode(dict(data,csrf_token=token)).encode()
            with client.open(base+path,payload,timeout=10) as response:
                assert response.status==200
                return response.read().decode('utf-8'),response.url
        def passed(name):
            evidence['checks'].append({'workflow':name,'result':'passed'})
            print(name+': passed')
        anon=browser()
        get(anon,'/');get(anon,'/clubs');get(anon,'/venues')
        body,_=get(anon,'/health/db');assert json.loads(body)['status']=='ok'
        passed('Homepage, clubs, venues and database health over HTTP')
        admin=browser()
        body,_=post(admin,'/auth/login',{'email':f'{tag}admin@example.invalid','password':password})
        assert 'System administrator dashboard' in body
        body,url=post(admin,'/clubs/new',{'club_name':f'HTTP {tag}','description':'HTTP workflow fixture'},page='/clubs/new')
        cid=int(url.rsplit('/',1)[1])
        body,_=post(admin,f'/clubs/{cid}/edit',{'club_name':f'HTTP edited {tag}','description':'Updated over HTTP'},page=f'/clubs/{cid}/edit')
        assert f'HTTP edited {tag}' in body
        post(admin,'/venues/new',{'venue_name':f'HTTP venue {tag}','location':'Campus','capacity':'125'},page='/venues/new')
        vid=conn.execute('SELECT venue_id FROM public.venues WHERE venue_name=%s',(f'HTTP venue {tag}',)).fetchone()['venue_id']
        body,_=post(admin,f'/venues/{vid}/edit',{'venue_name':f'HTTP venue {tag}','location':'Main campus','capacity':'150'},page=f'/venues/{vid}/edit')
        assert 'Main campus' in body
        passed('Administrator login, dashboard, club create/edit and venue create/edit')
        student=browser()
        post(student,'/auth/register',{'full_name':'HTTP Student','email':f'{tag}student@example.invalid','student_number':f'H{tag}','department':'CSE','batch':'2026','password':password,'confirm_password':password},page='/auth/register')
        body,_=post(student,'/auth/login',{'email':f'{tag}student@example.invalid','password':password})
        assert 'Student dashboard' in body
        body,_=post(student,'/profile/edit',{'full_name':'HTTP Updated Student','department':'EEE','batch':'2027'},page='/profile/edit')
        assert 'HTTP Updated Student' in body
        post(student,f'/clubs/{cid}/join',{},page=f'/clubs/{cid}')
        body,_=get(student,'/memberships');assert 'active' in body
        post(student,f'/clubs/{cid}/leave',{},page=f'/clubs/{cid}')
        post(student,f'/clubs/{cid}/join',{},page=f'/clubs/{cid}')
        passed('Student register/login, dashboard, profile edit, join/leave/rejoin and memberships')
        post(admin,f'/clubs/{cid}/admins',{'email':f'{tag}scoped@example.invalid'},page=f'/clubs/{cid}')
        scoped=browser()
        body,_=post(scoped,'/auth/login',{'email':f'{tag}scoped@example.invalid','password':password})
        assert 'Club administrator dashboard' in body
        body,_=get(scoped,f'/clubs/{cid}/members');assert 'HTTP Updated Student' in body
        mid=conn.execute('SELECT membership_id FROM public.club_memberships WHERE club_id=%s',(cid,)).fetchone()['membership_id']
        post(scoped,f'/clubs/{cid}/members/{mid}/status',{'status':'cancelled'},page=f'/clubs/{cid}/members')
        post(admin,f'/clubs/{cid}/status',{'status':'inactive'},page=f'/clubs/{cid}')
        body,_=get(student,f'/clubs/{cid}');assert 'This club is inactive' in body
        post(admin,f'/clubs/{cid}/status',{'status':'active'},page=f'/clubs/{cid}')
        passed('Club assignment, scoped dashboard/member administration and club activation')
        future=datetime.now(timezone.utc)+timedelta(days=3)
        event_values=dict(title=f'HTTP Event {tag}',description='HTTP event fixture',venue_id=str(vid),capacity='1',start_time=future.isoformat(),end_time=(future+timedelta(hours=1)).isoformat())
        body,url=post(admin,f'/clubs/{cid}/events/new',event_values,page=f'/clubs/{cid}/events/new')
        eid=int(url.rsplit('/',1)[1])
        event_values['title']=f'HTTP Updated Event {tag}'
        body,_=post(admin,f'/events/{eid}/edit',event_values,page=f'/events/{eid}/edit')
        assert event_values['title'] in body
        body,_=get(anon,'/events?'+urllib.parse.urlencode({'club_id':cid,'status':'scheduled','when':'upcoming'}))
        assert event_values['title'] in body
        body,_=get(anon,f'/venues/{vid}/availability?'+urllib.parse.urlencode({'start_time':future.isoformat(),'end_time':(future+timedelta(hours=1)).isoformat()}))
        assert 'already booked' in body
        passed('Event create/edit, public detail/filter pages and venue conflict feedback')
        post(student,f'/events/{eid}/register',{},page=f'/events/{eid}')
        first=conn.execute('SELECT registration_id,registered_at FROM public.registrations WHERE event_id=%s',(eid,)).fetchone()
        post(student,f'/events/{eid}/registration/cancel',{},page=f'/events/{eid}')
        post(student,f'/events/{eid}/register',{},page=f'/events/{eid}')
        final=conn.execute('SELECT registration_id,registered_at FROM public.registrations WHERE event_id=%s',(eid,)).fetchone()
        assert first==final
        body,_=get(student,'/registrations');assert event_values['title'] in body
        passed('HTTP registration, cancellation, reactivation and lifetime row/timestamp preservation')
        # Advance only the application service clock for rollback-only attendance fixtures.
        service.now_utc=lambda:future+timedelta(minutes=5)
        body,_=post(scoped,f'/events/{eid}/participants/{first["registration_id"]}/status',{'status':'attended'},page=f'/events/{eid}/participants')
        assert 'attended' in body
        body,_=get(student,'/registrations?status=attended');assert event_values['title'] in body
        body,_=post(scoped,f'/events/{eid}/participants/{first["registration_id"]}/status',{'status':'registered'},page=f'/events/{eid}/participants')
        assert 'registered' in body
        service.now_utc=lambda:future+timedelta(hours=2)
        post(admin,f'/events/{eid}/status',{'status':'completed'},page=f'/events/{eid}')
        passed('Scoped HTTP attendance/correction, student history and event completion (fixture clock advanced)')
        later=dict(event_values,title=f'HTTP Cancel Event {tag}',start_time=(future+timedelta(days=1)).isoformat(),end_time=(future+timedelta(days=1,hours=1)).isoformat())
        body,url=post(scoped,f'/clubs/{cid}/events/new',later,page=f'/clubs/{cid}/events/new')
        later_id=int(url.rsplit('/',1)[1])
        body,_=post(scoped,f'/events/{later_id}/status',{'status':'cancelled'},page=f'/events/{later_id}')
        assert 'cancelled' in body
        passed('Scoped HTTP event cancellation preserving history')
        expense_date=datetime.now(timezone.utc).date().isoformat()
        first_values={'description':'HTTP room cost','amount':'100.10','expense_date':expense_date}
        body,_=post(admin,f'/events/{eid}/expenses/new',first_values,page=f'/events/{eid}/expenses/new')
        assert '100.10' in body
        xid=conn.execute('SELECT expense_id FROM public.event_expenses WHERE event_id=%s AND description=%s',(eid,first_values['description'])).fetchone()['expense_id']
        post(scoped,f'/events/{eid}/expenses/new',dict(first_values,description='HTTP supplies',amount='20.20'),page=f'/events/{eid}/expenses/new')
        body,_=post(admin,f'/events/{eid}/expenses/{xid}/edit',dict(first_values,amount='150.10'),page=f'/events/{eid}/expenses/{xid}/edit')
        assert '170.30' in body
        for path in ['/reports','/reports/financial','/reports/analytics',f'/clubs/{cid}/financial']:
            get(scoped,path)
        body,_=get(scoped,'/reports/financial?'+urllib.parse.urlencode({'event_id':eid,'from_date':expense_date,'to_date':expense_date}))
        assert '170.30' in body
        text,_=get(scoped,'/reports/financial.csv?'+urllib.parse.urlencode({'event_id':eid}))
        finance_rows=list(csv.DictReader(StringIO(text)))
        assert len(finance_rows)==1 and finance_rows[0]['total_expenses_bdt']=='170.30'
        text,_=get(scoped,'/reports/participation.csv?'+urllib.parse.urlencode({'event_id':eid}))
        participation_rows=list(csv.DictReader(StringIO(text)))
        assert len(participation_rows)==1 and participation_rows[0]['occupied']=='1'
        assert not {'email','student_id','full_name'}&set(participation_rows[0])
        passed('Scoped HTTP expense create/edit, exact financial totals, participation reports and CSV downloads')
        try:
            get(student,'/reports/financial.csv')
            raise AssertionError('Student unexpectedly accessed financial export')
        except HTTPError as error:
            assert error.code==403
        body,_=get(admin,f'/events/{eid}/expenses/{xid}/delete')
        assert 'Confirm deletion' in body
        assert conn.execute('SELECT expense_id FROM public.event_expenses WHERE expense_id=%s',(xid,)).fetchone()
        body,_=post(admin,f'/events/{eid}/expenses/{xid}/delete',{'confirm':'delete'},page=f'/events/{eid}/expenses/{xid}/delete')
        assert '20.20' in body and not conn.execute('SELECT expense_id FROM public.event_expenses WHERE expense_id=%s',(xid,)).fetchone()
        passed('HTTP expense delete confirmation/POST and student export denial')
        body,_=post(student,'/auth/logout',{},page='/profile');assert 'Log in' in body
        passed('POST logout with CSRF')
    finally:
        if server:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()
        db.transaction=original
        service.now_utc=original_clock
        conn.rollback()
        after=counts()
        conn.rollback()
        conn.close()
    assert before==after, 'Database row counts changed unexpectedly'
    evidence['row_counts_before']=before
    evidence['row_counts_after']=after
    evidence['temporary_server_stopped']=True
    (Path(__file__).resolve().parents[1]/output_name).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    print('Server stopped; all HTTP fixtures rolled back; row counts unchanged.')


if __name__=='__main__':
    run()
