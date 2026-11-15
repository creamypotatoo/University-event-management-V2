"""Independent PostgreSQL connections, real commits, exact fixture cleanup.

Only this test's UUID-labelled records are removed. Never reset tables/sequences.
Tests hold a blocker lock and observe pg_stat_activity to prove actual contention.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import os
import secrets
import threading
import time
from types import SimpleNamespace
import uuid
import psycopg
from psycopg.rows import dict_row
import pytest
from app import db,sql,event_services as service

pytestmark=[pytest.mark.integration,pytest.mark.concurrency,pytest.mark.skipif(os.getenv('RUN_RAW_SQL_INTEGRATION')!='1',reason='Explicit PostgreSQL integration opt-in required.')]


def connect(app):
    c=app.config
    assert c['DB_NAME']=='university_events_raw'
    return psycopg.connect(dbname=c['DB_NAME'],host=c['DB_HOST'],port=c['DB_PORT'],user=c['DB_USER'],password=c['DB_PASSWORD'],connect_timeout=5,row_factory=dict_row,options='-c search_path=public -c statement_timeout=5000')


@pytest.fixture
def committed(app):
    base=1000000000+secrets.randbelow(500000000)
    tag=uuid.uuid4().hex
    now=datetime.now(timezone.utc)
    start=now+timedelta(days=30)
    committed=False
    conn=connect(app)
    try:
        for ident in (base,base+1):
            conn.execute('INSERT INTO public.users (user_id,full_name,email,password_hash) VALUES (%s,%s,%s,%s)',(ident,'Concurrency fixture',f'{tag}{ident}@example.invalid','unusable-fixture-hash'))
            conn.execute('INSERT INTO public.students (student_id,user_id,student_number,department,batch) VALUES (%s,%s,%s,%s,%s)',(ident,ident,f'C{ident}{tag[:20]}','Test','Test'))
            conn.execute('INSERT INTO public.clubs (club_id,club_name,description) VALUES (%s,%s,%s)',(ident,f'Concurrency {tag} {ident}','Disposable concurrency fixture'))
        conn.execute('INSERT INTO public.venues (venue_id,venue_name,location,capacity) VALUES (%s,%s,%s,%s)',(base,f'Concurrency {tag}','Test',10))
        conn.execute("INSERT INTO public.events (event_id,club_id,venue_id,title,description,start_time,end_time,capacity) VALUES (%s,%s,%s,'Last seat','Disposable',%s,%s,1)",(base,base,base,start,start+timedelta(hours=1)))
        conn.commit();committed=True
        yield app,base,start
    finally:
        conn.rollback()
        if committed:
            try:
                # Exact test-owned club IDs scope all child cleanup, never a table-wide delete.
                conn.execute('DELETE FROM public.registrations WHERE event_id IN (SELECT event_id FROM public.events WHERE club_id=ANY(%s))',([base,base+1],))
                conn.execute('DELETE FROM public.events WHERE club_id=ANY(%s)',([base,base+1],))
                conn.execute('DELETE FROM public.venues WHERE venue_id=%s',(base,))
                conn.execute('DELETE FROM public.clubs WHERE club_id=ANY(%s)',([base,base+1],))
                conn.execute('DELETE FROM public.students WHERE student_id=ANY(%s)',([base,base+1],))
                conn.execute('DELETE FROM public.users WHERE user_id=ANY(%s)',([base,base+1],))
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            finally:
                conn.close()
        else:
            conn.close()


def wait_for_blocked(observer,pids):
    deadline=time.monotonic()+3
    while time.monotonic()<deadline:
        observer.execute('SELECT pg_stat_clear_snapshot()')
        count=observer.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE pid=ANY(%s) AND wait_event_type='Lock'",(pids,)).fetchone()['n']
        if count==len(pids):return
        time.sleep(0.02)
    raise AssertionError('Expected workers were not observed waiting on PostgreSQL locks')


def race(app,blocker_sql,blocker_params,operation):
    barrier=threading.Barrier(3)
    pids=[]
    hold=connect(app);observer=connect(app)
    def worker(index):
        try:
            with app.app_context(),db.transaction(readonly=False) as conn:
                pids.append(conn.info.backend_pid)
                barrier.wait(timeout=5)
                operation(conn,index)
            return 'success'
        except service.RuleViolation as exc:
            return str(exc)
    try:
        hold.execute(blocker_sql,blocker_params)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(worker,i) for i in range(2)]
            try:
                barrier.wait(timeout=5)
                wait_for_blocked(observer,pids)
            finally:
                hold.rollback()
            return [future.result(timeout=10) for future in futures]
    finally:
        hold.close();observer.rollback();observer.close()


def test_two_students_race_for_last_seat(committed):
    app,base,start=committed
    results=race(app,'SELECT event_id FROM public.events WHERE event_id=%s FOR UPDATE',(base,),lambda conn,index:service.register_student(conn,base,base+index))
    assert results.count('success')==1
    assert sum('full' in result for result in results)==1
    with connect(app) as conn:
        assert service.occupied(conn,base)==1
        assert conn.execute('SELECT count(*) AS n FROM public.registrations WHERE event_id=%s',(base,)).fetchone()['n']==1


def test_same_student_concurrent_registration_is_idempotent(committed):
    app,base,start=committed
    results=race(app,'SELECT event_id FROM public.events WHERE event_id=%s FOR UPDATE',(base,),lambda conn,index:service.register_student(conn,base,base))
    assert results==['success','success']
    with connect(app) as conn:
        assert service.occupied(conn,base)==1
        assert conn.execute('SELECT count(*) AS n FROM public.registrations WHERE event_id=%s',(base,)).fetchone()['n']==1


def test_concurrent_clubs_booking_same_venue(committed):
    app,base,start=committed
    actor=SimpleNamespace(user_id=base,role='system_admin')
    values=dict(venue_id=base,title='Race booking',description='Disposable',start_time=start+timedelta(days=1),end_time=start+timedelta(days=1,hours=1),capacity=1)
    results=race(app,'SELECT venue_id FROM public.venues WHERE venue_id=%s FOR UPDATE',(base,),lambda conn,index:service.save_event(conn,actor,values,club_id=base+index))
    assert results.count('success')==1
    assert sum('already booked' in result for result in results)==1
    with connect(app) as conn:
        assert conn.execute('SELECT count(*) AS n FROM public.events WHERE venue_id=%s AND start_time=%s',(base,values['start_time'])).fetchone()['n']==1


def test_database_exclusion_rejects_concurrent_direct_writer(committed):
    app,base,start=committed
    first=connect(app);observer=connect(app)
    ready=threading.Event();pids=[]
    params=(base,base,'Direct booking','Disposable',start+timedelta(days=2),start+timedelta(days=2,hours=1),1)
    def second_writer():
        try:
            with app.app_context(),db.transaction(readonly=False) as conn:
                pids.append(conn.info.backend_pid);ready.set()
                sql.execute(conn,'events.create',params,one=True)
        except db.Conflict as exc:
            return str(exc)
        return 'unexpected success'
    try:
        sql.execute(first,'events.create',params,one=True)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(second_writer)
            try:
                assert ready.wait(5)
                wait_for_blocked(observer,pids)
                first.commit()
            finally:
                first.rollback()
            assert 'venue booking conflicts' in future.result(timeout=10)
        with connect(app) as conn:
            assert conn.execute('SELECT count(*) AS n FROM public.events WHERE venue_id=%s AND start_time=%s',(base,params[4])).fetchone()['n']==1
    finally:
        first.rollback();first.close();observer.rollback();observer.close()
