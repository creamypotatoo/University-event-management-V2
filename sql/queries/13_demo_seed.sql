-- Operator-only demo seeder. No automatic execution; --apply requires approval.
-- name: seed.club
INSERT INTO public.clubs (club_name,description,created_at) VALUES (%s,%s,%s) RETURNING club_id;
-- name: seed.admin
INSERT INTO public.club_admins (club_id,user_id) VALUES (%s,%s) RETURNING club_admin_id;
-- name: seed.membership
INSERT INTO public.club_memberships (club_id,student_id,joined_at,status) VALUES (%s,%s,%s,%s) RETURNING membership_id;
-- name: seed.event
INSERT INTO public.events (club_id,venue_id,title,description,start_time,end_time,capacity,status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING event_id;
-- name: seed.registration
INSERT INTO public.registrations (event_id,student_id,registered_at,status) VALUES (%s,%s,%s,%s) RETURNING registration_id;
