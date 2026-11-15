import secrets
import time
from datetime import timedelta
from flask import abort, current_app, request, session


def csrf_token():
    now = time.time()
    if not session.get('_csrf_token') or now-session.get('_csrf_time',0)>3600:
        session['_csrf_token'] = secrets.token_hex(32)
        session['_csrf_time'] = now
    return session['_csrf_token']


def protect_csrf():
    # Let Flask retain its 404/405 behavior for routes/methods that do not exist.
    if request.routing_exception or request.method not in {'POST','PUT','PATCH','DELETE'}:
        return
    expected = session.get('_csrf_token','')
    supplied = request.form.get('csrf_token','')
    age = time.time()-session.get('_csrf_time',0)
    if not expected or len(supplied)!=64 or not supplied.isascii() or not 0<=age<=3600 or not secrets.compare_digest(expected,supplied):
        abort(400, description='Your form expired or could not be verified. Reload and try again.')


def secure_headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; img-src 'self' data:; form-action 'self'; base-uri 'self'; frame-ancestors 'none'"
    if request.endpoint!='static':
        response.headers['Cache-Control']='no-store'
    if current_app.config.get('SESSION_COOKIE_SECURE'):
        response.headers['Strict-Transport-Security']='max-age=31536000'
    return response


def init_app(app):
    app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8),SESSION_REFRESH_EACH_REQUEST=False,
                      MAX_CONTENT_LENGTH=64*1024)
    app.before_request(protect_csrf)
    app.after_request(secure_headers)
    app.jinja_env.globals['csrf_token']=csrf_token
