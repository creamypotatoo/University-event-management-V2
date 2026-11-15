from functools import wraps
import secrets
from urllib.parse import urlsplit
import click
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from . import db, sql
from .validation import registration, valid_email, valid_password, fields, REGISTER_FIELDS

bp=Blueprint('auth',__name__,url_prefix='/auth')
manager=LoginManager()
_DUMMY_HASH=generate_password_hash(secrets.token_urlsafe(32),method='scrypt')


class User(UserMixin):
    def __init__(self,row):
        self.user_id=row['user_id']
        self.full_name=row['full_name']
        self.email=row['email']
        self.role=row['role']
        self.password_hash=row['password_hash']

    def get_id(self):
        return str(self.user_id)

    def check_password(self,password):
        try:
            return check_password_hash(self.password_hash,password)
        except (ValueError,TypeError):
            return False


@manager.user_loader
def load_user(identifier):
    if not isinstance(identifier,str) or not identifier.isascii() or not identifier.isdigit() or len(identifier)>10 or not 1<=int(identifier)<=2147483647:
        return None
    row=sql.read('auth.by_id',(int(identifier),),one=True)
    return User(row) if row else None


def roles_required(*roles):
    def decorate(view):
        @wraps(view)
        @login_required
        def protected(*args,**kwargs):
            if current_user.role not in roles: abort(403)
            return view(*args,**kwargs)
        return protected
    return decorate


def can_manage_club(user,club_id):
    if not user.is_authenticated: return False
    if user.role=='system_admin': return True
    return user.role=='club_admin' and bool(sql.read('clubs.scope',(club_id,user.user_id),one=True))


def club_admin_required(view):
    @wraps(view)
    @login_required
    def protected(*args,**kwargs):
        if not can_manage_club(current_user,kwargs['club_id']): abort(403)
        return view(*args,**kwargs)
    return protected


def safe_next(target):
    if not target or not target.startswith('/') or target.startswith('//'): return None
    if any(c in target for c in ('\\','%')) or any(ord(c)<33 or ord(c)==127 for c in target): return None
    try:
        parsed=urlsplit(target)
    except ValueError:
        return None
    return target if not parsed.scheme and not parsed.netloc else None


@bp.route('/register',methods=['GET','POST'])
def register():
    if current_user.is_authenticated: return redirect(url_for('management.dashboard'))
    values,errors={},{}
    if request.method=='POST':
        values,errors=registration(request.form)
        if not errors:
            try:
                with db.transaction(readonly=False) as conn:
                    row=sql.execute(conn,'auth.create_student_user',(values['full_name'],values['email'],generate_password_hash(request.form['password'],method='scrypt')),one=True)
                    sql.execute(conn,'students.create',(row['user_id'],values['student_number'],values['department'],values['batch']),one=True)
            except db.Conflict:
                errors['form']='Unable to register with these details. Check your information or log in.'
            else:
                session.clear()
                flash('Your student account is ready. Please log in.','success')
                return redirect(url_for('auth.login'))
    return render_template('auth/register.html',values=values,errors=errors,fields=REGISTER_FIELDS),400 if errors else 200


@bp.route('/login',methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('management.dashboard'))
    error=None
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()
        password=request.form.get('password','')
        row=sql.read('auth.by_email',(email,),one=True) if valid_email(email) and 1<=len(password)<=128 else None
        user=User(row) if row else None
        valid=user.check_password(password) if user else check_password_hash(_DUMMY_HASH,password[:128])
        if user and valid:
            destination=safe_next(request.form.get('next'))
            session.clear()
            login_user(user,remember=False,fresh=True)
            session.permanent=True
            session['_remember']='clear'
            return redirect(destination or url_for('management.dashboard'))
        error='Invalid email or password.'
    return render_template('auth/login.html',error=error,next_url=safe_next(request.values.get('next')) or ''),401 if error else 200


@bp.post('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    session['_remember']='clear'
    flash('You have been logged out.','info')
    return redirect(url_for('auth.login'))


def provision(role):
    name=click.prompt('Full name').strip()
    email=click.prompt('Email').strip().lower()
    password=click.prompt('Password',hide_input=True,confirmation_prompt=True)
    _,errors=fields({'full_name':name},[('full_name','Full name',150)])
    if errors or not valid_email(email) or not valid_password(password):
        raise click.ClickException('Invalid name/email or passphrase. Password must contain 12 to 128 printable characters.')
    try:
        with db.transaction(readonly=False) as conn:
            sql.execute(conn,'auth.bootstrap_lock')
            if role=='system_admin' and sql.execute(conn,'auth.existing_admin',one=True):
                raise click.ClickException('A system administrator already exists. Nothing changed.')
            sql.execute(conn,'auth.create_admin_user',(name,email,generate_password_hash(password,method='scrypt'),role),one=True)
    except (db.Conflict,db.DatabaseUnavailable):
        raise click.ClickException('Account creation failed; transaction rolled back. No credentials displayed.') from None
    click.echo('Administrator account created. No credentials displayed.')


def init_app(app):
    manager.login_view='auth.login'
    manager.session_protection='strong'
    manager.init_app(app)
    app.register_blueprint(bp)

    @app.cli.command('create-admin')
    def create_admin():
        """Create the initial system admin; hidden password prompts only."""
        provision('system_admin')

    @app.cli.command('create-club-admin')
    def create_club_admin():
        """Operator-only provisioning; system admin assigns club scope in the UI."""
        provision('club_admin')
