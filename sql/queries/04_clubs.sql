-- name: clubs.detail
SELECT club_id,club_name,description,is_active,created_at FROM public.clubs WHERE club_id=%s;
-- name: clubs.lock
SELECT club_id,club_name,description,is_active FROM public.clubs WHERE club_id=%s FOR UPDATE;
-- name: clubs.create
INSERT INTO public.clubs (club_name,description) VALUES (%s,%s) RETURNING club_id;
-- name: clubs.edit
UPDATE public.clubs SET club_name=%s,description=%s WHERE club_id=%s RETURNING club_id;
-- name: clubs.status
UPDATE public.clubs SET is_active=%s WHERE club_id=%s RETURNING club_id;
-- name: clubs.scope
SELECT club_admin_id FROM public.club_admins WHERE club_id=%s AND user_id=%s;
-- name: clubs.assigned
SELECT c.club_id,c.club_name,c.is_active FROM public.clubs c JOIN public.club_admins a ON a.club_id=c.club_id WHERE a.user_id=%s ORDER BY c.club_name,c.club_id;
-- name: clubs.admins
SELECT u.user_id,u.full_name,u.email FROM public.club_admins a JOIN public.users u ON u.user_id=a.user_id WHERE a.club_id=%s ORDER BY u.full_name,u.user_id;
-- name: clubs.admin_candidate
SELECT user_id FROM public.users WHERE email=%s AND role='club_admin' FOR UPDATE;
-- name: clubs.assign
INSERT INTO public.club_admins (club_id,user_id) VALUES (%s,%s) ON CONFLICT (club_id,user_id) DO NOTHING;
-- name: clubs.unassign
DELETE FROM public.club_admins WHERE club_id=%s AND user_id=%s;
-- name: clubs.directory
SELECT club_id, club_name, description, is_active
FROM public.clubs ORDER BY club_name, club_id LIMIT %s;
-- name: clubs.filtered
SELECT club_id,club_name,description,is_active FROM public.clubs
WHERE (%s='all' OR is_active=%s) AND (position(lower(%s) in lower(club_name))>0 OR position(lower(%s) in lower(description))>0)
ORDER BY club_name,club_id LIMIT %s;
