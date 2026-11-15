from datetime import date, datetime, time, timedelta
from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user
from . import db, sql, event_services as services
from .auth import roles_required, club_admin_required, can_manage_club
from .management import my_student, pagination, require_record
from .event_validation import CAMPUS_TIMEZONE, event_input, timestamp

bp=Blueprint('events',__name__)


@bp.errorhandler(services.RuleViolation)
def rule_failure(error):
    return render_template('errors/error.html',code=error.code,message=str(error)),error.code


@bp.app_template_filter('campus_time')
def campus_time(value,pattern='%d %b %Y, %I:%M %p'):
    return value.astimezone(CAMPUS_TIMEZONE).strftime(pattern)


def identifier(name):
    raw=request.args.get(name,'')
    if not raw: return None
    if not raw.isascii() or not raw.isdigit() or len(raw)>10 or not 1<=int(raw)<=2147483647: abort(400)
    return int(raw)


def search():
    q=request.args.get('q','').strip()
    if len(q)>150 or not all(c.isprintable() for c in q): abort(400)
    return q


def status_filter(allowed):
    status=request.args.get('status','all')
    if status not in allowed: abort(400)
    return status


def directory(manage=False,fixed_club=None):
    q=search();status=status_filter({'all','scheduled','completed','cancelled'})
    when=request.args.get('when','upcoming')
    if when not in {'all','upcoming','past'}: abort(400)
    club_id=fixed_club or identifier('club_id');venue_id=identifier('venue_id')
    boundaries={}
    for name in ('from_date','to_date'):
        raw=request.args.get(name,'')
        try:
            parsed=date.fromisoformat(raw) if raw else None
            if parsed and name=='to_date': parsed+=timedelta(days=1)
            boundaries[name]=datetime.combine(parsed,time.min,CAMPUS_TIMEZONE) if parsed else None
        except (ValueError,OverflowError): abort(400,description='Choose a valid date range.')
    start,end=boundaries['from_date'],boundaries['to_date']
    if start and end and start>=end: abort(400,description='The date range is reversed.')
    page,limit,offset=pagination();now=services.now_utc()
    scope=current_user.user_id if manage and current_user.role=='club_admin' else None
    params=(status,status,when,when,now,when,now,club_id,club_id,venue_id,venue_id,start,start,end,end,q,q,scope,scope,limit,offset)
    choices=sql.read('clubs.assigned',(current_user.user_id,)) if manage and current_user.role=='club_admin' else sql.read('events.clubs')
    return render_template('events/directory.html',events=sql.read('events.directory',params),clubs=choices,venues=sql.read('events.venues'),manage=manage,page=page)


@bp.get('/events')
def index():
    return directory()


@bp.get('/events/manage')
@roles_required('club_admin','system_admin')
def manage():
    return directory(manage=True)


@bp.get('/clubs/<int:club_id>/events')
@club_admin_required
def club_events(club_id):
    require_record(sql.read('clubs.detail',(club_id,),one=True))
    return directory(manage=True,fixed_club=club_id)


@bp.get('/events/<int:event_id>')
def detail(event_id):
    event=require_record(sql.read('events.detail',(event_id,),one=True))
    registration=sql.read('registrations.mine_one',(event_id,my_student()['student_id']),one=True) if current_user.is_authenticated and current_user.role=='student' else None
    now=services.now_utc()
    return render_template('events/detail.html',event=event,registration=registration,may_manage=can_manage_club(current_user,event['club_id']),now=now,
        registration_open=event['status']=='scheduled' and event['start_time']>now and event['club_active'],
        can_cancel=registration and registration['status']=='registered' and event['status']!='completed' and (event['status']=='cancelled' or event['start_time']>now))


@bp.route('/clubs/<int:club_id>/events/new',methods=['GET','POST'])
@club_admin_required
def create(club_id):
    return event_form(require_record(sql.read('clubs.detail',(club_id,),one=True)))


@bp.route('/events/<int:event_id>/edit',methods=['GET','POST'])
@roles_required('club_admin','system_admin')
def edit(event_id):
    event=require_record(sql.read('events.detail',(event_id,),one=True))
    if not can_manage_club(current_user,event['club_id']): abort(403)
    return event_form(require_record(sql.read('clubs.detail',(event['club_id'],),one=True)),event)


