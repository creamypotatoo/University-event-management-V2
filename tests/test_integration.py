"""Disabled until explicit approval and schema setup. Never writes fixtures."""
import os
import pytest
from app import db

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv('RUN_RAW_SQL_INTEGRATION') != '1',
    reason='Pending explicit database approval and setup; no PostgreSQL connection attempted.')]


def test_live_connectivity(app):
    with app.app_context():
        row = db.check_connection()
        assert row == {'database': 'university_events_raw', 'ok': 1}


def test_live_clubs_read_only(app):
    with app.app_context():
        with db.transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only')
                assert cursor.fetchone()['transaction_read_only'] == 'on'
                cursor.execute('SELECT club_id, club_name FROM public.clubs ORDER BY club_id LIMIT %s', (5,))
                assert len(cursor.fetchall()) <= 5
