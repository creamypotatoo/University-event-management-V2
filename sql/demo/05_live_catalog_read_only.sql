-- READ ONLY: inspect actual schema, never modify it or its records.
BEGIN READ ONLY;
DO $$ BEGIN IF current_database()<>'university_events_raw' THEN RAISE EXCEPTION 'Wrong database'; END IF; END $$;
SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name;
SELECT c.relname,con.conname,con.contype,pg_get_constraintdef(con.oid) AS definition FROM pg_constraint con
JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,con.contype,con.conname;
SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname;
SELECT viewname,definition FROM pg_views WHERE schemaname='public' AND viewname LIKE 'stage4_%' ORDER BY viewname;
SELECT extname,extversion FROM pg_extension WHERE extname='btree_gist';
COMMIT;
