from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from . import db, sql
from .auth import roles_required, club_admin_required, can_manage_club
from .validation import fields, venue, PROFILE_FIELDS, CLUB_FIELDS, VENUE_FIELDS, valid_email

bp=Blueprint('management',__name__)


def require_record(row):
    if row is None: abort(404)
    return row


def my_student():
    row=sql.read('students.by_user',(current_user.user_id,),one=True)
    if row is None: abort(403)
    return row


def pagination():
    raw=request.args.get('page','1')
    if not raw.isascii() or not raw.isdigit() or len(raw)>6 or not 1<=int(raw)<=100000: abort(400)
    return int(raw),20,(int(raw)-1)*20


def form_response(title,spec,values,errors,back):
    return render_template('management/form.html',heading=title,fields=spec,values=values,errors=errors,back=back),400 if errors else 200


def lock_club(conn,club_id,manage=False):
    club=require_record(sql.execute(conn,'clubs.lock',(club_id,),one=True))
    if manage and current_user.role!='system_admin' and not sql.execute(conn,'clubs.scope',(club_id,current_user.user_id),one=True):
        abort(403)
    return club


@bp.get('/dashboard')
@login_required
def dashboard():
    endpoints={'student':'management.student_dashboard','system_admin':'management.admin_dashboard','club_admin':'management.club_admin_dashboard'}
    if current_user.role not in endpoints: abort(403)
    return redirect(url_for(endpoints[current_user.role]))


@bp.get('/dashboard/student')
@roles_required('student')
def student_dashboard():
    from .event_services import now_utc
    student=my_student();now=now_utc()
    personal=sql.read('reports.personal',(now,now,student['student_id']),one=True)
    return render_template('management/dashboard.html',heading='Student dashboard',student=student,clubs=[],personal=personal)


@bp.get('/dashboard/system-admin')
@roles_required('system_admin')
def admin_dashboard():
    return render_template('management/dashboard.html',heading='System administrator dashboard',student=None,clubs=[])


@bp.get('/dashboard/club-admin')
@roles_required('club_admin')
def club_admin_dashboard():
    return render_template('management/dashboard.html',heading='Club administrator dashboard',student=None,clubs=sql.read('clubs.assigned',(current_user.user_id,)))


@bp.get('/profile')
@roles_required('student')
def profile():
    return render_template('management/profile.html',student=my_student())


@bp.route('/profile/edit',methods=['GET','POST'])
@roles_required('student')
def profile_edit():
    student=my_student()
    values,errors=student,{}
    if request.method=='POST':
        values,errors=fields(request.form,PROFILE_FIELDS)
        if not errors:
            with db.transaction(readonly=False) as conn:
                require_record(sql.execute(conn,'students.update_name',(values['full_name'],current_user.user_id),one=True))
                require_record(sql.execute(conn,'students.update_profile',(values['department'],values['batch'],current_user.user_id),one=True))
            flash('Your profile has been updated.','success')
            return redirect(url_for('management.profile'))
    return form_response('Edit your student profile',PROFILE_FIELDS,values,errors,url_for('management.profile'))


@bp.get('/students')
@roles_required('system_admin')
def students():
    page,limit,offset=pagination()
    return render_template('management/students.html',students=sql.read('students.directory',(limit,offset)),page=page)


@bp.get('/students/<int:student_id>')
@roles_required('student','system_admin')
def student_detail(student_id):
    if current_user.role=='student' and my_student()['student_id']!=student_id: abort(403)
    return render_template('management/profile.html',student=require_record(sql.read('students.by_id',(student_id,),one=True)))


@bp.get('/clubs/<int:club_id>')
def club_detail(club_id):
    club=require_record(sql.read('clubs.detail',(club_id,),one=True))
    membership=None
    if current_user.is_authenticated and current_user.role=='student':
        membership=sql.read('memberships.mine_one',(club_id,my_student()['student_id']),one=True)
    may_manage=can_manage_club(current_user,club_id)
    admins=sql.read('clubs.admins',(club_id,)) if current_user.is_authenticated and current_user.role=='system_admin' else []
    return render_template('management/club_detail.html',club=club,membership=membership,may_manage=may_manage,admins=admins)


@bp.route('/clubs/new',methods=['GET','POST'])
@roles_required('system_admin')
def club_create():
    return club_form()


@bp.route('/clubs/<int:club_id>/edit',methods=['GET','POST'])
@club_admin_required
def club_edit(club_id):
    return club_form(club_id)


def club_form(club_id=None):
    values=require_record(sql.read('clubs.detail',(club_id,),one=True)) if club_id else {}
    errors={}
    if request.method=='POST':
        values,errors=fields(request.form,CLUB_FIELDS)
        if not errors:
            try:
                with db.transaction(readonly=False) as conn:
                    if club_id:
                        lock_club(conn,club_id,manage=True)
                        row=sql.execute(conn,'clubs.edit',(values['club_name'],values['description'],club_id),one=True)
                    else:
                        row=sql.execute(conn,'clubs.create',(values['club_name'],values['description']),one=True)
            except db.Conflict:
                errors['form']='A club with that name already exists.'
            else:
                flash('Club saved.','success')
                return redirect(url_for('management.club_detail',club_id=row['club_id']))
    return form_response('Edit club' if club_id else 'Create club',CLUB_FIELDS,values,errors,url_for('main.clubs'))


