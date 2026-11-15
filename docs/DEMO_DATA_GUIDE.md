# Fictional demonstration data - APPLIED WITH APPROVAL

Stage 5 user approval was received; 32 records committed and four logins passed.
The private .demo/seed-manifest.json tracks ownership; verify it with the seed CLI.
Existing records must not be deleted.

The seed CLI is explicit and preview-first. It never runs at startup. All identities
are clearly fictional and all emails use example.invalid. The dataset labdemo-v1
contains 4 users (one club administrator and three students), 3 student profiles,
2 clubs, 3 memberships, 2 club-admin assignments, 2 venues, 4 events, 7 registration/
attendance rows and 5 expenses: 32 records across all nine existing tables.

The events include two upcoming scheduled events, a completed event and a cancelled
event. Registered/attended/cancelled rows, a last-seat example and exact expenses
support the presentation. Times are relative to the first seed run. Dates are not
reset when repeated. Expense total is BDT 1205.80. No system-admin default account
is introduced; use the existing create-admin hidden-prompt CLI for your own admin.

## Safe preview and rollback validation (no approval for persistent data implied)

```powershell
Set-Location 'D:\dbms_project_raw_sql'
.\.venv\Scripts\python.exe -m flask --app run:app seed-demo
.\.venv\Scripts\python.exe -m flask --app run:app seed-demo --check
```

Default prints a plan without opening a DB connection. --check validates actual
parameterized INSERTs then rolls back everything and writes no ownership manifest.
SERIAL counters may advance, as PostgreSQL nextval is nontransactional; no sequence
is reset. Existing records are never updated/deleted by the seeder.

## Persistent apply - ONLY after explicit user approval

```powershell
.\.venv\Scripts\python.exe -m flask --app run:app seed-demo --apply
```

The CLI separately asks you to confirm persistent inserts, then privately prompts
for a 12-128-character demo passphrase and confirmation. Choose a private lab-only
passphrase, not the PostgreSQL password or session secret. It is hashed with scrypt,
never displayed/stored in the manifest, and shared only among the fictional demo
accounts for the local demo. Keep it locally; do not paste it into chat or a report.
The agent does not run --apply or create persistent demo records without approval.

Account emails (identifiers, not credentials): labdemo.club@example.invalid and
labdemo.student1@example.invalid through labdemo.student3@example.invalid.
Club/venue/event labels begin [LabDemo-v1]; student numbers are LABDEMO-001..003.

A transaction advisory lock serializes seeding. First apply refuses any reserved
email/number/club/venue collision instead of upserting. The ownership manifest at
.demo/seed-manifest.json records exact PKs and identifying labels, never passwords.
It is written as prepared before commit, then marked applied after success. A
repeat verifies every recorded identity and makes NO changes. Missing/edited rows
cause a safe refusal instead of partial reseeding, overwrites, or date resets.
A crash/commit/filesystem failure may leave a prepared manifest requiring manual
inspection; never erase it and rerun blindly. The manifest is private operator
bookkeeping, not an authorization credential or a cryptographic audit log.

## Identify and remove ONLY demo-owned records

No cleanup is run by Stage 5, and no automatic cleanup command is provided. The
current instruction forbids deleting existing records. If removal is requested
later, obtain separate explicit approval and back up the manifest first.

1. Validate every manifest PK still has the expected identifying labels and parent
   IDs. Stop on mismatch; do not infer ownership from a loose name prefix alone.
2. List the exact recorded IDs first using SELECT ... WHERE <pk>=ANY(ARRAY[...]).
3. In one transaction, delete ONLY those recorded expense, registration, event,
   membership, admin-assignment, student, club, venue, then user IDs (FK-safe order).
4. End a review run with ROLLBACK. Only explicitly approved actual removal should
   end with COMMIT. Never delete all children of a demo event or all matching names.
5. ON DELETE RESTRICT will stop removal if later non-demo children reference a demo
   parent. Preserve those new records and investigate; never cascade or widen
   cleanup predicates. Never reset IDs/sequences or drop/truncate any table.

The sanitized submission package excludes .env, .demo/, caches and credentials.
Keep the ownership manifest locally if you later apply the seed; do not lose it.
