import csv
from datetime import date,datetime,timedelta,timezone
from decimal import Decimal
from io import StringIO
import os
from pathlib import Path
import re
from types import SimpleNamespace
import pytest
from app import db,sql,event_services
from app.report_queries import Filters,financial,analytics
from test_stage2_integration import pg,account,club,login,post
from test_stage3_integration import setup

pytestmark=[pytest.mark.integration,pytest.mark.skipif(os.getenv('RUN_RAW_SQL_INTEGRATION')!='1',reason='Explicit PostgreSQL integration opt-in required.')]


@pytest.fixture
def data(setup):
    app,conn,tag,actor,cid,vid,eid,values=setup
    other_values=dict(values,title=f'Empty event {tag}',start_time=values['start_time']+timedelta(days=1),end_time=values['end_time']+timedelta(days=1),capacity=4)
    empty=event_services.save_event(conn,actor,other_values,club_id=cid)['event_id']
    ids=[]
    for suffix,amount,expense_date in [('One','10.10',date(2026,1,10)),('Two','20.20',date(2026,2,15))]:
        ids.append(sql.execute(conn,'expenses.create',(eid,suffix,Decimal(amount),expense_date),one=True)['expense_id'])
    students=[]
    for index,status in enumerate(['registered','attended','cancelled']):
        uid,sid=account(conn,tag+str(index));students.append((uid,sid))
        conn.execute('INSERT INTO public.registrations (event_id,student_id,status) VALUES (%s,%s,%s)',(eid,sid,status))
    return app,conn,tag,actor,cid,vid,eid,empty,ids,students,values


