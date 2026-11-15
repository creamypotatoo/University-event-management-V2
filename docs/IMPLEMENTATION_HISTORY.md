# Historical implementation notes (Stages 1-4)

Historical only: the current deployment, seed and test status is in the root README and submission checklist. Earlier pending/empty-data statements describe those earlier runs.

# University Event and Club Management - Raw SQL Edition

Stage 4 is complete: authentication, profiles, clubs, memberships, venues,
events, registrations, attendance, expense management, financial/participation
reports and authorized CSV exports. The database is university_events_raw.
All nine base tables and constraints are preserved. No ORM or migration framework
is used. Three proposed normal reporting views remain UNDEPLOYED by explicit user
choice; the app works entirely through ordinary SELECT reports. Stage 5 has not started.

Current full test result: **212 passed, 0 failed, 1 skipped**. The only skip is
persistent-view verification because the user kept those new objects pending.

## Stack and architecture

Python 3.12, Flask 3, psycopg 3 with dict_row, Flask-Login, Werkzeug scrypt,
python-dotenv, Bootstrap 5/Jinja and pytest. All SQL is handwritten PostgreSQL.

| Source | Responsibility |
| --- | --- |
| app/__init__.py | Factory, blueprint setup, safe errors and database-name guard |
| app/config.py | Loads this project's .env; connection, secret and cookie configuration |
| app/db.py | Read-only default transactions; explicit write opt-in, commit/rollback/cleanup |
| app/sql.py | Cached, trusted named SQL loader; cursor execution and bound parameters |
| app/auth.py | Non-ORM UserMixin, database-backed login loader, role/scope decorators, registration/login/logout, administrator CLI |
| app/security.py | Session-bound expiring CSRF, cookie settings, security headers |
| app/validation.py | Whitelisted fields, email/student-number/password/text/capacity validation |
| app/routes.py | Public homepage, bounded club directory and read-only health check |
| app/management.py | Dashboards, profiles, clubs, assignments, memberships and venues |
| app/templates/auth/ | Registration and login forms |
| app/templates/management/ | Reusable form macros, profiles, dashboards, details and management lists |
| app/templates/base.html | Shared Bootstrap navigation, messages and POST logout |
| app/templates/errors/error.html | Friendly errors without database details or credentials |
| app/static/css/style.css | Local layout, descriptions and form styles |
| run.py | Localhost Flask development entry point, debug off |
| sql/schema/ | Stage 1 DDL, unchanged; do not reapply to the existing database |
| sql/queries/ | Commented examples plus named statements actually used by Flask |
| tests/test_stage1.py | Original 19 offline cases, unchanged |
| tests/test_integration.py | Original 2 live read-only cases, unchanged |
| tests/test_schema_integration.py | Original 9 PostgreSQL schema/constraint cases, unchanged in Stage 2 |
| tests/test_stage2_security.py | 41 validation, session, SQL binding, CSRF, access and transaction cases |
| tests/test_stage2_integration.py | 20 PostgreSQL-backed application workflow cases |
| scripts/init_secret.py | Generates a private persistent secret without printing it; preserves existing secrets |
| scripts/verify_stage2_http.py | Actual local HTTP workflows in a rolled-back outer transaction |
| requirements.txt / pytest.ini | Dependencies and integration-test marker |
| .env.example / .gitignore | Blank secret/credential template and exclusions for private files/caches |

Runtime reads use read-only REPEATABLE READ connections, providing a stable
snapshot within each multi-query report. Writes explicitly use READ COMMITTED,
preserving the last-seat allocation protocol. Mutation handlers opt into
`db.transaction(readonly=False)` and execute related operations using the same
connection. A successful transaction commits; PostgreSQL or application errors
roll back; the connection always closes. Unique/constraint conflicts become safe
form errors or HTTP 409; connection errors return a friendly HTTP 503.
`db-check` and /health/db remain read-only. Only university_events_raw is allowed
by the factory and connection helper.

## Authentication and sessions

Registration creates users and students atomically with a hardcoded student
role. Submitted privileged roles, owner IDs and extra fields are ignored.
Duplicate email/student-number conflicts roll back the entire operation, so no
orphan user remains. Emails are trimmed/lowercase; student numbers are unique.
Passwords are never echoed to templates, logs, cookies or documentation.
Passphrases accept 12 to 128 printable characters and use Werkzeug scrypt hashes.

Flask-Login uses a plain Python UserMixin object loaded with parameterized SQL;
there is no SQLAlchemy. Each request reloads the account role from PostgreSQL.
Club scope is checked against club_admins, including inside the write transaction
after locking the club. Removing an assignment takes effect on the next request.
The signed session holds the user ID and session metadata, not passwords, hashes,
or an authorization list. Login/logout clear the previous session. Persistent
remember-me login is disabled. Sessions expire after eight hours without rolling
refresh; HttpOnly and SameSite=Lax are enabled. APP_ENV=production enables Secure
cookies and HSTS and therefore requires HTTPS.

