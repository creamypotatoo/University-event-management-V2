from datetime import date,datetime
from decimal import Decimal
from flask import Blueprint,abort,flash,redirect,render_template,request,url_for
from flask_login import current_user
from . import db,sql,event_services
from .auth import roles_required,can_manage_club,club_admin_required
from .event_validation import CAMPUS_TIMEZONE
from .events import identifier,search
from .management import pagination,require_record
from .report_validation import expense_input
from .report_queries import Filters,financial as financial_data,analytics as analytics_data,scope
from .csv_export import csv_response

bp=Blueprint('reports',__name__)


@bp.app_template_filter('money')
def money(value):
    return f'{value if value is not None else Decimal("0.00"):,.2f}'


def manager_event(event_id):
    event=require_record(sql.read('events.detail',(event_id,),one=True))
    if not can_manage_club(current_user,event['club_id']):abort(403)
    return event


def report_filters():
    values={}
    for name in ('from_date','to_date'):
        raw=request.args.get(name,'')
        try:
            parsed=date.fromisoformat(raw) if raw else None
            if parsed and (parsed.isoformat()!=raw or parsed.year==9999):raise ValueError
            values[name]=parsed
        except ValueError:abort(400,description='Choose canonical YYYY-MM-DD dates before year 9999.')
    if values['from_date'] and values['to_date'] and values['from_date']>values['to_date']:
        abort(400,description='The end date cannot precede the start date.')
    values['club_id']=identifier('club_id');values['event_id']=identifier('event_id')
    if values['club_id']:
        if not can_manage_club(current_user,values['club_id']):abort(403)
        require_record(sql.read('clubs.detail',(values['club_id'],),one=True))
    if values['event_id']:
        event=manager_event(values['event_id'])
        if values['club_id'] and event['club_id']!=values['club_id']:abort(400,description='The event does not belong to the selected club.')
    return Filters(**values)


def choices():
    user=scope(current_user)
    return {'clubs':sql.read('reports.clubs',(user,user)),'events':sql.read('reports.events',(user,user))}


def report_page(rows):
    page,_,_=pagination()
    return rows[(page-1)*10:page*10],page,len(rows)>page*10


def locked_expense_event(conn,event_id):
    event,club=event_services.event_and_club(conn,event_id)
    event_services.require_manager(conn,current_user,event['club_id'])
    return event


@bp.get('/events/<int:event_id>/expenses')
@roles_required('club_admin','system_admin')
def expenses(event_id):
    event=manager_event(event_id);filters=report_filters()
    if (filters.event_id and filters.event_id!=event_id) or (filters.club_id and filters.club_id!=event['club_id']):
        abort(400,description='Expense filters must match this event.')
    q=search();page,limit,offset=pagination()
    params=(event_id,filters.from_date,filters.from_date,filters.to_date,filters.to_date,q)
    with db.transaction() as conn:
        rows=sql.execute(conn,'expenses.list',params+(limit,offset))
        totals=sql.execute(conn,'expenses.total',params,one=True)
    return render_template('reports/expenses.html',event=event,expenses=rows,totals=totals,page=page)


@bp.route('/events/<int:event_id>/expenses/new',methods=['GET','POST'])
@roles_required('club_admin','system_admin')
def expense_create(event_id):
    return expense_form(manager_event(event_id))


@bp.route('/events/<int:event_id>/expenses/<int:expense_id>/edit',methods=['GET','POST'])
@roles_required('club_admin','system_admin')
def expense_edit(event_id,expense_id):
    event=manager_event(event_id)
    return expense_form(event,require_record(sql.read('expenses.detail',(event_id,expense_id),one=True)))


