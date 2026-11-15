"""Preview-first synthetic fixtures. No automatic persistent seeding or data reset."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import secrets
import click
from psycopg import sql as pgsql
from werkzeug.security import generate_password_hash
from . import db,sql
from .validation import valid_password

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'.demo/seed-manifest.json'
DATASET='labdemo-v1'
COUNTS=dict(users=4,students=3,clubs=2,club_memberships=3,club_admins=2,venues=2,events=4,registrations=7,event_expenses=5)
TABLES={
 'users':('user_id',('email',)), 'students':('student_id',('user_id','student_number')),
 'clubs':('club_id',('club_name',)), 'club_memberships':('membership_id',('club_id','student_id')),
 'club_admins':('club_admin_id',('club_id','user_id')), 'venues':('venue_id',('venue_name',)),
 'events':('event_id',('club_id','title')), 'registrations':('registration_id',('event_id','student_id')),
 'event_expenses':('expense_id',('event_id','description')),
}
EMAILS=['labdemo.club@example.invalid']+[f'labdemo.student{i}@example.invalid' for i in range(1,4)]
STUDENT_NUMBERS=[f'LABDEMO-{i:03d}' for i in range(1,4)]
CLUBS=['[LabDemo-v1] Robotics Circle','[LabDemo-v1] Arts Society']
VENUES=['[LabDemo-v1] Innovation Hall','[LabDemo-v1] Studio Room']


class SeedConflict(RuntimeError):pass
class PreviewRollback(Exception):pass


def read_manifest():
    if not MANIFEST.exists():return None
    try:return json.loads(MANIFEST.read_text(encoding='utf-8'))
    except (ValueError,OSError):raise SeedConflict('Demo ownership manifest cannot be read; stop and inspect it locally.') from None


def write_manifest(manifest):
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    temporary=MANIFEST.with_suffix('.tmp')
    temporary.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    temporary.replace(MANIFEST)


def verify_existing(conn,manifest):
    if manifest.get('dataset')!=DATASET or manifest.get('database')!='university_events_raw' or set(manifest.get('rows',{}))!=set(TABLES):
        raise SeedConflict('Unexpected ownership manifest. No existing records changed.')
    for table,(primary,fields) in TABLES.items():
        rows=manifest['rows'][table]
        if len(rows)!=COUNTS[table] or len({row.get('id') for row in rows})!=len(rows):raise SeedConflict('Incomplete manifest. No existing records changed.')
        for row in rows:
            if type(row.get('id')) is not int or not 1<=row['id']<=2147483647 or set(row.get('identity',{}))!=set(fields):
                raise SeedConflict('Invalid manifest row. No existing records changed.')
            query=pgsql.SQL('SELECT {} FROM public.{} WHERE {}=%s').format(pgsql.SQL(',').join(map(pgsql.Identifier,fields)),pgsql.Identifier(table),pgsql.Identifier(primary))
            existing=conn.execute(query,(row['id'],)).fetchone()
            if existing is None or dict(existing)!=row['identity']:
                raise SeedConflict('Demo rows are missing or changed. Refusing to overwrite or repair existing records.')
    return manifest


def create_records(conn,password):
    if not valid_password(password):raise SeedConflict('Use a private demo passphrase of 12 to 128 printable characters.')
    # Any natural-key collision without an ownership manifest is a stop, never an upsert.
    for statement,params in [
        ('SELECT 1 FROM public.users WHERE email=ANY(%s)',(EMAILS,)),
        ('SELECT 1 FROM public.clubs WHERE club_name=ANY(%s)',(CLUBS,)),
        ('SELECT 1 FROM public.venues WHERE venue_name=ANY(%s)',(VENUES,)),
        ('SELECT 1 FROM public.students WHERE student_number=ANY(%s)',(STUDENT_NUMBERS,)),
    ]:
        if conn.execute(statement,params).fetchone():raise SeedConflict('Demo labels already exist without matching ownership. Nothing overwritten.')
    now=datetime.now(timezone.utc).replace(second=0,microsecond=0)
    result={'dataset':DATASET,'database':'university_events_raw','created_at':now.isoformat(),'state':'prepared','rows':{table:[] for table in TABLES}}
    def remember(table,row,**identity):
        ident=row[TABLES[table][0]]
        result['rows'][table].append({'id':ident,'identity':identity})
        return ident
    users=[];students=[]
    for index,email in enumerate(EMAILS):
        role='club_admin' if index==0 else 'student'
        name='Demo Club Administrator (Fictional)' if index==0 else f'Demo Student {index} (Fictional)'
        uid=remember('users',sql.execute(conn,'auth.create_admin_user',(name,email,generate_password_hash(password,method='scrypt'),role),one=True),email=email)
        users.append(uid)
        if index:
            number=STUDENT_NUMBERS[index-1]
            sid=remember('students',sql.execute(conn,'students.create',(uid,number,['Computer Science','Business','Arts'][index-1],'2026'),one=True),user_id=uid,student_number=number)
            students.append(sid)
    clubs=[];venues=[]
    for name in CLUBS:
        clubs.append(remember('clubs',sql.execute(conn,'seed.club',(name,'Fictional, demo-owned DBMS lab club; labdemo-v1.',now-timedelta(days=60)),one=True),club_name=name))
    for name,capacity in zip(VENUES,[100,60]):
        venues.append(remember('venues',sql.execute(conn,'venues.create',(name,'Fictional demo campus',capacity),one=True),venue_name=name))
    for cid in clubs:
        remember('club_admins',sql.execute(conn,'seed.admin',(cid,users[0]),one=True),club_id=cid,user_id=users[0])
    for cid,sid,status in [(clubs[0],students[0],'active'),(clubs[0],students[1],'cancelled'),(clubs[1],students[2],'active')]:
        remember('club_memberships',sql.execute(conn,'seed.membership',(cid,sid,now-timedelta(days=30),status),one=True),club_id=cid,student_id=sid)
    events=[];starts=[]
    for title,cid,vid,days,capacity,status in [
        ('[LabDemo-v1] Robotics Workshop',clubs[0],venues[0],3,2,'scheduled'),
        ('[LabDemo-v1] Campus Arts Seminar',clubs[1],venues[1],5,4,'scheduled'),
        ('[LabDemo-v1] Completed Coding Lab',clubs[0],venues[0],-7,3,'completed'),
        ('[LabDemo-v1] Cancelled Open Mic',clubs[1],venues[1],-3,3,'cancelled'),
    ]:
        start=(now+timedelta(days=days)).replace(hour=4,minute=0)
        eid=remember('events',sql.execute(conn,'seed.event',(cid,vid,title,'Fictional, demo-owned event; labdemo-v1.',start,start+timedelta(hours=2),capacity,status),one=True),club_id=cid,title=title)
        events.append(eid);starts.append(start)
    for event_index,student_index,status in [(0,0,'registered'),(0,1,'cancelled'),(1,2,'registered'),(2,0,'attended'),(2,1,'registered'),(2,2,'attended'),(3,2,'cancelled')]:
        eid=events[event_index];sid=students[student_index]
        remember('registrations',sql.execute(conn,'seed.registration',(eid,sid,starts[event_index]-timedelta(days=1),status),one=True),event_id=eid,student_id=sid)
    from decimal import Decimal
    for event_index,description,amount in [(0,'Demo workshop supplies','10.10'),(0,'Demo printed handouts','20.20'),(1,'Demo art materials','150.50'),(2,'Demo equipment rental','1000.00'),(3,'Demo non-refundable reservation','25.00')]:
        eid=events[event_index]
        remember('event_expenses',sql.execute(conn,'expenses.create',(eid,description,Decimal(amount),starts[event_index].date()),one=True),event_id=eid,description=description)
    assert {table:len(rows) for table,rows in result['rows'].items()}==COUNTS
    return result


def seed(*,apply=False,password=None):
    manifest=None;existing=False
    try:
        with db.transaction(readonly=False) as conn:
            conn.execute('SELECT pg_advisory_xact_lock(42819035)')
            prior=read_manifest()
            if prior:
                manifest=verify_existing(conn,prior);existing=True
            else:
                if apply and not password:raise SeedConflict('Persistent seeding requires a privately supplied demo passphrase.')
                manifest=create_records(conn,password or secrets.token_urlsafe(24))
                if apply:write_manifest(manifest) # Ownership recorded before commit; no secret material.
            if not apply:raise PreviewRollback()
    except PreviewRollback:
        return manifest,existing
    if not existing:
        manifest['state']='applied'
        write_manifest(manifest)
    return manifest,existing


def init_app(app):
    @app.cli.command('seed-demo')
    @click.option('--check',is_flag=True,help='Validate synthetic inserts then roll back; no persistent records.')
    @click.option('--apply',is_flag=True,help='Only after explicit user approval; persistent inserts with hidden password prompt.')
    def seed_demo(check,apply):
        """Default is an offline plan only; never automatically seeds the database."""
        if check and apply:raise click.UsageError('Choose --check or --apply, not both.')
        if not check and not apply:
            click.echo(json.dumps({'dataset':DATASET,'planned_records':COUNTS,'persistent_changes':False,'views':'not changed by seeder'},indent=2))
            return
        password=None
        if apply:
            click.confirm('Only after explicit approval: insert this fictional labdemo-v1 dataset into university_events_raw?',abort=True)
            if read_manifest() is None:
                password=click.prompt('Private demo passphrase',hide_input=True,confirmation_prompt=True)
        try:
            _,existing=seed(apply=apply,password=password)
        except (SeedConflict,db.Conflict,db.DatabaseUnavailable,OSError) as error:
            message=str(error) if isinstance(error,SeedConflict) else 'Demo operation failed; stop and inspect connection/manifest state. No secrets displayed.'
            raise click.ClickException(message) from None
        if not apply:click.echo('Demo inserts validated then rolled back. No persistent demo records; sequences may advance.')
        elif existing:click.echo('Existing demo-owned records verified. No records inserted, updated or deleted.')
        else:click.echo('Fictional demo records created; ownership IDs saved in .demo/seed-manifest.json. No credentials displayed.')