def event_form(club,event=None):
    values=dict(event) if event else {}
    if event:
        for name in ('start_time','end_time'): values[name]=campus_time(event[name],'%Y-%m-%dT%H:%M')
    errors={}
    if request.method=='POST':
        parsed,values,errors=event_input(request.form)
        if not errors:
            with db.transaction(readonly=False) as conn:
                row=services.save_event(conn,current_user,parsed,event_id=event['event_id'] if event else None,club_id=club['club_id'])
            flash('Event saved.','success')
            return redirect(url_for('events.detail',event_id=row['event_id']))
    return render_template('events/form.html',event=event,club=club,values=values,errors=errors,venues=sql.read('events.venues')),400 if errors else 200


@bp.post('/events/<int:event_id>/status')
@roles_required('club_admin','system_admin')
def status(event_id):
    with db.transaction(readonly=False) as conn:
        services.change_event_status(conn,current_user,event_id,request.form.get('status'))
    flash('Event status updated. Participation history is preserved.','success')
    return redirect(url_for('events.detail',event_id=event_id))


@bp.post('/events/<int:event_id>/register')
@roles_required('student')
def register(event_id):
    student=my_student()
    with db.transaction(readonly=False) as conn:
        services.register_student(conn,event_id,student['student_id'])
    flash('Your registration is confirmed.','success')
    return redirect(url_for('events.detail',event_id=event_id))


@bp.post('/events/<int:event_id>/registration/cancel')
@roles_required('student')
def cancel(event_id):
    student=my_student()
    with db.transaction(readonly=False) as conn:
        services.cancel_registration(conn,event_id,student['student_id'])
    flash('Your registration is cancelled.','success')
    return redirect(url_for('events.detail',event_id=event_id))


@bp.get('/registrations')
@roles_required('student')
def history():
    status=status_filter({'all','registered','attended','cancelled'});page,limit,offset=pagination()
    return render_template('events/history.html',registrations=sql.read('registrations.history',(my_student()['student_id'],status,status,search(),limit,offset)),page=page)


@bp.get('/events/<int:event_id>/participants')
@roles_required('club_admin','system_admin')
def participants(event_id):
    event=require_record(sql.read('events.detail',(event_id,),one=True))
    if not can_manage_club(current_user,event['club_id']): abort(403)
    status=status_filter({'all','registered','attended','cancelled'});q=search();page,limit,offset=pagination()
    return render_template('events/participants.html',event=event,participants=sql.read('registrations.participants',(event_id,status,status,q,q,limit,offset)),page=page,attendance_open=event['status']!='cancelled' and event['start_time']<=services.now_utc())


@bp.post('/events/<int:event_id>/participants/<int:registration_id>/status')
@roles_required('club_admin','system_admin')
def participant_status(event_id,registration_id):
    with db.transaction(readonly=False) as conn:
        services.mark_participant(conn,current_user,event_id,registration_id,request.form.get('status'))
    flash('Attendance updated.','success')
    return redirect(url_for('events.participants',event_id=event_id))


@bp.get('/venues/<int:venue_id>/availability')
def availability(venue_id):
    venue=require_record(sql.read('venues.detail',(venue_id,),one=True))
    if not request.args.get('start_time') and not request.args.get('end_time'):
        return render_template('events/availability.html',venue=venue,conflicts=None,start=None,end=None,exclude_event_id=identifier('exclude_event_id'))
    try:
        start=timestamp(request.args.get('start_time',''));end=timestamp(request.args.get('end_time',''))
        if end<=start: raise ValueError
    except (ValueError,OverflowError): abort(400,description='Supply valid start_time and end_time in campus time or with explicit offsets.')
    ignore=identifier('exclude_event_id')
    conflicts=sql.read('events.overlap',(venue_id,end,start,ignore,ignore))
    return render_template('events/availability.html',venue=venue,conflicts=conflicts,start=start,end=end,exclude_event_id=ignore)


@bp.app_template_global()
def event_page_url(page):
    values={name:request.args[name] for name in ('q','status','when','club_id','venue_id','from_date','to_date') if name in request.args}
    values.update(request.view_args or {})
    values['page']=page
    return url_for(request.endpoint,**values)