def expense_form(event,expense=None):
    values=dict(description=expense['description'],amount=format(expense['amount'],'.2f'),expense_date=expense['expense_date'].isoformat()) if expense else {'expense_date':datetime.now(CAMPUS_TIMEZONE).date().isoformat()}
    errors={}
    if request.method=='POST':
        parsed,values,errors=expense_input(request.form)
        if not errors:
            with db.transaction(readonly=False) as conn:
                locked_expense_event(conn,event['event_id'])
                if expense:
                    require_record(sql.execute(conn,'expenses.lock',(event['event_id'],expense['expense_id']),one=True))
                    sql.execute(conn,'expenses.edit',(parsed['description'],parsed['amount'],parsed['expense_date'],event['event_id'],expense['expense_id']),one=True)
                else:
                    sql.execute(conn,'expenses.create',(event['event_id'],parsed['description'],parsed['amount'],parsed['expense_date']),one=True)
            flash('Expense saved.','success')
            return redirect(url_for('reports.expenses',event_id=event['event_id']))
    return render_template('reports/expense_form.html',event=event,expense=expense,values=values,errors=errors),400 if errors else 200


@bp.route('/events/<int:event_id>/expenses/<int:expense_id>/delete',methods=['GET','POST'])
@roles_required('club_admin','system_admin')
def expense_delete(event_id,expense_id):
    event=manager_event(event_id)
    expense=require_record(sql.read('expenses.detail',(event_id,expense_id),one=True))
    if request.method=='POST':
        if request.form.get('confirm')!='delete':abort(400,description='Confirm deletion using the confirmation form.')
        with db.transaction(readonly=False) as conn:
            locked_expense_event(conn,event_id)
            require_record(sql.execute(conn,'expenses.lock',(event_id,expense_id),one=True))
            require_record(sql.execute(conn,'expenses.delete',(event_id,expense_id),one=True))
        flash('Expense deleted. The event and its other records were preserved.','success')
        return redirect(url_for('reports.expenses',event_id=event_id))
    return render_template('reports/expense_delete.html',event=event,expense=expense)


@bp.get('/reports')
@roles_required('club_admin','system_admin')
def dashboard():
    filters=report_filters()
    return render_template('reports/dashboard.html',finance=financial_data(current_user,filters),analytics=analytics_data(current_user,filters))


@bp.get('/reports/financial')
@roles_required('club_admin','system_admin')
def financial():
    data=financial_data(current_user,report_filters());rows,page,more=report_page(data['events'])
    return render_template('reports/financial.html',data=data,rows=rows,page=page,more=more,**choices())


@bp.get('/clubs/<int:club_id>/financial')
@club_admin_required
def club_financial(club_id):
    require_record(sql.read('clubs.detail',(club_id,),one=True))
    return redirect(url_for('reports.financial',club_id=club_id))


@bp.get('/reports/analytics')
@roles_required('club_admin','system_admin')
def analytics():
    data=analytics_data(current_user,report_filters());rows,page,more=report_page(data['events'])
    return render_template('reports/analytics.html',data=data,rows=rows,page=page,more=more,**choices())


@bp.get('/reports/financial.csv')
@roles_required('club_admin','system_admin')
def financial_csv():
    data=financial_data(current_user,report_filters())
    return csv_response('event-expenses.csv',['event_id','event_title','club_id','club_name','expense_count','total_expenses_bdt'],
        ((r['event_id'],r['title'],r['club_id'],r['club_name'],r['expense_count'],r['total_expenses']) for r in data['events']))


@bp.get('/reports/participation.csv')
@roles_required('club_admin','system_admin')
def participation_csv():
    data=analytics_data(current_user,report_filters())
    columns=['event_id','title','club_id','club_name','status','capacity','total_registrations','active_registrations','attended','cancelled_registrations','occupied','occupancy_pct','attendance_rate']
    return csv_response('event-participation.csv',columns,([row[name] for name in columns] for row in data['events']))


@bp.app_template_global()
def report_url(endpoint=None,page=None):
    values={name:request.args[name] for name in ('from_date','to_date','club_id','event_id') if name in request.args}
    if endpoint is None:
        endpoint=request.endpoint
        values.update(request.view_args or {})
        if 'q' in request.args:values['q']=request.args['q']
    if page is not None:values['page']=page
    return url_for(endpoint,**values)
