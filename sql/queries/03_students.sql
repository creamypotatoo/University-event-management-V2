-- Student create/read/update. Deletion is intentionally unavailable.
-- name: students.create
INSERT INTO public.students (user_id,student_number,department,batch) VALUES (%s,%s,%s,%s) RETURNING student_id;
-- name: students.by_user
SELECT s.student_id,s.user_id,s.student_number,s.department,s.batch,u.full_name,u.email
FROM public.students s JOIN public.users u ON u.user_id=s.user_id WHERE s.user_id=%s;
-- name: students.by_id
SELECT s.student_id,s.user_id,s.student_number,s.department,s.batch,u.full_name,u.email
FROM public.students s JOIN public.users u ON u.user_id=s.user_id WHERE s.student_id=%s;
-- name: students.directory
SELECT s.student_id,s.student_number,s.department,s.batch,u.full_name,u.email
FROM public.students s JOIN public.users u ON u.user_id=s.user_id
ORDER BY u.full_name,s.student_id LIMIT %s OFFSET %s;
-- name: students.update_name
UPDATE public.users SET full_name=%s WHERE user_id=%s RETURNING user_id;
-- name: students.update_profile
UPDATE public.students SET department=%s,batch=%s WHERE user_id=%s RETURNING student_id;