Every implemented unsafe HTTP action requires a session-bound, random CSRF token
with a one-hour lifetime. Logout is POST-only. Login accepts only safe root-relative
next URLs. Unauthenticated protected requests redirect to login; authenticated
users with the wrong role/scope get 403. CSRF, ownership and role checks are server
side; hiding a button is not the permission boundary. Security headers include
CSP, frame denial, content-type protection and no-store for dynamic responses.

## Roles and permissions

| Action | Anonymous | Student | Club admin | System admin |
| --- | --- | --- | --- | --- |
| Homepage, clubs, club details, venues | Yes | Yes | Yes | Yes |
| Public registration | Student accounts only | Redirect to dashboard | Redirect | Redirect |
| Student profile | No | Own only | No | Read through student directory |
| Edit student profile | No | Own name/department/batch | No | No |
| Student directory | No | No | No | Yes |
| Create club | No | No | No | Yes |
| Edit club details | No | No | Assigned clubs only | Any club |
| Activate/deactivate club | No | No | No | Yes |
| Assign/remove club admins | No | No | No | Yes |
| Join/leave, view own memberships | No | Yes | No | No |
| View/manage club memberships | No | No | Assigned clubs only | Any club |
| Create/edit venue | No | No | No | Yes |
| Create administrator accounts | Operator CLI only | Operator CLI only | Operator CLI only | Operator CLI only |

This preserves the reference role model. The requested assignment UI is an
extension: it can only assign an existing club_admin account, never promote a
public student account. Provision club_admin accounts through the trusted CLI.
The CLI is an operator boundary: anyone with shell access and write credentials
already has database authority; it is not a browser endpoint.

Student profile creation occurs during registration. Student email and number
are immutable in the UI, matching the reference. Account/profile deletion and
arbitrary role changes are intentionally unavailable. Clubs deactivate in place;
no club, student or venue delete endpoint exists. The Stage 2 assignment DELETE removes
an explicitly selected club_admins association; the account remains intact.

## SQL files executed by Flask

`app/sql.py` discovers fixed files under sql/queries once per process and parses
`-- name: namespace.statement` headers. Duplicate or empty named statements fail
loading; unknown names raise KeyError. Request input cannot choose a filesystem
path. Trusted handlers select constant query names and pass value tuples separately
to cursor.execute(statement, params). There is no untrusted SQL interpolation.
Restart the server after changing SQL files to clear the loader cache.

| File | Used for |
| --- | --- |
| 01_basic_selects.sql | Standalone teaching examples; never loaded/executed by Flask |
| 02_authentication.sql | Email/ID lookup, student account insert, admin insert and advisory bootstrap lock |
| 03_students.sql | Profile creation, joined lookup/directory and ownership-based updates |
| 04_clubs.sql | Directory/filter/detail, row lock, create/edit/status, scope and assignments |
| 05_memberships.sql | Own memberships, joined member lists, join/reactivation, leave/admin status |
| 06_venues.sql | Directory/detail/lock, create/edit and existing-event capacity guard |

Named runtime files contain psycopg `%s` placeholders. Do not run them directly in
psql. Representative JOINs in these files are used by profile, student-directory,
club-dashboard, administrator-assignment, membership and member-list pages.
User-supplied names, descriptions, IDs, search values and limits are always bound.
Search uses position(lower(parameter) in lower(column)) for literal matching;
percent signs and SQL-looking strings do not become wildcard patterns or commands.

Membership transitions lock the owning club until commit, serializing join/rejoin,
club status changes and scoped administration. ON CONFLICT reactivates the lifetime
(club_id,student_id) row, preserving membership_id and joined_at. Repeated joins
are idempotent. Leaving with no membership creates no row. Inactive clubs reject
joining and reactivation; leaving/cancellation remains allowed. Administrators
cannot change a membership belonging to another club through a forged ID.

Venue capacity must be an integer from 1 to 2147483647. Venue edits lock the row
and reject capacity below any existing non-cancelled event's capacity. This reads
existing events to preserve the reference safety rule. Stage 3 event writes use
compatible venue locking before checking venue capacity and inserting/updating.

## Existing nine-table schema

users has an optional one-to-one students profile. Students and clubs are linked
by club_memberships; users and clubs by club_admins. Events reference clubs and
venues; registrations reference events/students; event_expenses reference events.

Stage 1.5 created all nine tables and btree_gist after explicit approval. Stage 2
made **no schema changes**. Live metadata matches the Stage 1.5 snapshot exactly:
46 required columns, 9 PKs, 10 RESTRICT FKs, 19 CHECKs, 7 UNIQUE constraints,
unique email index, 13 ordinary indexes and venue GiST exclusion, totaling 31
indexes. The exclusion rejects overlapping non-cancelled venue bookings using
half-open time ranges. Detailed DDL remains in sql/schema and the historical
Stage 1 reports. **Do not recreate, reset, or reapply schema scripts to the
existing university_events_raw database.**