def test_financial_aggregation_exact_no_registration_fanout(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    with app.app_context():result=financial(actor,Filters(club_id=cid))
    events={row['event_id']:row for row in result['events']}
    assert events[eid]['total_expenses']==Decimal('30.30') and events[eid]['expense_count']==2
    assert events[eid]['average_expense']==Decimal('15.15')
    assert events[eid]['minimum_expense']==Decimal('10.10') and events[eid]['maximum_expense']==Decimal('20.20')
    assert events[empty]['total_expenses']==Decimal('0') and events[empty]['expense_count']==0
    assert result['clubs'][0]['event_count']==2 and result['clubs'][0]['total_expenses']==Decimal('30.30')
    assert result['summary']['total_expenses']==Decimal('30.30')
    assert [row['total_expenses'] for row in result['monthly']]==[Decimal('10.10'),Decimal('20.20')]
    assert result['highest'][0]['event_id']==eid and result['unrecorded'][0]['event_id']==empty


def test_participation_metrics_and_statuses_no_expense_fanout(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    sql.execute(conn,'events.status',('completed',eid),one=True)
    with app.app_context():result=analytics(actor,Filters(club_id=cid))
    row=next(row for row in result['events'] if row['event_id']==eid)
    assert (row['total_registrations'],row['active_registrations'],row['attended'],row['cancelled_registrations'])==(3,1,1,1)
    assert row['occupied']==2 and row['occupancy_pct']==Decimal('100.0')
    assert row['attendance_rate']==Decimal('50.0') and result['summary']['attendance_rate']==Decimal('50.0')
    assert result['summary']['total_events']==2 and result['summary']['total_registrations']==3
    assert result['clubs'][0]['occupied']==2 and result['popular'][0]['event_id']==eid
    assert {row['status']:row['event_count'] for row in result['statuses']}=={'completed':1,'scheduled':1}


def test_financial_dates_use_expense_dates_not_event_start(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    sql.execute(conn,'events.status',('cancelled',eid),one=True)
    with app.app_context():result=financial(actor,Filters(club_id=cid,from_date=date(2026,1,10),to_date=date(2026,1,10)))
    assert result['summary']['total_expenses']==Decimal('10.10') and result['summary']['event_count']==2
    assert sum(row['expense_count'] for row in result['events'])==1
    assert len(result['monthly'])==1


def test_campus_date_and_month_boundary(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    start=datetime(2026,1,31,18,30,tzinfo=timezone.utc)
    conn.execute('UPDATE public.events SET start_time=%s,end_time=%s WHERE event_id=%s',(start,start+timedelta(hours=1),eid))
    with app.app_context():result=analytics(actor,Filters(club_id=cid,from_date=date(2026,2,1),to_date=date(2026,2,1)))
    assert [r['event_id'] for r in result['events']]==[eid]
    assert result['monthly']==[{'month':date(2026,2,1),'event_count':1}]


def test_completed_attendance_weighted_and_zero_denominator(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    sql.execute(conn,'events.status',('completed',eid),one=True)
    sql.execute(conn,'events.status',('completed',empty),one=True)
    with app.app_context():zero=analytics(actor,Filters(event_id=empty))
    assert zero['summary']['attendance_rate'] is None
    for (_,sid),status in zip(students,['registered','registered','attended']):
        conn.execute('INSERT INTO public.registrations (event_id,student_id,status) VALUES (%s,%s,%s)',(empty,sid,status))
    with app.app_context():result=analytics(actor,Filters(club_id=cid))
    assert result['summary']['attendance_rate']==Decimal('40.0')


def test_expense_crud_confirmation_csrf_and_owner_id_ignored(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    client=app.test_client();login(client,tag)
    assert client.get(f'/events/{eid}/expenses').status_code==200
    assert client.get(f'/events/{eid}/expenses/new').status_code==200
    new={'description':'New expense','amount':'0.10','expense_date':'2026-03-01','event_id':empty}
    assert post(client,f'/events/{eid}/expenses/new',new).status_code==302
    created=conn.execute('SELECT * FROM public.event_expenses WHERE event_id=%s AND description=%s',(eid,'New expense')).fetchone()
    assert created and created['amount']==Decimal('0.10')
    xid=created['expense_id']
    assert post(client,f'/events/{eid}/expenses/{xid}/edit',dict(new,amount='99.99',event_id=empty)).status_code==302
    assert sql.execute(conn,'expenses.detail',(eid,xid),one=True)['amount']==Decimal('99.99')
    assert client.get(f'/events/{eid}/expenses/{xid}/delete').status_code==200
    assert sql.execute(conn,'expenses.detail',(eid,xid),one=True)
    assert client.post(f'/events/{eid}/expenses/{xid}/delete',data={'confirm':'delete'}).status_code==400
    assert post(client,f'/events/{eid}/expenses/{xid}/delete',{'confirm':'wrong'}).status_code==400
    assert post(client,f'/events/{eid}/expenses/{xid}/delete',{'confirm':'delete'}).status_code==302
    assert sql.execute(conn,'expenses.detail',(eid,xid),one=True) is None
    assert sql.execute(conn,'events.detail',(eid,),one=True)['occupied']==2


def test_expense_scope_and_private_reports(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    aid,_=account(conn,tag+'a','club_admin')
    own=club(conn,tag+'other')
    sql.execute(conn,'clubs.assign',(own,aid))
    scoped=app.test_client();login(scoped,tag+'a')
    paths=[f'/events/{eid}/expenses',f'/events/{eid}/expenses/new',f'/events/{eid}/expenses/{ids[0]}/edit',f'/events/{eid}/expenses/{ids[0]}/delete',f'/clubs/{cid}/financial',f'/reports/financial?club_id={cid}',f'/reports/analytics?event_id={eid}',f'/reports/financial.csv?event_id={eid}',f'/reports/participation.csv?club_id={cid}']
    for path in paths:assert scoped.get(path).status_code==403
    report=scoped.get('/reports/financial')
    assert report.status_code==200 and f'Event {tag}'.encode() not in report.data
    sql.execute(conn,'clubs.assign',(cid,aid))
    assert scoped.get(f'/events/{eid}/expenses').status_code==200
    assert post(scoped,f'/events/{eid}/expenses/new',{'description':'Scoped','amount':'1','expense_date':'2026-01-01'}).status_code==302
    sql.execute(conn,'clubs.unassign',(cid,aid))
    assert post(scoped,f'/events/{eid}/expenses/{ids[0]}/delete',{'confirm':'delete'}).status_code==403
    student=app.test_client();login(student,tag+'0')
    for path in ['/reports','/reports/financial','/reports/analytics','/reports/financial.csv','/reports/participation.csv',f'/events/{eid}/expenses']:
        assert student.get(path).status_code==403
    assert b'Total expenses' not in student.get('/dashboard/student').data
    assert b'Your participation' in student.get('/dashboard/student').data


def test_cross_event_expense_id_is_not_authorized(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    client=app.test_client();login(client,tag)
    for suffix in ['edit','delete']:
        assert client.get(f'/events/{empty}/expenses/{ids[0]}/{suffix}').status_code==404
        assert post(client,f'/events/{empty}/expenses/{ids[0]}/{suffix}',{'confirm':'delete','description':'Hijack','amount':'1','expense_date':'2026-01-01'}).status_code==404
    assert sql.execute(conn,'expenses.detail',(eid,ids[0]),one=True)['amount']==Decimal('10.10')


@pytest.mark.parametrize('query',[{'from_date':'bad'},{'from_date':'20260101'},{'to_date':'9999-01-01'},{'from_date':'2026-02-01','to_date':'2026-01-01'},{'club_id':"1 OR 1=1"},{'event_id':'-1'},{'page':'0'}])
def test_bad_report_filters(data,query):
    app,conn,tag,*_=data
    client=app.test_client();login(client,tag)
    assert client.get('/reports/financial',query_string=query).status_code==400


def test_empty_and_unassigned_reports(pg):
    app,conn,tag=pg
    uid,_=account(conn,tag,'club_admin');actor=SimpleNamespace(user_id=uid,role='club_admin')
    with app.app_context():
        f=financial(actor,Filters());a=analytics(actor,Filters())
    assert f['events']==f['clubs']==f['monthly']==[] and f['summary']['total_expenses']==Decimal('0')
    assert a['events']==[] and a['summary']['total_events']==0 and a['summary']['attendance_rate'] is None
    cid=club(conn,tag);sql.execute(conn,'clubs.assign',(cid,uid))
    with app.app_context():
        f=financial(actor,Filters());a=analytics(actor,Filters())
    assert f['clubs'][0]['event_count']==0 and a['clubs'][0]['occupied']==0
    client=app.test_client();login(client,tag)
    for path in ['/reports','/reports/financial','/reports/analytics','/reports/financial.csv','/reports/participation.csv']:
        assert client.get(path).status_code==200


def test_csv_filtering_exact_money_unicode_and_formula_defense(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    title=' =SUM(1,2) \u09ac\u09bf\u09b6\u09cd\u09ac'
    conn.execute('UPDATE public.events SET title=%s WHERE event_id=%s',(title,eid))
    client=app.test_client();login(client,tag)
    response=client.get('/reports/financial.csv',query_string={'event_id':eid,'from_date':'2026-01-01','to_date':'2026-01-31'})
    assert response.status_code==200 and response.content_type=='text/csv; charset=utf-8'
    rows=list(csv.DictReader(StringIO(response.data.decode('utf-8'))))
    assert len(rows)==1 and rows[0]['total_expenses_bdt']=='10.10'
    assert rows[0]['event_title']=="'"+title and rows[0]['expense_count']=='1'
    assert 'attachment' in response.headers['Content-Disposition'] and response.headers['Cache-Control']=='no-store'
    response=client.get('/reports/participation.csv',query_string={'event_id':eid})
    rows=list(csv.DictReader(StringIO(response.data.decode('utf-8'))))
    assert rows[0]['occupied']=='2' and rows[0]['attended']=='1' and rows[0]['attendance_rate']==''
    assert not {'email','student_id','full_name','student_number'}&set(rows[0])
    assert f'{tag}0@example.invalid'.encode() not in response.data


def test_csv_export_ignores_html_pagination(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    for index in range(12):
        extra=dict(values,title=f'Extra {index}',start_time=values['start_time']+timedelta(days=10+index),end_time=values['end_time']+timedelta(days=10+index))
        event_services.save_event(conn,actor,extra,club_id=cid)
    client=app.test_client();login(client,tag)
    response=client.get('/reports/financial',query_string={'club_id':cid,'page':2})
    assert response.status_code==200 and b'Page 2' in response.data
    response=client.get('/reports/financial.csv',query_string={'club_id':cid,'page':2})
    assert len(list(csv.DictReader(StringIO(response.data.decode('utf-8')))))==14


def test_expense_totals_search_and_injection_are_literal(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    sql.execute(conn,'expenses.create',(eid,'100% cost',Decimal('1.11'),date(2026,1,10)),one=True)
    client=app.test_client();login(client,tag)
    response=client.get(f'/events/{eid}/expenses',query_string={'q':'%'})
    assert response.status_code==200 and b'1.11' in response.data and b'100% cost' in response.data
    response=client.get(f'/events/{eid}/expenses',query_string={'q':"x'; DELETE FROM event_expenses; --"})
    assert response.status_code==200 and b'No matching expenses' in response.data
    assert sql.execute(conn,'expenses.detail',(eid,ids[0]),one=True)
    result=post(client,f'/events/{eid}/expenses/new',{'description':"x'); DROP TABLE events; --",'amount':'1','expense_date':'2026-01-01'})
    assert result.status_code==302 and sql.execute(conn,'events.detail',(eid,),one=True)


def test_expense_update_rolls_back_on_failure(data,monkeypatch):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    original=sql.execute
    def failing(connection,name,params=(),*,one=False):
        result=original(connection,name,params,one=one)
        if name=='expenses.edit':raise db.DatabaseUnavailable('injected-private-detail')
        return result
    client=app.test_client();login(client,tag)
    monkeypatch.setattr(sql,'execute',failing)
    response=post(client,f'/events/{eid}/expenses/{ids[0]}/edit',{'description':'Must rollback','amount':'999','expense_date':'2026-01-01'})
    assert response.status_code==503 and b'injected-private-detail' not in response.data
    assert original(conn,'expenses.detail',(eid,ids[0]),one=True)['amount']==Decimal('10.10')


def test_reporting_views_select_definitions_parse_without_creation(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    text=(Path(__file__).resolve().parents[1]/'sql/reports/01_create_reporting_views.sql').read_text(encoding='utf-8')
    definitions=dict(re.findall(r'CREATE VIEW public\.(\w+) AS\n(.*?);',text,re.S))
    assert len(definitions)==3 and 'OR REPLACE' not in text.split('BEGIN;')[1]
    names=['stage4_event_participation_summary','stage4_event_financial_summary']
    for name in names:assert conn.execute('EXPLAIN '+definitions[name]).fetchall()
    third=definitions['stage4_club_activity_summary'].replace('public.stage4_event_participation_summary','v_participation').replace('public.stage4_event_financial_summary','v_financial')
    expanded='WITH v_participation AS ('+definitions[names[0]]+'), v_financial AS ('+definitions[names[1]]+'), '+third[len('WITH '):]
    assert conn.execute('EXPLAIN '+expanded).fetchall()
    participation={r['event_id']:r for r in conn.execute(definitions[names[0]]).fetchall()}
    finances={r['event_id']:r for r in conn.execute(definitions[names[1]]).fetchall()}
    assert participation[eid]['occupied']==2 and finances[eid]['total_expenses']==Decimal('30.30')
    activities={r['club_id']:r for r in conn.execute(expanded).fetchall()}
    assert activities[cid]['total_expenses']==Decimal('30.30')


def test_persistent_views_when_deployed(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    names=['stage4_event_participation_summary','stage4_event_financial_summary','stage4_club_activity_summary']
    present=conn.execute("SELECT viewname FROM pg_views WHERE schemaname='public' AND viewname=ANY(%s)",(names,)).fetchall()
    if not present:pytest.skip('User explicitly kept persistent reporting views pending; no CREATE VIEW executed.')
    assert {r['viewname'] for r in present}==set(names)
    assert conn.execute('SELECT total_expenses FROM public.stage4_event_financial_summary WHERE event_id=%s',(eid,)).fetchone()['total_expenses']==Decimal('30.30')
    assert conn.execute('SELECT occupied FROM public.stage4_event_participation_summary WHERE event_id=%s',(eid,)).fetchone()['occupied']==2


def test_scoped_aggregate_and_csv_never_include_unassigned_costs(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    aid,_=account(conn,tag+'a','club_admin');sql.execute(conn,'clubs.assign',(cid,aid))
    hidden_club=club(conn,tag+'hidden')
    hidden_values=dict(values,title='PRIVATE OTHER CLUB SENTINEL',start_time=values['start_time']+timedelta(days=5),end_time=values['end_time']+timedelta(days=5))
    hidden_event=event_services.save_event(conn,actor,hidden_values,club_id=hidden_club)['event_id']
    sql.execute(conn,'expenses.create',(hidden_event,'PRIVATE COST',Decimal('99999.99'),date(2026,1,1)),one=True)
    scoped_actor=SimpleNamespace(user_id=aid,role='club_admin')
    with app.app_context():
        f=financial(scoped_actor,Filters());a=analytics(scoped_actor,Filters())
    assert f['summary']['total_expenses']==Decimal('30.30') and a['summary']['total_registrations']==3
    client=app.test_client();login(client,tag+'a')
    for path in ['/reports','/reports/financial','/reports/analytics','/reports/financial.csv','/reports/participation.csv']:
        response=client.get(path)
        assert response.status_code==200 and b'PRIVATE OTHER CLUB SENTINEL' not in response.data
    for path in ['/reports/financial.csv','/reports/participation.csv']:
        rows=list(csv.DictReader(StringIO(client.get(path).data.decode('utf-8'))))
        assert {int(row['event_id']) for row in rows}=={eid,empty}


def test_mismatched_and_unknown_report_ids_are_rejected(data):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    other=club(conn,tag+'other')
    client=app.test_client();login(client,tag)
    assert client.get('/reports/financial',query_string={'club_id':other,'event_id':eid}).status_code==400
    assert client.get(f'/events/{eid}/expenses',query_string={'event_id':empty}).status_code==400
    unknown=conn.execute('SELECT coalesce(max(event_id),0)+1 AS id FROM public.events').fetchone()['id']
    assert client.get('/reports/financial',query_string={'event_id':unknown}).status_code==404


@pytest.mark.parametrize('status',['completed','cancelled'])
def test_final_or_inactive_events_still_allow_expense_accounting(data,status):
    app,conn,tag,actor,cid,vid,eid,empty,ids,students,values=data
    sql.execute(conn,'events.status',(status,eid),one=True)
    sql.execute(conn,'clubs.status',(False,cid),one=True)
    client=app.test_client();login(client,tag)
    assert post(client,f'/events/{eid}/expenses/new',{'description':'Retained cost','amount':'0','expense_date':'2026-01-01','category':'IGNORED'}).status_code==302
    assert client.get('/reports/financial',query_string={'event_id':eid}).status_code==200
    assert sql.execute(conn,'events.detail',(eid,),one=True)['status']==status
