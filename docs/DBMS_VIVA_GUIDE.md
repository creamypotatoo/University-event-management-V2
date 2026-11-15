# DBMS viva guide - PostgreSQL raw SQL project

All demo identities are fictional. Use university_events_raw only. No original
project/database operation is needed. Never show .env, passwords, cookies or the
private ownership manifest on a projector or in submission files.

## Five-minute demonstration

| Time | Demonstration and explanation |
| --- | --- |
| 0:00-0:35 | Homepage, clubs and upcoming events; explain three roles and nine normalized tables. Styling works offline. |
| 0:35-1:15 | Fictional student login with your private passphrase; profile, memberships and own registrations. Explain lifetime cancellation/reactivation. |
| 1:15-2:00 | Seeded club-admin login; assigned clubs, events and completed-event participants. Explain server-side scope and registration/attendance statuses. |
| 2:00-2:50 | Workshop expenses: 10.10+20.20=30.30. Show edit/delete confirmation WITHOUT deleting existing data. Explain NUMERIC and filtered totals. |
| 2:50-3:35 | Finance/participation reports and CSV: initial total 1205.80, completed attendance 2/3=66.7%, no student identities in export. |
| 3:35-4:20 | sql/demo/03 output: JOIN/GROUP BY/HAVING and TEMP views. Explain approved normal live views versus temporary teaching copies. |
| 4:20-5:00 | SELECT FOR UPDATE code, four passing contention tests, last-seat winner, exclusion, parameter binding and ACID. |

Prefer TEMP files for CRUD practice; existing records must not be deleted.
Manual UI changes should affect only explicitly intended fictional data.

## Why Flask, psycopg and raw SQL?

Flask supplies routes, templates, sessions and CLI without requiring a data layer.
psycopg 3 speaks PostgreSQL, binds parameters, returns dictionary rows and supports
explicit transactions. Raw SQL exposes the joins, constraints, locks and aggregates
for DBMS teaching. Flask-Login is a session helper, not an ORM.

## All nine tables

| Table | Meaning |
| --- | --- |
| users | Account identity, normalized unique email, salted password hash and role |
| students | Optional one-to-one profile; unique student number, department and batch |
| clubs | Club details and active flag; deactivation preserves relationships |
| club_memberships | Student/club association, joined time and lifetime membership status |
| club_admins | User/club assignments defining club-specific administrative authority |
| venues | Space name, location and positive capacity |
| events | Club/venue, title, timezone-aware start/end, capacity and status |
| registrations | Event/student lifetime association, time and attendance status |
| event_expenses | Exact expense amount, description and date for one event |

PK: events.event_id uniquely identifies one event. FK: registrations.event_id
references events.event_id with ON DELETE RESTRICT. UNIQUE(event_id,student_id)
prevents a second lifetime row, including after cancellation. CHECK(capacity>0)
prevents nonpositive capacities. All columns are required. Derived totals are
computed instead of redundantly stored.

## Actual JOIN / GROUP BY / HAVING examples

```sql
SELECT e.title,c.club_name,v.venue_name
FROM public.events e
JOIN public.clubs c ON c.club_id=e.club_id
JOIN public.venues v ON v.venue_id=e.venue_id
ORDER BY e.start_time,e.event_id;

SELECT c.club_id,c.club_name,SUM(x.amount) AS total_expenses
FROM public.clubs c
JOIN public.events e ON e.club_id=c.club_id
JOIN public.event_expenses x ON x.event_id=e.event_id
GROUP BY c.club_id,c.club_name
HAVING SUM(x.amount)>0
ORDER BY total_expenses DESC,c.club_id LIMIT 5;
```

Actual finance SQL first groups expenses by event_id, then LEFT JOINs the one-row
rollup to events. Registration children are separately grouped. Otherwise two
expenses x three registrations becomes six joined rows and multiplies money.
CASE counts statuses; COALESCE supplies zero; NULLIF protects denominators;
NOT EXISTS finds events without expense records. CTEs organize permission scope,
event selection and independent child aggregation.

## Views and indexes

Approved normal views summarize event participation, event finance and club
activity. They store query definitions, not copied rows. The club view depends
on the two event views. They contain no student identities or PUBLIC SELECT grants,
but do not replace application authorization. Ordinary SELECT reports stay usable.

31 indexes include PK/UNIQUE-backed, unique email, FK-leading/composite and venue
GiST indexes. Email uniqueness supports login and duplicate prevention. btree_gist
supplies integer equality for the venue exclusion. Indexes cost storage/write
maintenance; a planner may prefer sequential scans for small tables.

## ACID, isolation, locking and venue overlap

Atomicity: user and student profile creation commits/rolls back together.
Consistency: database constraints plus service rules preserve invariants.
Isolation: the Event row lock serializes competing seat decisions.
Durability: PostgreSQL commit/WAL supplies persistence subject to durability settings.

Registration uses one READ COMMITTED transaction: Club FOR SHARE -> Event FOR UPDATE
-> existing Registration FOR UPDATE -> eligibility/deadline/count -> insert or
reactivate -> commit. Time is evaluated AFTER waiting for the Event lock. A waiter's
next SELECT sees the winner's committed seat. Venue edits lock IDs in ascending
order before the Event. Reports use read-only REPEATABLE READ snapshots.