@bp.post('/clubs/<int:club_id>/status')
@roles_required('system_admin')
def club_status(club_id):
    target=request.form.get('status')
    if target not in {'active','inactive'}: abort(400)
    with db.transaction(readonly=False) as conn:
        lock_club(conn,club_id)
        sql.execute(conn,'clubs.status',(target=='active',club_id),one=True)
    flash('Club status updated. Existing memberships are preserved.','success')
    return redirect(url_for('management.club_detail',club_id=club_id))


@bp.post('/clubs/<int:club_id>/admins')
@roles_required('system_admin')
def assign_admin(club_id):
    email=request.form.get('email','').strip().lower()
    if not valid_email(email): abort(400,description='Enter a valid administrator email.')
    with db.transaction(readonly=False) as conn:
        lock_club(conn,club_id)
        candidate=sql.execute(conn,'clubs.admin_candidate',(email,),one=True)
        if not candidate: abort(400,description='Use an existing club administrator account provisioned through the CLI.')
        sql.execute(conn,'clubs.assign',(club_id,candidate['user_id']))
    flash('Club administrator assigned.','success')
    return redirect(url_for('management.club_detail',club_id=club_id))


@bp.post('/clubs/<int:club_id>/admins/<int:user_id>/remove')
@roles_required('system_admin')
def remove_admin(club_id,user_id):
    with db.transaction(readonly=False) as conn:
        lock_club(conn,club_id)
        sql.execute(conn,'clubs.unassign',(club_id,user_id))
    flash('Club administrator assignment removed. Account preserved.','success')
    return redirect(url_for('management.club_detail',club_id=club_id))


@bp.post('/clubs/<int:club_id>/join')
@roles_required('student')
def join_club(club_id):
    return change_membership(club_id,True)


@bp.post('/clubs/<int:club_id>/leave')
@roles_required('student')
def leave_club(club_id):
    return change_membership(club_id,False)


def change_membership(club_id,joining):
    student=my_student()
    with db.transaction(readonly=False) as conn:
        club=lock_club(conn,club_id)
        if joining and not club['is_active']: abort(409,description='Inactive clubs cannot accept memberships.')
        sql.execute(conn,'memberships.join' if joining else 'memberships.leave',(club_id,student['student_id']),one=True)
    flash('You have joined the club.' if joining else 'Your membership is cancelled.','success')
    return redirect(url_for('management.club_detail',club_id=club_id))


@bp.get('/memberships')
@roles_required('student')
def memberships():
    page,limit,offset=pagination()
    rows=sql.read('memberships.mine',(my_student()['student_id'],limit,offset))
    return render_template('management/memberships.html',memberships=rows,page=page)


@bp.get('/clubs/<int:club_id>/members')
@club_admin_required
def club_members(club_id):
    club=require_record(sql.read('clubs.detail',(club_id,),one=True))
    page,limit,offset=pagination()
    return render_template('management/members.html',club=club,members=sql.read('memberships.members',(club_id,limit,offset)),page=page)


@bp.post('/clubs/<int:club_id>/members/<int:membership_id>/status')
@club_admin_required
def member_status(club_id,membership_id):
    target=request.form.get('status')
    if target not in {'active','cancelled'}: abort(400)
    with db.transaction(readonly=False) as conn:
        club=lock_club(conn,club_id,manage=True)
        if target=='active' and not club['is_active']: abort(409,description='Inactive clubs cannot reactivate memberships.')
        require_record(sql.execute(conn,'memberships.status',(target,club_id,membership_id),one=True))
    flash('Membership updated.','success')
    return redirect(url_for('management.club_members',club_id=club_id))


@bp.get('/venues')
def venues():
    page,limit,offset=pagination()
    return render_template('management/venues.html',venues=sql.read('venues.directory',(limit,offset)),page=page)


@bp.route('/venues/new',methods=['GET','POST'])
@roles_required('system_admin')
def venue_create():
    return venue_form()


@bp.route('/venues/<int:venue_id>/edit',methods=['GET','POST'])
@roles_required('system_admin')
def venue_edit(venue_id):
    return venue_form(venue_id)


def venue_form(venue_id=None):
    values=require_record(sql.read('venues.detail',(venue_id,),one=True)) if venue_id else {}
    errors={}
    if request.method=='POST':
        values,errors=venue(request.form)
        if not errors:
            try:
                with db.transaction(readonly=False) as conn:
                    if venue_id:
                        require_record(sql.execute(conn,'venues.lock',(venue_id,),one=True))
                        if sql.execute(conn,'venues.capacity_guard',(venue_id,int(values['capacity'])),one=True):
                            abort(409,description='Capacity cannot be below an existing non-cancelled event capacity.')
                        sql.execute(conn,'venues.edit',(values['venue_name'],values['location'],int(values['capacity']),venue_id),one=True)
                    else:
                        sql.execute(conn,'venues.create',(values['venue_name'],values['location'],int(values['capacity'])),one=True)
            except db.Conflict:
                errors['form']='A venue with that name already exists.'
            else:
                flash('Venue saved.','success')
                return redirect(url_for('management.venues'))
    return form_response('Edit venue' if venue_id else 'Create venue',VENUE_FIELDS,values,errors,url_for('management.venues'))
