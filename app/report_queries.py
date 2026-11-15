"""Scoped report APIs. All arithmetic/aggregation stays exact in PostgreSQL."""
from dataclasses import dataclass
from datetime import date,datetime,time,timedelta
from flask import abort
from . import db,sql,event_services
from .event_validation import CAMPUS_TIMEZONE


@dataclass(frozen=True)
class Filters:
    from_date:date|None=None
    to_date:date|None=None
    club_id:int|None=None
    event_id:int|None=None


def scope(actor):
    if actor.role not in {'system_admin','club_admin'}:abort(403)
    return None if actor.role=='system_admin' else actor.user_id


def parameters(actor,filters,*,participation=False):
    userid=scope(actor)
    start,end=filters.from_date,filters.to_date
    if participation:
        start=datetime.combine(start,time.min,CAMPUS_TIMEZONE) if start else None
        end=datetime.combine(end+timedelta(days=1),time.min,CAMPUS_TIMEZONE) if end else None
    return (userid,userid,filters.club_id,filters.club_id,filters.event_id,filters.event_id,filters.event_id,filters.event_id,start,start,end,end)


def financial(actor,filters):
    params=parameters(actor,filters)
    with db.transaction() as conn:
        result={key:sql.execute(conn,'finance.'+key,params) for key in ('events','clubs','monthly','highest','unrecorded')}
        result['summary']=sql.execute(conn,'finance.summary',params,one=True)
    return result


def analytics(actor,filters):
    params=parameters(actor,filters,participation=True)
    with db.transaction() as conn:
        result={key:sql.execute(conn,'analytics.'+key,params) for key in ('events','clubs','monthly','statuses','popular')}
        result['summary']=sql.execute(conn,'analytics.summary',params+(event_services.now_utc(),),one=True)
    return result
