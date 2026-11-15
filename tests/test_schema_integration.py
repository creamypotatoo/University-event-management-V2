"""Real PostgreSQL metadata and rollback-only constraint tests.

Explicit negative fixture IDs avoid advancing SERIAL sequences. All writes are
confined to university_events_raw and rolled back, including on assertion failure.
"""
import os
import re
import secrets
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import pytest
from app import db

pytestmark = [pytest.mark.integration, pytest.mark.skipif(
    os.getenv('RUN_RAW_SQL_INTEGRATION') != '1', reason='Explicit PostgreSQL opt-in required.')]
ROOT = Path(__file__).resolve().parents[1]
TABLE_SQL = (ROOT / 'sql/schema/01_create_tables.sql').read_text(encoding='utf-8')
INDEX_SQL = (ROOT / 'sql/schema/02_constraints_indexes.sql').read_text(encoding='utf-8')
TABLES = {'users', 'students', 'clubs', 'club_memberships', 'club_admins',
          'venues', 'events', 'registrations', 'event_expenses'}


def query(app, statement, params=()):
    with app.app_context():
        return db.fetch_all(statement, params)


def test_all_tables_columns_types_defaults(app):
    tables = query(app, "SELECT tablename FROM pg_tables WHERE schemaname='public'")
    assert {r['tablename'] for r in tables} == TABLES
    rows = query(app, """SELECT c.relname AS table_name, a.attname AS column_name,
        format_type(a.atttypid,a.atttypmod) AS data_type, a.attnotnull,
        pg_get_expr(d.adbin,d.adrelid) AS default_expr
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE n.nspname='public' AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped""")
    actual = {(r['table_name'],r['column_name']):r for r in rows}
    expected = set()
    aliases = {'INTEGER':'integer', 'TEXT':'text', 'BOOLEAN':'boolean',
               'DATE':'date', 'TIMESTAMP WITH TIME ZONE':'timestamp with time zone'}
    for table, body in re.findall(r'CREATE TABLE public\.(\w+) \((.*?)\n\);', TABLE_SQL, re.S):
        for line in body.splitlines():
            match = re.match(r'    (\w+) (SERIAL|INTEGER|VARCHAR\(\d+\)|TEXT|BOOLEAN|TIMESTAMP WITH TIME ZONE|NUMERIC\(\d+, \d+\)|DATE) NOT NULL(.*)', line)
            if not match:
                continue
            column, data_type, tail = match.groups()
            key = (table,column)
            expected.add(key)
            row = actual[key]
            assert row['attnotnull'] is True
            pg_type = 'integer' if data_type == 'SERIAL' else aliases.get(data_type, data_type.lower().replace('varchar','character varying').replace(', ',','))
            assert row['data_type'] == pg_type
            if data_type == 'SERIAL':
                assert 'nextval(' in row['default_expr']
            elif 'DEFAULT now()' in tail:
                assert row['default_expr'] == 'now()'
            elif 'DEFAULT true' in tail:
                assert row['default_expr'] == 'true'
            elif "DEFAULT '" in tail:
                value = re.search("DEFAULT '([^']+)'", tail).group(1)
                assert row['default_expr'].startswith("'" + value + "'::")
            else:
                assert row['default_expr'] is None
    assert set(actual) == expected


def test_primary_foreign_unique_and_check_constraints(app):
    rows = query(app, """SELECT c.conname, c.contype, c.convalidated,
        pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
        WHERE n.nspname='public' AND c.contype IN ('p','f','u','c','x')""")
    actual = {r['conname']:r for r in rows}
    expected = set(re.findall(r'CONSTRAINT (\w+)', TABLE_SQL)) | {'ex_events_venue_time'}
    assert set(actual) == expected
    assert all(r['convalidated'] for r in rows)
    assert {kind:sum(r['contype']==kind for r in rows) for kind in 'pfucx'} == dict(p=9,f=10,u=7,c=19,x=1)
    for table,body in re.findall(r'CREATE TABLE public\.(\w+) \((.*?)\n\);', TABLE_SQL, re.S):
        for name,parent,column in re.findall(r'CONSTRAINT (\w+) REFERENCES public\.(\w+) \((\w+)\) ON DELETE RESTRICT',body):
            local = next(line.strip().split()[0] for line in body.splitlines() if name in line)
            definition = actual[name]['definition']
            assert f'FOREIGN KEY ({local}) REFERENCES {parent}({column}) ON DELETE RESTRICT' == definition
        for name,columns in re.findall(r'CONSTRAINT (\w+) UNIQUE \(([^)]+)\)',body):
            assert actual[name]['definition'] == f'UNIQUE ({columns})'
        pk_column = re.search(r'    (\w+) SERIAL NOT NULL CONSTRAINT pk_', body).group(1)
        assert actual[f'pk_{table}']['definition'] == f'PRIMARY KEY ({pk_column})'
        for line in body.splitlines():
            inline = re.search(r'CONSTRAINT (uq_\w+) UNIQUE(?:,|$)', line)
            if inline:
                column = line.strip().split()[0]
                assert actual[inline.group(1)]['definition'] == f'UNIQUE ({column})'


