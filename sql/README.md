# SQL guide

The Stage 1 schema already exists in university_events_raw. Stages 2, 3 and 4 do not
modify it. Do not rerun creation scripts against this existing database, and
never drop/reset tables to make a script succeed.

On an explicitly approved FRESH database only, Stage 1 order was:
1. schema/01_create_tables.sql (tables, PK/FK/UNIQUE/CHECK constraints/defaults)
2. schema/02_constraints_indexes.sql (btree_gist, exclusion and indexes)

Both scripts guard current_database() and use explicit transactions. Use psql -X
-v ON_ERROR_STOP=1 and stop immediately on failure. Existing tables cause failure;
no reset/overwrite is provided. Extension privileges must be available.

queries/01_basic_selects.sql is an optional standalone read-only psql teaching
script; Flask never executes it. queries/02_authentication.sql through
06_venues.sql contain actual runtime SQL split by `-- name: namespace.statement`
headers and loaded by app/sql.py. These use psycopg %s placeholders and must NOT
be run directly in psql. Handler-supplied values are passed separately to
cursor.execute; query text and filenames never come from request input.

The runtime files include JOINs for student profiles, student lists, assigned
clubs, club admin lists, memberships and member lists. Read/update rows in place;
club/membership cancellation uses status updates. No student, club or venue
DELETE statement exists. The Stage 2 scoped assignment DELETE removes an explicitly selected
club_admins association, preserving its user account. Runtime files are trusted
source code; restart Flask after editing them to refresh the SQL-loader cache.


Stage 3 runtime: queries/07_events.sql and 08_registrations_attendance.sql add
20 named statements actually executed by app/events.py and app/event_services.py.
They include event and venue locks, status changes, seat counts, event/club/venue
JOINs, student/registration histories, participants/attendance and overlap checks.
Caller-controlled values use psycopg binding; these files are not standalone psql
scripts. No event delete or new schema statement is added.

demonstrations/01_registration_locks.sql is separate, standalone psql teaching SQL.
Supply your own event_id/student_id through -v, target university_events_raw, and
use password prompting. It checks the database, shows Club FOR SHARE -> Event
FOR UPDATE -> Registration FOR UPDATE and occupied counts, then ROLLBACKs. It
contains no data mutations and is never loaded/executed automatically by Flask.
See README for the exact Windows invocation and concurrency demonstration.


Stage 4 runtime: 09_expenses.sql, 10_financial_reports.sql,
11_participation_reports.sql and 12_reporting_choices.sql contain 22 statements
executed by the expense/report pages, CSV exports and personal summary. Money is
Decimal/numeric. Expense and registration children are grouped independently,
then joined to scoped events/clubs to prevent aggregate fanout. Report reads use
read-only REPEATABLE READ snapshots; mutation/seat-allocation writes remain READ
COMMITTED. Export queries are shared with HTML; no separate unscoped CSV path.

reports/01_create_reporting_views.sql is PROPOSED ONLY. The user explicitly kept
its three normal views pending; do not run persistent CREATE VIEW without fresh
explicit approval. View SELECT definitions are validated without creating objects.
reports/02_pgadmin_examples.sql is an executable standalone read-only set of useful
JOIN/CTE/subquery/aggregate/HAVING/EXISTS examples, guarded to university_events_raw.
It is safe to open in pgAdmin's Query Tool for the NEW database and creates no
objects. Neither file is loaded automatically by Flask.


FINAL STAGE 5 STATUS supersedes earlier pending statements above: the user approved
three normal reporting views and 32 fictional demo records. Both deployments
passed; base tables/constraints/indexes are unchanged. Do not rerun schema/view
creation on existing objects. Repeat seeding must be a no-op, never a data reset.

sql/demo/README.md is the final ordered educational entry point. Five standalone
TEMP/read-only files cover schema/CRUD/constraints/indexes/JOINs/aggregates/subqueries,
TEMP views and transactions/locks without touching public rows. 13_demo_seed.sql
contains operator-only named INSERTs and is never run automatically.
