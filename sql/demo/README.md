# Safe SQL laboratory demonstrations

Run 01 through 05 in numeric order. EACH file is standalone and guards the
university_events_raw database name. All work is either read-only metadata or
TEMPORARY copies with explicit pg_temp references. No public rows are inserted,
updated or deleted. No original database access, seed, reset or persistent view
creation occurs. Demos need the already-installed btree_gist extension.

01: Exact nine-table DDL adapted only to TEMP and temporary FKs, all indexes and
venue exclusion; six expected constraint rejections print PASS notices. Ends ROLLBACK.
02: Temporary INSERT/SELECT/UPDATE/DELETE, WHERE/ORDER BY/LIMIT, savepoint rollback,
COMMIT and full transaction ROLLBACK. Expected expense counts 2 after DELETE and
3 after ROLLBACK TO; temporary tables/probe removed both return true.
03: INNER/LEFT/multi-table JOINs, correlated subqueries, COUNT/SUM/AVG/MIN/MAX,
GROUP BY/HAVING, CTE/CASE/COALESCE/EXISTS/NOT EXISTS and three TEMP reporting views.
Expected workshop total 30.30, 2 occupied/2 capacity, occupancy 100.0, attendance
50.0%; upcoming event has zero totals. Ends ROLLBACK, removing temporary views.
04: Club shared/Event exclusive/Registration locks on temporary copies and lock
catalog inspection. Ends ROLLBACK. Cross-session contention is verified by the
four real concurrency tests, because separate sessions cannot share temp tables.
05: Read-only actual nine-table constraint/index/view/extension catalog inspection.

PowerShell (match host/port/user to your NEW project configuration):

```powershell
Set-Location 'D:\dbms_project_raw_sql'
$env:Path = 'C:\Program Files\PostgreSQL\18\bin;' + $env:Path
psql -X -W -h localhost -p 5432 -U postgres -d university_events_raw -v ON_ERROR_STOP=1 -f sql/demo/01_schema_constraints_indexes.sql
# Repeat with 02_crud_transactions.sql, 03_joins_aggregates_temp_views.sql,
# 04_row_locks.sql, then 05_live_catalog_read_only.sql.
```

Each complete file also works in pgAdmin Query Tool on university_events_raw.
Never select the original university_events database. If an example errors in
pgAdmin, ROLLBACK that session before rerunning. No DROP of live objects is needed.

These files are EDUCATIONAL, never loaded by Flask. The actual site uses named
parameterized statements in sql/queries, service transactions in app/db.py and
app/event_services.py, and approved normal reporting views in sql/reports.