Positive capacities are database CHECKs. Stage 3 services now enforce cross-row
event/registration capacity rules inside explicit locking transactions. Every
writer must follow that protocol; arbitrary direct SQL can bypass cross-row
capacity checks. No invented columns, new tables, ORM objects or migration
records were added.

## Windows setup and launch

Use only this new project and its private .env. Never copy the reference .env.
The current configured .env and private session secret are already present.
For a fresh checkout, these commands preserve an existing .env and generate a
secret privately when needed:

```powershell
Set-Location 'D:\dbms_project_raw_sql'
# Run only if .venv is absent:
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.init_secret
# Edit this project's .env locally; do not paste credentials into chat.
# PGDATABASE must be university_events_raw.
.\.venv\Scripts\python.exe -m flask --app run:app db-check
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000/ and stop with Ctrl+C. The server is localhost-only and
debug is off. Activation or PowerShell policy changes are unnecessary. Keep
APP_ENV=development for local plain HTTP. Production requires HTTPS, a suitable
production WSGI deployment and deployment-level rate limiting. Do not publish
the development server. Bootstrap loads from a CDN; local styling remains usable
without network access.

PostgreSQL 18.6 tools are installed in C:\Program Files\PostgreSQL\18\bin.
If you need psql, add that directory to this session's PATH. No system PATH or
PostgreSQL service configuration was changed by Stage 2.

## Safely create administrators

The verification accounts were rolled back; there are no retained demo accounts
or shared default passwords. In a new terminal with the same project directory:

```powershell
.\.venv\Scripts\python.exe -m flask --app run:app create-admin
```

Enter full name, email and a private passphrase at the interactive prompts.
Password input and confirmation are hidden; there is no password flag and no
credential output. This creates the first system_admin atomically and refuses if
one already exists. An advisory transaction lock serializes simultaneous bootstrap
attempts. It does not update, replace or reset an existing administrator.

Create a separate club administrator account when needed:

```powershell
.\.venv\Scripts\python.exe -m flask --app run:app create-club-admin
```

This also uses hidden prompts, validation, hashing and atomic inserts. It does
not change existing student roles or assign clubs automatically. Log in as the
system administrator, open a club detail page and assign the new club-admin email.
You can remove that specific assignment without deleting its account.

## Demonstration

1. Start Flask and bootstrap your own system administrator through the CLI.
2. Log in as system admin; use the dashboard to create a club and venue. Edit both.
3. In another browser/session, register a student; log in and edit their profile.
4. Open a club, join, view Memberships, leave and rejoin. The same lifetime row and
   original joined timestamp are preserved.
5. Provision a club admin through the CLI; assign the email on the club detail page.
6. Log in as that club admin. Only assigned clubs can be edited and their members
   managed. System-only create/status/venue actions are unavailable.
7. As system admin, deactivate the club. Joining/reactivation fails, but leaving
   still works. Reactivate to reopen membership and remove assignments as needed.
8. Continue with the Stage 3 event demonstration below, then log out using the POST form.
   Continue with the Stage 4 expense/reporting demonstration below.

The real demo intentionally commits only records you create through these flows.
The automated tests and HTTP verifier below retain no fixture rows.

## Testing and evidence

Safe default suite without database integration:

```powershell
Set-Location 'D:\dbms_project_raw_sql'
Remove-Item Env:RUN_RAW_SQL_INTEGRATION -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest -q
```

The approved complete PostgreSQL suite and live HTTP verifier:

```powershell
$env:RUN_RAW_SQL_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.verify_stage2_http
Remove-Item Env:RUN_RAW_SQL_INTEGRATION
```

Stage 2 historical result: **91 passed, 0 failed, 0 skipped**. Stage 3 historical
full result: **140 passed, 0 failed, 0 skipped**, preserving all 91 earlier tests.
The additional 49 cases cover Stage 3 validation/workflows and four genuine
independent-connection race tests. The Stage 2 workflow fixture
uses one outer PostgreSQL transaction and a savepoint per application transaction;
it runs actual parameterized SQL and rolls everything back on teardown. Production
commit/rollback and cleanup are separately covered by transaction tests. The HTTP
verifier uses actual localhost requests and the same savepoint isolation model.
It stops its temporary server and verifies unchanged row counts. It is intended
for local verification without concurrent writers.

PostgreSQL SERIAL sequences can advance even when an INSERT rolls back. They were
not reset; gaps are expected. No table is dropped, truncated or cleared; no existing
record is erased. Final inspection found all nine tables still empty. Columns,
constraints and indexes exactly match the Stage 1.5 catalog snapshot.

Historical test results are summarized in this guide. Development-stage report
and validation artifacts were removed; source, SQL, tests and retained test XML
remain available.

Stage 5 has not started. No commit or push has been made.


## Stage 3 architecture and routes

| File | Responsibility |
| --- | --- |
| app/event_validation.py | Validates title, description, capacity, venue ID and timezone-aware times |
| app/event_services.py | Transactional event/registration/status/attendance rules and locking protocol |
| app/events.py | Event blueprint, scope enforcement, filters, histories, availability and campus-time formatting |
| sql/queries/07_events.sql | 13 named runtime event/filter/lock/overlap queries |
| sql/queries/08_registrations_attendance.sql | 7 named runtime registration/history/participant queries |
| sql/demonstrations/01_registration_locks.sql | Standalone SELECT/lock walkthrough ending in ROLLBACK |
| app/templates/events/ | Directory, form, detail, histories, attendance, availability and filter/pagination macros |
| tests/test_stage3_validation.py | 23 validation/error/security cases |
| tests/test_stage3_integration.py | 22 rollback-isolated PostgreSQL event/registration/attendance cases |
| tests/test_stage3_concurrency.py | 4 actual independent-connection contention cases with exact cleanup |
| scripts/verify_stage3_http.py | Repeatable local HTTP verification, fixture rollback and final row-count check |

GET /events is public. It supports q, status=all/scheduled/completed/cancelled,
when=upcoming/past/all, club_id, venue_id, from_date, to_date and page. Date bounds
use Asia/Dhaka calendar days; the end date is inclusive. Sort is start_time then
event_id and pages contain 20 rows. GET /events/<event_id> is public.

| Action | Permission |
| --- | --- |
| /events/manage | Club admins see assigned-club events; system admins see all |
| /clubs/<club_id>/events and /clubs/<club_id>/events/new | Assigned club admin or system admin |
| /events/<event_id>/edit (GET/POST) | Manager of the event's actual club |
| /events/<event_id>/status (POST) | Manager; target cancelled or completed only |
| /events/<event_id>/register (POST) | Student, own profile only |
| /events/<event_id>/registration/cancel (POST) | Student, own registration only |
| /registrations | Student's own registration and attendance history; q/status/page filters |
| /events/<event_id>/participants | Event's club manager only; q/status/page filters |
| /events/<event_id>/participants/<registration_id>/status (POST) | Event's club manager; registration must belong to that event |
| /venues/<venue_id>/availability | Public advisory interval availability form/results |

Every mutation inherits Stage 2 CSRF protection. Administrator event scope is
rechecked inside the write transaction. Submitted club ownership/status/owner IDs
cannot transfer an event or a student's participation. There is no event delete
endpoint. Cancellation preserves registrations and expenses; no records cascade.

## Event and attendance business rules

Events retain the existing fields: event_id, club_id, venue_id, title,
description, start_time, end_time, capacity and status. Status is scheduled,
completed or cancelled. New events are scheduled. Event ownership cannot change.
Creation/editing requires an active club, a future start, end after start,
positive capacity no greater than venue capacity, and an available venue. Only
upcoming scheduled events are editable. Capacity cannot shrink below the count
of registered plus attended participants. Cancelled/completed statuses are final;
repeating the same final status is idempotent. Completion requires the event to
have ended. Cancelling a scheduled event is allowed before or after it starts.

A student need not be a club member to register. Registration requires an
upcoming scheduled event and active organizing club. The deadline is start_time,
evaluated after acquiring the Event lock. A duplicate request for an already
registered/attended student is idempotent while eligibility remains open.
Reactivation updates the cancelled lifetime (event_id,student_id) row, preserving
registration_id and registered_at. Both registered and attended consume seats;
cancelled does not. A full event rejects new/reactivated registrations.

Students may cancel registered participation before the event starts. If the
event itself is cancelled, cancellation remains available after its start.
Attended participation and completed-event participation cannot be cancelled.
Leaving an absent/already cancelled registration is idempotent and creates no row.
Attendance opens when the event starts, including for completed events. Managers
may mark attended or correct back to registered; both still occupy one seat.
Cancelled registrations/events cannot be marked for attendance. Students see
attended rows by selecting status=attended in their own history.

Browser datetime-local inputs mean Asia/Dhaka. Explicit ISO offsets are accepted
by validation and normalized to UTC instants. PostgreSQL stores TIMESTAMP WITH
TIME ZONE; all displayed event times convert to Asia/Dhaka. No extra deadline,
attendance flag, or history column was invented.

## Registration transaction and SELECT FOR UPDATE

The caller opens one explicit read/write transaction. The service never commits
partway through an operation. The global application lock order is:

1. Club FOR SHARE. This allows registrations for the same club concurrently but
   blocks deactivation and assignment removal while permissions/eligibility matter.
2. Venue rows FOR UPDATE in ascending venue_id order for scheduling operations.
   Edits lock both the old and chosen venue before locking the Event.
3. Event FOR UPDATE. This is the shared serialization point for seat allocation,
   cancellation, attendance, status changes and event capacity edits.
4. The specific Registration FOR UPDATE, when a lifetime row exists.

Registration omits Venue locks. After the Event lock is acquired, the service
checks current status/time/club eligibility, loads the student's existing row,
counts occupied seats, and inserts or reactivates only if capacity permits.
The read-only preview used to find immutable club ownership does not determine
capacity or deadline decisions; those use the newly locked Event row. An edit
that discovers another request moved the event to an unanticipated venue returns
409 instead of taking a new Venue lock out of order.

At PostgreSQL's READ COMMITTED isolation, a waiting registration acquires the lock
after the winner commits, then its next SELECT sees that committed registration.
The capacity count and insert are therefore protected by one serialization lock,
rather than an unprotected count-then-insert. The existing UNIQUE(event_id,
student_id) constraint is a final duplicate guard. Exceptions roll back the whole
operation; a success commits once. Deadlock/serialization/lock-unavailable errors
return a safe 409 suggesting reload; no blind retry can double-submit an action.

All event/registration writers must follow this protocol. The schema alone does
not enforce aggregate capacities against arbitrary external SQL writers.

## Venue overlap and availability

Venue row locking serializes cooperating schedulers. The overlap query uses
existing.start_time < proposed.end_time AND existing.end_time > proposed.start_time,
excludes the edited event itself, and ignores cancelled bookings. Half-open
[start,end) intervals permit adjacent events. Completed bookings retain historical
venue occupancy.

PostgreSQL's unchanged ex_events_venue_time GiST exclusion combines venue_id
WITH = and tstzrange(start_time,end_time,'[)') WITH && WHERE status<>'cancelled'.
btree_gist supplies integer equality. The constraint also rejects overlapping
direct/concurrent writers that bypass application locks. SQLSTATE 23P01 is mapped
to a friendly scheduling-conflict response after rollback. /venues/<id>/availability
is an advisory check only; save always repeats capacity/overlap checks under locks.

## SQL walkthrough and DBMS viva demonstration

1. Log in as your own system admin or an assigned club admin. Open a club detail
   page and choose Create event. Pick a venue, future start/end and capacity.
2. Create an adjacent event: it succeeds. Try an overlapping booking: it returns
   a friendly conflict. View venue availability from the venue directory.
3. In a separate browser, log in as a student and register. Open My registrations,
   cancel and reactivate. Compare registration_id/registered_at: both are preserved.
4. Fill the event; another student is rejected. Try shrinking event capacity below
   occupied seats; it is rejected. Attended still counts as occupied.
5. Once a real event starts, its club manager can open Participants and attendance,
   mark attendance or correct it. The student history shows attended participation.
   Once it ends, the manager can complete the event. Cancellation is also available
   for a scheduled event; historical participation remains intact.
6. Show events.club_share, events.lock, registrations.lock and events.occupied in
   the runtime SQL files alongside register_student in app/event_services.py.
   Show the exclusion constraint using sql/demo/05_live_catalog_read_only.sql.

An optional SELECT-only locking walkthrough for YOUR OWN existing demo IDs:

```powershell
$env:Path = 'C:\Program Files\PostgreSQL\18\bin;' + $env:Path
# Replace 123/456 with your event/student IDs. Password is prompted privately.
psql -X -W -h localhost -U postgres -d university_events_raw -v event_id=123 -v student_id=456 -f sql/demonstrations/01_registration_locks.sql
```

The demonstration is separate from runtime SQL, contains no named loader headers,
checks the database name, takes SELECT locks, and always ROLLBACKs. It never
inserts/cancels registrations. The actual application uses the 20 named statements
in 07_events.sql and 08_registrations_attendance.sql through bound psycopg calls.

## Stage 3 verification and Windows commands

Launch commands remain:

```powershell
Set-Location 'D:\dbms_project_raw_sql'
.\.venv\Scripts\python.exe -m flask --app run:app db-check
.\.venv\Scripts\python.exe run.py
```

Complete approved test suite (including committed disposable concurrency fixtures):

```powershell
$env:RUN_RAW_SQL_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=STAGE3_TEST_RESULTS.xml
.\.venv\Scripts\python.exe -m pytest -q -m concurrency
.\.venv\Scripts\python.exe -m scripts.verify_stage3_http
Remove-Item Env:RUN_RAW_SQL_INTEGRATION
```

Stage 3 historical full run: **140 passed, 0 failed, 0 skipped** in 40.55 seconds. This includes
all 91 unchanged earlier tests, 23 new offline cases, 22 rollback-isolated workflow
cases and 4 true concurrency cases. The race tests use independent PostgreSQL
connections and real commits. They deliberately hold a blocker row lock and
observe worker PIDs in pg_stat_activity waiting on locks before release. Outcomes:

- Two students race for one seat: one success, one full rejection, one occupied row.
- Same student submits concurrently: both requests succeed idempotently, one row.
- Two clubs book one venue interval: one success, one scheduling conflict.
- A direct concurrent writer bypasses application checks: PostgreSQL exclusion
  blocks/rejects it with a friendly mapped conflict after the winner commits.

Concurrency tests use unique explicit-ID/UUID fixtures and delete only their own
children/parents in FK-safe order. They do not erase existing user data or reset
sequences. Run locally without parallel pytest workers or unrelated writers when
comparing whole-database row counts. Stage 1/2 isolated tests and the HTTP verifier
continue to roll back outer transactions. SERIAL counters may advance, as expected.

Actual HTTP checks passed for event create/edit/filter/detail, availability,
registration/cancellation/reactivation, scoped attendance/correction, student
history, event completion/cancellation and all baseline flows. The verifier advances
only its fixture service clock for attendance/completion, then restores it; it
never waits days or rewrites existing event times. The temporary server is stopped.
Final metadata exactly matches Stage 1.5, and all nine tables remain empty.
No original project/database access occurred during those tests. No commit/push
was performed. Historical Stage 3 details are preserved in this guide;
current Stage 4 verification is described below.


## Stage 4 expense and reporting architecture

| Source | Responsibility |
| --- | --- |
| app/report_validation.py | Exact NUMERIC(12,2) amount, description and canonical-date validation |
| app/report_queries.py | Role-scoped report APIs, date semantics and trusted named query execution |
| app/reports.py | Expense CRUD/confirmation, reporting dashboard, filters, financial/participation pages and exports |
| app/csv_export.py | UTF-8 CSV, exact numeric output, quoting and formula-prefix neutralization |
| sql/queries/09_expenses.sql | Seven actual expense CRUD/filter/total statements |
| sql/queries/10_financial_reports.sql | Six actual event/club/month/top/summary/missing-entry report statements |
| sql/queries/11_participation_reports.sql | Six actual event/club/month/status/popular/weighted-summary statements |
| sql/queries/12_reporting_choices.sql | Scoped filter choices and the student's own participation summary |
| sql/reports/01_create_reporting_views.sql | Proposed three normal views; NOT applied |
| sql/reports/02_pgadmin_examples.sql | Executable standalone read-only advanced SQL examples |
| app/templates/reports/ | Dashboard, expense forms/confirmation/list, financial/participation tables and shared filters |
| tests/test_stage4_validation.py | 47 offline amount/date/CSV/access/isolation cases |
| tests/test_stage4_integration.py | 26 database cases, including one pending-view deployment check |
| scripts/verify_stage4_http.py | Actual localhost expense/report/CSV workflows with fixture rollback |

All 22 new runtime statements use the existing trusted SQL loader. SQL text and
query names come from source files/constants; amounts, descriptions, dates and IDs
are bound separately. The report folder's view/demo files have no loader headers
and are never automatically executed. CSV uses the SAME scoped event queries as
HTML, preventing differences in authorization or filter behavior.

Expense mutations use one write transaction and lock Club FOR SHARE -> Event
FOR UPDATE -> Expense FOR UPDATE when editing/deleting. Club scope is rechecked
inside that transaction, so assignment removal cannot race a financial write.
The existing nine-table schema is reused without adding categories, currency,
revenue, budget, ticket, sponsorship or profit fields.

## Expenses and permissions

EventExpense remains expense_id, event_id, description VARCHAR(255), amount
NUMERIC(12,2), expense_date DATE. Currency is assumed BDT, matching the reference.
Amounts stay Decimal/PostgreSQL numeric throughout; there is no float conversion.
Accepted amounts are 0.00 through 9999999999.99, with at most two decimal places.
Negative/scientific/comma/NaN/Infinity/overprecision/overflow values are rejected.
Descriptions are nonblank and at most 255 characters. Expense dates are canonical
YYYY-MM-DD; future/backdated entries are permitted because the reference imposes
no event-time restriction. Cancelled/completed events and inactive clubs retain
legitimate incurred costs and can still have authorized expense accounting.

| Route/action | Allowed users |
| --- | --- |
| /events/<event_id>/expenses | System admin, or club admin assigned to the event's club |
| /events/<event_id>/expenses/new (GET/POST) | Same scope |
| /events/<event_id>/expenses/<expense_id>/edit (GET/POST) | Same scope; expense must belong to that event |
| /events/<event_id>/expenses/<expense_id>/delete (GET/POST) | Same scope; GET confirmation only, POST requires confirm=delete and CSRF |
| /reports, /reports/financial, /reports/analytics | System admin globally; club admin only assigned clubs |
| /clubs/<club_id>/financial | Authorized club manager; redirects to scoped club finances |
| /reports/financial.csv, /reports/participation.csv | Same role/scope and filters as HTML reports |

Students cannot access expense, aggregate financial/participation report or export
routes. They retain their OWN history/attendance and gain only their own dashboard
participation summary. Anonymous requests redirect to login. Wrong roles/scopes
return 403; mismatched event/club filters return 400. Every expense identifier is
scoped to the URL event; forged related IDs return 404. Submitted event/owner/category
fields are ignored. Only the specifically confirmed expense is deleted; event,
registrations, club and all other expenses remain intact. GET never deletes.

## Financial aggregates and SQL walkthrough

The financial page includes event totals/counts and per-entry AVG/MIN/MAX, club
totals including zero-event clubs, monthly expense totals, the top five positive
spenders, and events without expense entries in the selected date range.
Filters: from_date, to_date, club_id, event_id. Dates are inclusive expense_date
bounds, NOT event start dates. Selected events still show zero if no expense matches.
Cancelled-event costs still count. Date filters are canonical, ordered, and before
year 9999. The expense list additionally supports literal description q search;
its total matches both the date and text filters, including rows on other pages.

The SQL first builds scoped_clubs using EXISTS against club_admins, then
scoped_events using INNER JOIN. Expense rows are grouped by event_id with COUNT,
SUM, AVG, MIN and MAX before LEFT JOIN to events. COALESCE supplies exact zero
counts/totals for empty children. Club totals aggregate those one-row-per-event
results rather than joining ungrouped registrations and expenses together.
Three registrations plus two expenses of 10.10 and 20.20 must still total 30.30,
not 90.90. That regression is tested on PostgreSQL.

Highest positive spend uses GROUP BY ... HAVING SUM(amount)>0, ORDER BY and
LIMIT 5. NOT EXISTS identifies events missing expense records in the range.
Monthly totals group actual expense dates; no fake months or category fields are
invented. Shared CTEs make scope/date rules explicit. Each financial/analytics
report runs its component SELECTs in one read-only REPEATABLE READ transaction,
so tables/cards within that report share a consistent snapshot. Writes remain
READ COMMITTED and the four real Stage 3 concurrency tests still pass.

## Participation metrics

Participation date filters apply to event start in Asia/Dhaka with half-open UTC
boundaries [local midnight, midnight after the final day]. Monthly grouping uses
start_time AT TIME ZONE 'Asia/Dhaka', including UTC month-boundary events. Metrics
count the registration rows belonging to those events, not registrations created
in the date range. Registration children are preaggregated before joining events,
so expense rows cannot multiply attendance counts.

| Metric | Definition |
| --- | --- |
| Total registrations | All lifetime rows, including cancelled |
| Active registrations | Registration.status = registered; excludes attended |
| Attended / cancelled | Count of the corresponding status |
| Occupied | registered + attended; counts participation rows, not distinct students across events |
| Event occupancy | 100 * occupied / capacity, rounded to one decimal |
| Event attendance rate | 100 * attended / occupied, only for completed events and nonzero denominator |
| Overall completed attendance | Sum(attended for completed events) / sum(occupied for completed events), never a mean of percentages |
| Popular events | Top five by all lifetime registration rows, ties by event_id |
| Club activity | Event counts and summed registration/occupied/attended rows |
| Student summary | Only that student's registered/attended/cancelled/upcoming/past participation |

The report includes event statistics by status, monthly events and club activity.
CASE expressions implement status counts; NULLIF/CASE avoid dividing by zero.
Undefined or not-yet-applicable attendance is N/A, not a misleading zero.
A weighted 2 attended / 5 occupied across completed events is 40.0%, verified by
tests. Cancelled-event occupancy describes retained historical records, not an
available registration offer.

## CSV exports

Apply filters on the financial or participation page, then choose its download
button. CSV exports ALL matching event rows regardless of HTML page selection.
Financial columns: event_id, event_title, club_id, club_name, expense_count,
total_expenses_bdt. Participation columns: event_id, title, club_id, club_name,
status, capacity, total_registrations, active_registrations, attended,
cancelled_registrations, occupied, occupancy_pct, attendance_rate.

Downloads use fixed filenames, text/csv; charset=utf-8, CRLF lines, QUOTE_ALL and
no-store. Decimal values are emitted exactly; unavailable rates are empty. Text
formula prefixes (=, +, -, @ and full-width forms), including ones hidden behind
whitespace/BOM, receive an apostrophe. Commas/quotes/newlines remain correctly
quoted. Exported event aggregates contain no student names, emails, numbers or IDs.
Scope/filter checks are identical to HTML, including rejecting forged club/event
filters. Spreadsheet import should explicitly use UTF-8 and preserve text cells.

## Proposed normal views - PENDING, NOT DEPLOYED

The user explicitly chose to keep all persistent views pending. No CREATE VIEW,
CREATE OR REPLACE, DROP or other schema change has been executed in Stage 4.
The application does not depend on their existence.

| Proposed view | Dependencies and purpose |
| --- | --- |
| stage4_event_participation_summary | events + registrations; counts, occupied seats and attendance/occupancy percentages |
| stage4_event_financial_summary | events + event_expenses; exact expense totals/counts/average/min/max including zero-expense events |
| stage4_club_activity_summary | clubs + the two preceding views; one club row combining independently aggregated participation and finance |

Definitions are in sql/reports/01_create_reporting_views.sql. They are ordinary
views with current results, not materialized copies. They contain no student PII.
They are aggregate relations, not authorization boundaries; any future application
use must still apply role scope and appropriate filters. No public grants are added.
A future deployment needs fresh explicit approval; plain CREATE VIEW will fail on
name conflicts and the transaction rolls back rather than replacing objects.

Tests EXPLAIN and execute the base SELECT definitions without creating views.
The club view is expanded through query-local CTEs for dependency validation; its
real expense/participation totals are also checked. Live catalog inspection confirms
all three view names are absent. One persistent-view verification test skips for
that explicit reason. The nine base tables/columns/constraints/indexes remain
identical to the Stage 1.5 snapshot.

## pgAdmin / advanced SQL and DBMS viva

1. In pgAdmin choose university_events_raw, open Query Tool and load
   sql/reports/02_pgadmin_examples.sql. Run the file. It guards the database name
   and runs SELECTs inside BEGIN READ ONLY / COMMIT. It creates no objects.
2. Walk through its INNER/multi-table JOIN, expense LEFT JOIN, separate child CTEs,
   correlated seat-count subquery, EXISTS/NOT EXISTS, HAVING, CASE, COALESCE,
   COUNT/SUM/AVG/MIN/MAX, GROUP BY and ORDER BY/LIMIT examples.
3. Show the matching named runtime queries in sql/queries/09 through 12 and their
   execution via app/report_queries.py and app/reports.py. Runtime %s placeholders
   are psycopg bindings; they are not literal pgAdmin syntax.
4. Log in as your own admin, open an event and choose Expenses and financial summary.
   Add two expenses (10.10 and 20.20), edit one, open deletion confirmation and
   confirm only when desired. Demonstrate CSRF/confirmation and scope protections.
5. Open Reporting dashboard; compare event/club totals and monthly expenditure.
   Set a range by expense_date, then compare participation's event-date behavior.
6. Show an event with several registrations and expenses: totals must not multiply.
   Demonstrate empty event/club rows, occupancy and completed weighted attendance.
7. Download both CSVs and show stable headings, exact values and absence of student
   identities. Log in as an unassigned club admin/student and show denied access.
8. Review the proposed view definitions as SQL only. Do not apply them until the
   user explicitly approves. The ordinary SELECT reports already work.

The standalone read-only examples were actually executed successfully through
psql; output is STAGE4_SQL_DEMO_OUTPUT.txt. Using pgAdmin's query UI is a manual
follow-up, not claimed as an automated GUI action. These database examples use the
operator's DB privileges; browser role permissions belong to the Flask app.

## Stage 4 Windows launch and verification

```powershell
Set-Location 'D:\dbms_project_raw_sql'
.\.venv\Scripts\python.exe -m flask --app run:app db-check
.\.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:5000/. Manager reports are at /reports. Create your own initial
admin using the previously documented hidden-prompt create-admin CLI if needed;
verification accounts were rolled back. No shared passwords are provided.