The partial GiST exclusion combines equal venue_id with overlapping
tstzrange(start_time,end_time,'[)'), WHERE status<>'cancelled'. Half-open intervals
permit adjacent bookings. Completed bookings remain protected; cancelled events
release the venue. Exclusion catches direct writers bypassing app checks. Aggregate
capacity still requires service locks, not a simple row CHECK.

## Authentication, authorization, injection and CSRF

Authentication checks identity with scrypt and signed sessions. Authorization checks
role, owner and club assignment. Hidden buttons alone do not enforce permissions.
Public registration always creates students. CSRF validates a random expiring
session token for unsafe methods. Jinja escapes HTML; CSV neutralizes formulas.
Cursor.execute(statement, params) separates values from SQL grammar. Fixed query
names and identifier whitelists prevent request-driven SQL text/path construction.

## Thirty likely questions with answers

1. **Why separate users and students?** Identity/credentials differ from optional
   student attributes; administrators need not have a student profile.
2. **How is one-to-one represented?** students.user_id is an FK and UNIQUE.
3. **How is many-to-many represented?** Explicit memberships, registrations and
   admin assignment tables with unique parent pairs and association attributes.
4. **What is a primary key?** A unique non-null row identifier; each table has one.
5. **What is referential integrity?** FKs require referenced parents to exist.
6. **Why ON DELETE RESTRICT?** Parent deletion cannot silently erase history;
   cancellation/deactivation preserves relationships instead.
7. **What does UNIQUE(event_id,student_id) ensure?** One lifetime registration,
   even after cancellation; reactivation changes the same row.
8. **What normalization is used?** Entity attributes stay with their entity;
   names/venue details/totals are not duplicated in participation rows.
9. **INNER versus LEFT JOIN?** INNER requires a matching row; LEFT preserves
   left rows with null children, useful for zero-expense events.
10. **WHERE versus HAVING?** WHERE filters input rows; HAVING filters grouped
    results, e.g. SUM(amount)>0.
11. **Why can joins inflate totals?** Multiple one-to-many children form combinations;
    aggregate each independently before joining rollups.
12. **Why COALESCE?** Empty SUM is null; reports need exact zero totals/counts.
13. **COUNT(*) versus COUNT(column)?** COUNT(*) counts rows; COUNT(column) ignores
    null values, especially relevant after LEFT JOIN.
14. **Why NUMERIC/Decimal instead of float?** Exact decimal arithmetic preserves
    cents without binary floating approximation.
15. **What does NUMERIC(12,2) mean?** Twelve total digits with two decimal places;
    app bounds are nonnegative up to 9999999999.99.
16. **What is a CTE?** A named WITH subquery organizing a query, not automatically
    a persistent table or view.
17. **What is correlated SQL?** It refers to the current outer row, e.g. NOT EXISTS
    expense WHERE expense.event_id=event.event_id.
18. **What is a normal view?** A stored SELECT definition evaluated against current
    base data, unlike a materialized stored result.
19. **Does a view automatically secure finances?** No. Grants and scope checks
    still apply; these views have no public SELECT grants.
20. **What is an index tradeoff?** Suitable lookups/joins can be faster, but indexes
    require storage and write maintenance; the planner chooses their use.
21. **Why SELECT FOR UPDATE?** It blocks competing row writers/lockers until the
    transaction ends, serializing seats on the same Event.
22. **Why not unprotected count-then-insert?** Two requests may both see room and
    overbook; the Event lock protects both statements in one transaction.
23. **Why READ COMMITTED for registrations?** After waiting, the next statement
    sees the winner's committed row rather than a stale transaction snapshot.
24. **Why REPEATABLE READ for reports?** Multiple sections use a stable snapshot.
25. **What is deadlock and how is risk reduced?** A cycle of waiting transactions;
    consistent Club/Venue/Event/child order reduces cycles, and failures roll back.
26. **How does venue exclusion work?** Equal-venue overlapping half-open timezone
    ranges are rejected, except cancelled events.
27. **Why SERIAL gaps after rollback?** nextval is nontransactional; IDs are not
    gap-free row counters and sequences must not be reset.
28. **How is SQL injection prevented?** Bound parameters, fixed trusted names,
    whitelisted identifiers and validation; no request interpolation.
29. **Why CSRF with secure login?** Browsers automatically send cookies; a
    session-bound token prevents cross-site forged state-changing forms.
30. **What evidence proves correctness?** Four real contention tests, scoped/privacy/
    CSV tests, 228 passing cases, actual HTTP/browser checks and unchanged seeded
    record fingerprints support the claims; no exhaustive security proof is claimed.

## Practical files to show

- app/event_services.py and sql/queries/07_events.sql, 08_registrations_attendance.sql.
- sql/queries/10_financial_reports.sql, 11_participation_reports.sql.
- sql/demo/README.md and complete safe demos 01-05.
- sql/reports/01_create_reporting_views.sql and docs/VIEW_DEPLOYMENT_PLAN.md.
- STAGE5_TEST_RESULTS.xml, the verification scripts and docs/screenshots/.
