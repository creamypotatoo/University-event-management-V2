# Reporting-view deployment plan - APPLIED WITH APPROVAL

SQL: sql/reports/01_create_reporting_views.sql. The user explicitly approved all
three normal views in Stage 5. Collision checks passed and the guarded creation
transaction succeeded. Definitions are retained in the SQL script and verified by
tests/test_stage4_integration.py. No base table changed.
The earlier pending choice was superseded by explicit approval; do not rerun CREATE
on the existing views. The app retains ordinary SELECT reports independently.

Proposed objects, all normal/non-materialized views:

1. public.stage4_event_participation_summary: events + registrations.
2. public.stage4_event_financial_summary: events + event_expenses.
3. public.stage4_club_activity_summary: clubs + the two preceding views.

They aggregate event/club data, with no student identities or credentials. They
are not row-level authorization boundaries. The application must continue applying
club-admin scope and report filters. No public grants are proposed.

Before any approved deployment, read-only checks must confirm all three names are
absent in pg_class (all relation kinds, not just pg_views), and the database is
university_events_raw. Stop on any name collision; do not replace/drop anything.
The reviewed script uses plain CREATE VIEW in a transaction, never OR REPLACE.
Dependency order is participation, financial, club activity. A failure rolls the
whole creation transaction back.

Actual base SELECTs have already been EXPLAINed/executed against isolated records.
Stage 5 additionally tests TEMPORARY copies against exact temporary copies of the
nine-table schema. These temporary objects disappear on rollback/connection close
and do not deploy persistent views or change the live base schema.

Only AFTER fresh explicit approval, use the configured NEW database credentials:

```powershell
Set-Location 'D:\dbms_project_raw_sql'
$env:Path = 'C:\Program Files\PostgreSQL\18\bin;' + $env:Path
# Match host/port/user to the new project's .env; never embed a password.
psql -X -W -h localhost -p 5432 -U postgres -d university_events_raw -v ON_ERROR_STOP=1 -f sql/reports/01_create_reporting_views.sql
```

Verify pg_views definitions and equality to ordinary SELECT report totals using
isolated test data. The pending-view integration check will run when all three
persistent objects exist. Preserve all nine base tables/constraints/indexes.
No automatic deploy-on-startup, migration, materialized view or data copy occurs.