```powershell
$env:RUN_RAW_SQL_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest -q --junitxml=STAGE4_TEST_RESULTS.xml
.\.venv\Scripts\python.exe -m scripts.verify_stage4_http
Remove-Item Env:RUN_RAW_SQL_INTEGRATION
```

Final complete suite: **212 passed, 0 failed, 1 skipped in 99.73 seconds**.
All 140 earlier tests are unchanged/passing, including all four concurrency cases.
The new 73 cases comprise 47 offline and 26 database cases. The one skipped case
is undeployed persistent-view verification, not an untested ordinary report.
All expense/report fixtures roll back; only the existing race tests temporarily
commit/clean their own records. SERIAL gaps are expected and never reset.

Actual localhost HTTP verification passed expense create/edit/delete confirmation,
financial/participation pages, scoped CSVs, student denial and earlier workflows.
The temporary server is stopped. db-check passed. All nine base tables are empty
with no retained fixture records. Views remain absent by user choice. Detailed
retained test evidence: STAGE4_TEST_RESULTS.xml; verification commands are documented above.

Reports materialize grouped event rows before 10-row HTML pagination and CSV
creation, matching the local reference design; large datasets would need SQL
pagination/streaming. Expense lists use 20-row SQL pages. CSV contains all filtered
events. No categories/revenue/profit or materialized views were invented. The prior
production HTTPS/server/rate-limiting limitations remain. No original project or
database modification, commit/push, or Stage 5 work was performed.


Default Stage 4 offline mode was also verified: **130 passed, 0 failed, 83 skipped
in 5.19 seconds**. These skips are the explicitly gated database tests. Production
report helpers were additionally run through real read-only REPEATABLE READ
connections (outside the test savepoint adapter) and returned correct empty-data
results. btree_gist metadata also matches the historical snapshot.
