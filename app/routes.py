from flask import Blueprint, jsonify, render_template, request, abort
from . import db, sql

bp = Blueprint('main', __name__)
# Runtime SQL is deliberately separate from sql/queries demonstration scripts.
CLUBS_SQL = sql.load('clubs.directory')


@bp.get('/')
def index():
    return render_template('index.html')


@bp.get('/health/db')
def health():
    try:
        db.check_connection()
    except db.DatabaseUnavailable:
        return jsonify(status='unavailable'), 503
    return jsonify(status='ok', database='university_events_raw')


@bp.get('/clubs')
def clubs():
    try:
        limit = int(request.args.get('limit', '20'))
    except ValueError:
        abort(400)
    if not 1 <= limit <= 100:
        abort(400)
    q=request.args.get('q','').strip()
    status=request.args.get('status','all')
    if len(q)>150 or not all(c.isprintable() for c in q) or status not in {'all','active','inactive'}:
        abort(400)
    rows=sql.read('clubs.filtered',(status,status=='active',q,q,limit)) if q or status!='all' else db.fetch_all(CLUBS_SQL,(limit,))
    return render_template('clubs.html', clubs=rows)
