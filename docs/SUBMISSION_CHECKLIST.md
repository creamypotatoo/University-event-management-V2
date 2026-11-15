# Final submission checklist

Target: 16 November 2026 (Asia/Dhaka). Work: D:\dbms_project_raw_sql only.

- [x] Nine base tables/columns/constraints/indexes preserved.
- [x] Three normal reporting views deployed after explicit approval.
- [x] 32 fictional records approved/seeded; four role logins verified.
- [x] Repeat seed is a verified no-op; private ownership manifest retained locally.
- [x] Full suite: 228 passed, 0 failed, 0 skipped; four real contention cases pass.
- [x] db-check, dependencies and Python/Jinja compilation pass.
- [x] Real HTTP workflows pass with rollback-only fixtures.
- [x] Desktop/mobile browser QA, local styling and screenshots complete.
- [x] SQL demos 01-05 execute with TEMP/read-only objects only.
- [x] Existing 32-record fingerprints unchanged after all QA.
- [x] Original Git check is clean with optional writes disabled; original DB never accessed.
- [x] README includes HOW TO LAUNCH THE WEBSITE, setup/roles/SQL/seed/troubleshooting.
- [x] Viva guide includes five-minute demo, ACID/locks/joins and 30 Q&As.
- [x] No ORM or hardcoded real credentials; env configuration remains private.
- [x] Packager excludes .env, .demo, Git, virtual env, caches and logs.
- [ ] Inspect the final ZIP/hash manifest and back up private local configuration.
- [ ] Before presentation run db-check, launch run.py and use the private passphrase.
- [ ] For system-only screens create your initial admin via hidden CLI prompts.
- [ ] Add institutional cover/course/student details yourself; none were invented.

No commit/push/hosting deployment/table reset/existing-record removal was performed.
The ZIP reconstructs source/schema, not private credentials or a database dump.
Another machine needs its own approved fresh setup/seeding. Keep local ownership
manifest for any separately approved future cleanup; never delete by loose prefix.
