from datetime import datetime,timezone
from unittest.mock import MagicMock,patch
import pytest
import psycopg
from app import db
from app.event_validation import event_input,timestamp


def test_campus_time_and_explicit_offsets():
    assert timestamp('2040-01-01T10:00')==datetime(2040,1,1,4,tzinfo=timezone.utc)
    assert timestamp('2040-01-01T10:00+06:00')==timestamp('2040-01-01T04:00Z')


@pytest.mark.parametrize('value',['not-a-date','2040-01-01','2040-99-99T10:00','x'*50])
def test_invalid_times(value):
    with pytest.raises((ValueError,OverflowError)):timestamp(value)


@pytest.mark.parametrize('field,value',[('title',''),('description',''),('capacity','0'),('capacity','-1'),('capacity','2147483648'),('capacity',"1;DROP TABLE events"),('venue_id','abc'),('start_time','bad'),('end_time','2040-01-01T09:00')])
def test_event_input_validation(field,value):
    form=dict(title='Event',description='Description',capacity='10',venue_id='1',start_time='2040-01-01T10:00',end_time='2040-01-01T11:00')
    form[field]=value
    _,display,errors=event_input(form)
    assert field in errors
    assert display[field]==value


def test_exclusion_failure_maps_to_friendly_conflict_and_rolls_back(app):
    conn=MagicMock()
    with app.app_context(),patch('app.db.psycopg.connect',return_value=conn):
        with pytest.raises(db.Conflict,match='venue booking conflicts'):
            with db.transaction(readonly=False):raise psycopg.errors.ExclusionViolation('private')
    conn.rollback.assert_called_once();conn.close.assert_called_once();conn.commit.assert_not_called()


@pytest.mark.parametrize('error',[psycopg.errors.DeadlockDetected,psycopg.errors.SerializationFailure,psycopg.errors.LockNotAvailable])
def test_retryable_conflicts_are_safe(app,error):
    conn=MagicMock()
    with app.app_context(),patch('app.db.psycopg.connect',return_value=conn):
        with pytest.raises(db.Conflict,match='Reload and try again'):
            with db.transaction(readonly=False):raise error('private')
    conn.rollback.assert_called_once();conn.commit.assert_not_called()


@pytest.mark.parametrize('path',['/events/manage','/registrations','/events/1/edit','/events/1/participants','/clubs/1/events/new'])
def test_protected_event_pages_redirect_anonymous(app,path):
    response=app.test_client().get(path)
    assert response.status_code==302 and '/auth/login' in response.location