def test_all_indexes_and_exclusion_definition(app):
    rows = query(app, """SELECT ci.relname AS name, am.amname, i.indisvalid,
        i.indisready, i.indisunique, pg_get_indexdef(i.indexrelid) AS definition
        FROM pg_index i JOIN pg_class t ON t.oid=i.indrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN pg_class ci ON ci.oid=i.indexrelid JOIN pg_am am ON am.oid=ci.relam
        WHERE n.nspname='public' AND t.relkind='r'""")
    actual = {r['name']:r for r in rows}
    expected = set(re.findall(r'CONSTRAINT (\w+) (?:PRIMARY KEY|UNIQUE)',TABLE_SQL))
    expected |= set(re.findall(r'CREATE (?:UNIQUE )?INDEX (\w+)',INDEX_SQL)) | {'ex_events_venue_time'}
    assert set(actual) == expected
    assert len(rows) == 31
    assert all(r['indisvalid'] and r['indisready'] for r in rows)
    for unique,name,table,columns in re.findall(r'CREATE (UNIQUE )?INDEX (\w+) ON public\.(\w+) \(([^)]+)\);',INDEX_SQL):
        assert actual[name]['indisunique'] == bool(unique)
        assert actual[name]['amname'] == 'btree'
        assert actual[name]['definition'].endswith(f'ON public.{table} USING btree ({columns})')
    assert actual['ex_events_venue_time']['amname'] == 'gist'
    exclusion = query(app, "SELECT pg_get_constraintdef(oid) AS definition FROM pg_constraint WHERE conname='ex_events_venue_time'")[0]['definition']
    assert 'venue_id WITH =' in exclusion
    assert "tstzrange(start_time, end_time, '[)'::text) WITH &&" in exclusion
    assert "WHERE (((status)::text <> 'cancelled'::text))" in exclusion
    assert query(app, "SELECT extname FROM pg_extension WHERE extname='btree_gist'") == [{'extname':'btree_gist'}]


@pytest.fixture
def fixture_db(app):
    c = app.config
    assert c['DB_NAME'] == 'university_events_raw'
    conn = psycopg.connect(dbname=c['DB_NAME'],host=c['DB_HOST'],port=c['DB_PORT'],
                          user=c['DB_USER'],password=c['DB_PASSWORD'],connect_timeout=5,
                          row_factory=dict_row,options='-c statement_timeout=5000 -c search_path=public')
    ident = -secrets.randbelow(1000000000)-10
    try:
        conn.execute('INSERT INTO public.clubs (club_id,club_name,description) VALUES (%s,%s,%s)', (ident,f'Integration {ident}','Rollback-only fixture'))
        conn.execute('INSERT INTO public.venues (venue_id,venue_name,location,capacity) VALUES (%s,%s,%s,%s)', (ident,f'Integration {ident}','Test',100))
        yield conn,ident
    finally:
        conn.rollback()
        conn.close()


def insert_event(conn,ident,event_id,start,end,status='scheduled'):
    conn.execute("""INSERT INTO public.events (event_id,club_id,venue_id,title,description,start_time,end_time,capacity,status)
        VALUES (%s,%s,%s,'Integration event','Rollback-only',%s,%s,10,%s)""",(event_id,ident,ident,start,end,status))


@pytest.mark.parametrize('status',['scheduled','completed'])
def test_non_cancelled_overlap_is_rejected(fixture_db,status):
    conn,ident = fixture_db
    insert_event(conn,ident,ident,'2040-01-01T10:00:00+06:00','2040-01-01T11:00:00+06:00',status)
    with pytest.raises(psycopg.errors.ExclusionViolation):
        with conn.transaction():
            insert_event(conn,ident,ident-1,'2040-01-01T10:30:00+06:00','2040-01-01T11:30:00+06:00')


def test_adjacent_and_cancelled_bookings_allowed_reactivation_rejected(fixture_db):
    conn,ident = fixture_db
    insert_event(conn,ident,ident,'2040-01-01T10:00:00+06:00','2040-01-01T11:00:00+06:00')
    insert_event(conn,ident,ident-1,'2040-01-01T11:00:00+06:00','2040-01-01T12:00:00+06:00')
    insert_event(conn,ident,ident-2,'2040-01-01T10:30:00+06:00','2040-01-01T11:30:00+06:00','cancelled')
    with pytest.raises(psycopg.errors.ExclusionViolation):
        with conn.transaction():
            conn.execute("UPDATE public.events SET status='scheduled' WHERE event_id=%s",(ident-2,))
    with pytest.raises(psycopg.errors.ExclusionViolation):
        with conn.transaction():
            conn.execute("UPDATE public.events SET start_time='2040-01-01T10:30:00+06:00' WHERE event_id=%s",(ident-1,))


@pytest.mark.parametrize('table',['venues','events'])
def test_nonpositive_capacity_rejected(fixture_db,table):
    conn,ident = fixture_db
    insert_event(conn,ident,ident,'2040-01-01T10:00:00+06:00','2040-01-01T11:00:00+06:00')
    statement = 'UPDATE public.venues SET capacity=0 WHERE venue_id=%s' if table=='venues' else 'UPDATE public.events SET capacity=0 WHERE event_id=%s'
    with pytest.raises(psycopg.errors.CheckViolation):
        with conn.transaction():
            conn.execute(statement,(ident,))


def test_registration_uniqueness_includes_cancelled_rows(fixture_db):
    conn,ident = fixture_db
    insert_event(conn,ident,ident,'2040-01-01T10:00:00+06:00','2040-01-01T11:00:00+06:00')
    conn.execute("INSERT INTO public.users (user_id,full_name,email,password_hash) VALUES (%s,'Integration',%s,'not-a-real-password-hash')",(ident,f'integration{ident}@example.invalid'))
    conn.execute("INSERT INTO public.students (student_id,user_id,student_number,department,batch) VALUES (%s,%s,%s,'Test','Test')",(ident,ident,f'TEST{ident}'))
    conn.execute("INSERT INTO public.registrations (registration_id,event_id,student_id,status) VALUES (%s,%s,%s,'cancelled')",(ident,ident,ident))
    with pytest.raises(psycopg.errors.UniqueViolation):
        with conn.transaction():
            conn.execute('INSERT INTO public.registrations (registration_id,event_id,student_id) VALUES (%s,%s,%s)',(ident-1,ident,ident))
