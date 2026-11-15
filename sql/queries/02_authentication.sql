-- Runtime statements loaded by app/sql.py. No values are interpolated.
-- name: auth.by_email
SELECT user_id, full_name, email, password_hash, role FROM public.users WHERE email = %s;
-- name: auth.by_id
SELECT user_id, full_name, email, password_hash, role FROM public.users WHERE user_id = %s;
-- name: auth.create_student_user
INSERT INTO public.users (full_name, email, password_hash, role) VALUES (%s,%s,%s,'student') RETURNING user_id;
-- name: auth.create_admin_user
INSERT INTO public.users (full_name,email,password_hash,role) VALUES (%s,%s,%s,%s) RETURNING user_id;
-- name: auth.bootstrap_lock
SELECT pg_advisory_xact_lock(42819031);
-- name: auth.existing_admin
SELECT user_id FROM public.users WHERE role='system_admin' LIMIT 1;
