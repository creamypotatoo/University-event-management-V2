from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import os
import pytest
from app import sql,event_services as service
from test_stage2_integration import pg,account,club,login,post

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_RAW_SQL_INTEGRATION')!='1',reason='Explicit PostgreSQL integration opt-in required.')]


@pytest.fixture
def setup(pg):
    app,conn,tag=pg
    uid,_=account(conn,tag,'system_admin')
    cid=club(conn,tag)
    vid=sql.execute(conn,'venues.create',(f'Event venue {tag}','Campus',10),one=True)['venue_id']
    now=datetime.now(timezone.utc)
    values=dict(title=f'Event {tag}',description='Test event',venue_id=vid,start_time=now+timedelta(days=3),end_time=now+timedelta(days=3,hours=1),capacity=2)
    actor=SimpleNamespace(user_id=uid,role='system_admin')
    eid=service.save_event(conn,actor,values,club_id=cid)['event_id']
    return app,conn,tag,actor,cid,vid,eid,values


def form(values):
    return {k:v.isoformat() if isinstance(v,datetime) else str(v) for k,v in values.items()}


def test_event_create_edit_filter_details_and_status_http(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    client=app.test_client();login(client,tag)
    assert client.get('/events').status_code==200
    assert client.get('/events/manage').status_code==200
    assert client.get(f'/clubs/{cid}/events').status_code==200
    assert client.get(f'/clubs/{cid}/events/new').status_code==200
    assert client.get(f'/events/{eid}/edit').status_code==200
    assert client.get(f'/events/{eid}').status_code==200
    updated=form(dict(values,title='Updated event'))
    assert post(client,f'/events/{eid}/edit',dict(updated,club_id=cid+1,status='completed')).status_code==302
    assert sql.execute(conn,'events.detail',(eid,),one=True)['club_id']==cid
    queries=[{'club_id':cid},{'venue_id':vid},{'q':'Updated'},{'status':'scheduled'},{'when':'all','from_date':values['start_time'].date().isoformat(),'to_date':(values['start_time'].date()+timedelta(days=1)).isoformat()}]
    for query in queries: assert b'Updated event' in client.get('/events',query_string=query).data
    assert post(client,f'/events/{eid}/status',{'status':'completed'}).status_code==409
    assert post(client,f'/events/{eid}/status',{'status':'cancelled'}).status_code==302
    assert post(client,f'/events/{eid}/status',{'status':'completed'}).status_code==409
    assert post(client,f'/events/{eid}/edit',updated).status_code==409
    later=dict(values,start_time=values['start_time']+timedelta(hours=3),end_time=values['end_time']+timedelta(hours=3))
    assert post(client,f'/clubs/{cid}/events/new',form(later)).status_code==302
    assert client.delete(f'/events/{eid}').status_code==405


@pytest.mark.parametrize('query',[{'status':'bogus'},{'when':'bogus'},{'club_id':"1 OR 1=1"},{'venue_id':'0'},{'from_date':'bad'},{'to_date':'9999-12-31'},{'from_date':'2040-02-01','to_date':'2040-01-01'},{'page':'0'},{'q':'x'*151}])
def test_bad_filters(setup,query):
    app,*_=setup
    assert app.test_client().get('/events',query_string=query).status_code==400


def test_scoped_event_authorization(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    aid,_=account(conn,tag+'a','club_admin')
    account(conn,tag+'s')
    other=club(conn,tag+'other')
    client=app.test_client();login(client,tag+'a')
    assert client.get(f'/events/{eid}/edit').status_code==403
    sql.execute(conn,'clubs.assign',(cid,aid))
    assert client.get(f'/events/{eid}/edit').status_code==200
    assert client.get(f'/events/{eid}/participants').status_code==200
    assert client.get(f'/clubs/{other}/events/new').status_code==403
    other_values=dict(values,start_time=values['start_time']+timedelta(hours=3),end_time=values['end_time']+timedelta(hours=3))
    other_eid=service.save_event(conn,actor,other_values,club_id=other)['event_id']
    assert client.get(f'/events/{other_eid}/participants').status_code==403
    assert post(client,f'/events/{other_eid}/status',{'status':'cancelled'}).status_code==403
    body=client.get('/events/manage').data
    assert f'/events/{eid}'.encode() in body and f'/events/{other_eid}'.encode() not in body
    sql.execute(conn,'clubs.unassign',(cid,aid))
    assert post(client,f'/events/{eid}/edit',form(values)).status_code==403
    student=app.test_client();login(student,tag+'s')
    assert student.get(f'/clubs/{cid}/events/new').status_code==403
    assert student.get(f'/events/{eid}/participants').status_code==403


def test_registration_cancel_reactivate_idempotent_and_capacity(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    _,sid=account(conn,tag+'s');_,sid2=account(conn,tag+'t');_,sid3=account(conn,tag+'u')
    student=app.test_client();login(student,tag+'s')
    assert post(student,f'/events/{eid}/registration/cancel').status_code==302
    assert sql.execute(conn,'registrations.mine_one',(eid,sid),one=True) is None
    assert post(student,f'/events/{eid}/register',{'student_id':sid2}).status_code==302
    first=sql.execute(conn,'registrations.mine_one',(eid,sid),one=True)
    assert sql.execute(conn,'registrations.mine_one',(eid,sid2),one=True) is None
    assert post(student,f'/events/{eid}/register').status_code==302
    service.register_student(conn,eid,sid2)
    with pytest.raises(service.RuleViolation,match='full'): service.register_student(conn,eid,sid3)
    assert post(student,f'/events/{eid}/registration/cancel').status_code==302
    assert post(student,f'/events/{eid}/register').status_code==302
    assert sql.execute(conn,'registrations.mine_one',(eid,sid),one=True)==first
    assert b'registered' in student.get('/registrations').data
    with pytest.raises(service.RuleViolation,match='occupied'):service.save_event(conn,actor,dict(values,capacity=1),event_id=eid)


@pytest.mark.parametrize('condition',['inactive','started','cancelled','completed'])
def test_registration_eligibility(setup,condition):
    app,conn,tag,actor,cid,vid,eid,values=setup
    _,sid=account(conn,tag+'s')
    if condition=='inactive':sql.execute(conn,'clubs.status',(False,cid),one=True)
    elif condition=='started':conn.execute('UPDATE public.events SET start_time=%s,end_time=%s WHERE event_id=%s',(datetime.now(timezone.utc)-timedelta(hours=1),datetime.now(timezone.utc)+timedelta(hours=1),eid))
    else:sql.execute(conn,'events.status',(condition,eid),one=True)
    with pytest.raises(service.RuleViolation,match='closed'):service.register_student(conn,eid,sid)
    assert sql.execute(conn,'registrations.mine_one',(eid,sid),one=True) is None


def test_cancelled_event_allows_student_cancellation_after_start(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    _,sid=account(conn,tag+'s');service.register_student(conn,eid,sid)
    after_start=values['start_time']+timedelta(minutes=1)
    with pytest.raises(service.RuleViolation,match='closes'):service.cancel_registration(conn,eid,sid,now=after_start)
    service.change_event_status(conn,actor,eid,'cancelled')
    service.cancel_registration(conn,eid,sid,now=after_start)
    assert sql.execute(conn,'registrations.mine_one',(eid,sid),one=True)['status']=='cancelled'


def test_overlap_capacity_adjacent_and_availability(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    with pytest.raises(service.RuleViolation,match='already booked'):service.save_event(conn,actor,values,club_id=cid)
    with pytest.raises(service.RuleViolation,match='venue capacity'):service.save_event(conn,actor,dict(values,capacity=11),event_id=eid)
    adjacent=dict(values,start_time=values['end_time'],end_time=values['end_time']+timedelta(hours=1))
    service.save_event(conn,actor,adjacent,club_id=cid)
    client=app.test_client()
    assert client.get(f'/venues/{vid}/availability').status_code==200
    query={'start_time':values['start_time'].isoformat(),'end_time':values['end_time'].isoformat()}
    assert b'already booked' in client.get(f'/venues/{vid}/availability',query_string=query).data
    assert b'is available' in client.get(f'/venues/{vid}/availability',query_string=dict(query,exclude_event_id=eid)).data
    assert client.get(f'/venues/{vid}/availability',query_string={'start_time':'bad'}).status_code==400
    service.change_event_status(conn,actor,eid,'cancelled')
    service.save_event(conn,actor,values,club_id=cid)


def test_attendance_corrections_completion_history_and_object_scope(setup,monkeypatch):
    app,conn,tag,actor,cid,vid,eid,values=setup
    _,sid=account(conn,tag+'s')
    rid=service.register_student(conn,eid,sid)['registration_id']
    admin=app.test_client();login(admin,tag)
    assert post(admin,f'/events/{eid}/participants/{rid}/status',{'status':'attended'}).status_code==409
    monkeypatch.setattr(service,'now_utc',lambda:values['start_time']+timedelta(minutes=5))
    assert post(admin,f'/events/{eid}/participants/{rid}/status',{'status':'attended'}).status_code==302
    student=app.test_client();login(student,tag+'s')
    assert b'attended' in student.get('/registrations?status=attended').data
    assert post(student,f'/events/{eid}/participants/{rid}/status',{'status':'registered'}).status_code==403
    with pytest.raises(service.RuleViolation,match='Completed participation'):service.cancel_registration(conn,eid,sid)
    assert service.occupied(conn,eid)==1
    assert post(admin,f'/events/{eid}/participants/{rid}/status',{'status':'registered'}).status_code==302
    assert post(admin,f'/events/{eid}/participants/{rid}/status',{'status':'cancelled'}).status_code==400
    assert post(admin,f'/events/{eid}/participants/{rid+999999}/status',{'status':'attended'}).status_code==404
    service.change_event_status(conn,actor,eid,'completed',now=values['end_time']+timedelta(minutes=1))
    with pytest.raises(service.RuleViolation,match='final'):service.change_event_status(conn,actor,eid,'cancelled')
    assert post(admin,f'/events/{eid}/participants/{rid}/status',{'status':'attended'}).status_code==302


def test_cancelled_participant_or_event_cannot_attend(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    _,sid=account(conn,tag+'s')
    rid=service.register_student(conn,eid,sid)['registration_id']
    service.cancel_registration(conn,eid,sid)
    after=values['start_time']+timedelta(minutes=1)
    with pytest.raises(service.RuleViolation,match='Cancelled'):service.mark_participant(conn,actor,eid,rid,'attended',now=after)
    service.register_student(conn,eid,sid)
    service.change_event_status(conn,actor,eid,'cancelled')
    with pytest.raises(service.RuleViolation,match='Cancelled'):service.mark_participant(conn,actor,eid,rid,'attended',now=after)


def test_edit_deadlines_and_inactive_club(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    with pytest.raises(service.RuleViolation,match='upcoming'):service.save_event(conn,actor,values,event_id=eid,now=values['start_time'])
    with pytest.raises(service.RuleViolation,match='future'):service.save_event(conn,actor,dict(values,start_time=datetime.now(timezone.utc)-timedelta(hours=1)),club_id=cid)
    sql.execute(conn,'clubs.status',(False,cid),one=True)
    with pytest.raises(service.RuleViolation,match='inactive'):service.save_event(conn,actor,values,event_id=eid)


def test_injection_csrf_and_atomic_booking_failure(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    client=app.test_client();login(client,tag)
    assert client.post(f'/events/{eid}/status',data={'status':'cancelled'}).status_code==400
    assert client.get('/events',query_string={'q':"x'; DROP TABLE events; --"}).status_code==200
    name="<script>x</script> ' OR 1=1 --"
    good=dict(values,title=name,start_time=values['end_time']+timedelta(hours=2),end_time=values['end_time']+timedelta(hours=3))
    response=post(client,f'/clubs/{cid}/events/new',form(good))
    assert response.status_code==302 and b'&lt;script&gt;' in client.get(response.location).data
    original=sql.execute(conn,'events.detail',(eid,),one=True)
    bad=dict(values,title='Should not persist',start_time=good['start_time'],end_time=good['end_time'])
    assert post(client,f'/events/{eid}/edit',form(bad)).status_code==409
    assert sql.execute(conn,'events.detail',(eid,),one=True)==original
