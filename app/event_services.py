"""Transactional rules. Caller owns commit/rollback; no schema or ORM logic.

Lock order: Club FOR SHARE -> Venue(s) ascending -> Event FOR UPDATE -> Registration.
Registration/status/attendance omit venue locks. Event ownership never changes.
"""
from datetime import datetime, timezone
from . import sql

OCCUPIED={'registered','attended'}


class RuleViolation(Exception):
    def __init__(self,message,code=409):
        super().__init__(message)
        self.code=code


def now_utc():
    return datetime.now(timezone.utc)


def required(row,message='The requested record does not exist.'):
    if row is None: raise RuleViolation(message,404)
    return row


def require_manager(conn,actor,club_id):
    if actor.role=='system_admin': return
    if actor.role!='club_admin' or not sql.execute(conn,'clubs.scope',(club_id,actor.user_id),one=True):
        raise RuleViolation('You cannot manage events for this club.',403)


def event_and_club(conn,event_id):
    preview=required(sql.execute(conn,'events.preview',(event_id,),one=True),'Event not found.')
    club=required(sql.execute(conn,'events.club_share',(preview['club_id'],),one=True))
    event=required(sql.execute(conn,'events.lock',(event_id,),one=True),'Event not found.')
    return event,club


def occupied(conn,event_id):
    return sql.execute(conn,'events.occupied',(event_id,),one=True)['occupied']


def register_student(conn,event_id,student_id,*,now=None):
    event,club=event_and_club(conn,event_id)
    now=now or now_utc() # Deadline evaluated AFTER the event lock is acquired.
    if event['status']!='scheduled' or event['start_time']<=now or not club['is_active']:
        raise RuleViolation('Registration is closed. The event must be upcoming, scheduled, and organized by an active club.')
    existing=sql.execute(conn,'registrations.lock',(event_id,student_id),one=True)
    if existing and existing['status'] in OCCUPIED: return existing
    if occupied(conn,event_id)>=event['capacity']:
        raise RuleViolation('This event is full. Please check again if a seat becomes available.')
    if existing:
        return sql.execute(conn,'registrations.update',('registered',existing['registration_id'],event_id),one=True)
    return sql.execute(conn,'registrations.create',(event_id,student_id),one=True)


def cancel_registration(conn,event_id,student_id,*,now=None):
    event,club=event_and_club(conn,event_id)
    row=sql.execute(conn,'registrations.lock',(event_id,student_id),one=True)
    if row is None or row['status']=='cancelled': return row
    if row['status']=='attended' or event['status']=='completed':
        raise RuleViolation('Completed participation cannot be cancelled.')
    if event['status']!='cancelled' and event['start_time']<=(now or now_utc()):
        raise RuleViolation('Cancellation closes when the event starts.')
    return sql.execute(conn,'registrations.update',('cancelled',row['registration_id'],event_id),one=True)


def save_event(conn,actor,values,*,event_id=None,club_id=None,now=None):
    previous=required(sql.execute(conn,'events.preview',(event_id,),one=True),'Event not found.') if event_id is not None else None
    owner=previous['club_id'] if previous else club_id
    club=required(sql.execute(conn,'events.club_share',(owner,),one=True))
    require_manager(conn,actor,owner) # Recheck scope while assignment changes are blocked by Club lock.
    if not club['is_active']: raise RuleViolation('An inactive club cannot create or edit scheduled events.')
    venue_ids={values['venue_id']}
    if previous: venue_ids.add(previous['venue_id'])
    venues={vid:required(sql.execute(conn,'events.venue_lock',(vid,),one=True),'Venue not found.') for vid in sorted(venue_ids)}
    event=required(sql.execute(conn,'events.lock',(event_id,),one=True),'Event not found.') if previous else None
    if event and event['venue_id'] not in venue_ids:
        raise RuleViolation('Another request moved this event. Reload and try again.')
    now=now or now_utc()
    if event and (event['status']!='scheduled' or event['start_time']<=now):
        raise RuleViolation('Only upcoming scheduled events can be edited.')
    if values['start_time']<=now or values['end_time']<=values['start_time']:
        raise RuleViolation('Choose a future start and an end later than the start.',400)
    if not 1<=values['capacity']<=venues[values['venue_id']]['capacity']:
        raise RuleViolation('Event capacity must be positive and cannot exceed venue capacity.',400)
    if event and values['capacity']<occupied(conn,event_id):
        raise RuleViolation('Capacity cannot be reduced below the occupied seat count.')
    if sql.execute(conn,'events.overlap',(values['venue_id'],values['end_time'],values['start_time'],event_id,event_id)):
        raise RuleViolation('This venue is already booked for part of that time. Choose another venue or time.')
    params=(values['venue_id'],values['title'],values['description'],values['start_time'],values['end_time'],values['capacity'])
    return sql.execute(conn,'events.edit',params+(event_id,),one=True) if event else sql.execute(conn,'events.create',(owner,)+params,one=True)


def change_event_status(conn,actor,event_id,target,*,now=None):
    event,club=event_and_club(conn,event_id)
    require_manager(conn,actor,event['club_id'])
    if target not in {'cancelled','completed'}: raise RuleViolation('Choose cancelled or completed status.',400)
    if event['status']==target: return event
    if event['status']!='scheduled': raise RuleViolation('Cancelled and completed events are final and cannot change status.')
    if target=='completed' and event['end_time']>(now or now_utc()):
        raise RuleViolation('An event can be completed only after it ends.')
    return sql.execute(conn,'events.status',(target,event_id),one=True)


def mark_participant(conn,actor,event_id,registration_id,target,*,now=None):
    event,club=event_and_club(conn,event_id)
    require_manager(conn,actor,event['club_id'])
    row=required(sql.execute(conn,'registrations.participant_lock',(event_id,registration_id),one=True),'Registration not found for this event.')
    if target not in OCCUPIED: raise RuleViolation('Choose registered or attended status. Students manage cancellation.',400)
    if row['status']=='cancelled' or event['status']=='cancelled': raise RuleViolation('Cancelled registrations or events cannot be marked for attendance.')
    if event['start_time']>(now or now_utc()): raise RuleViolation('Attendance can be recorded only after the event starts.')
    return sql.execute(conn,'registrations.update',(target,registration_id,event_id),one=True)
