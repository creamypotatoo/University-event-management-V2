-- Runtime registration lifecycle. Caller locks Club -> Event -> Registration.
-- name: registrations.lock
SELECT registration_id,event_id,student_id,registered_at,status FROM public.registrations WHERE event_id=%s AND student_id=%s FOR UPDATE;
-- name: registrations.mine_one
SELECT registration_id,event_id,student_id,registered_at,status FROM public.registrations WHERE event_id=%s AND student_id=%s;
-- name: registrations.create
INSERT INTO public.registrations (event_id,student_id,status) VALUES (%s,%s,'registered') RETURNING registration_id;
-- name: registrations.update
UPDATE public.registrations SET status=%s WHERE registration_id=%s AND event_id=%s RETURNING registration_id;
-- name: registrations.participant_lock
SELECT registration_id,event_id,student_id,status FROM public.registrations WHERE event_id=%s AND registration_id=%s FOR UPDATE;
-- name: registrations.history
SELECT r.registration_id,r.status,r.registered_at,e.event_id,e.title,e.start_time,e.end_time,e.status AS event_status,c.club_name,v.venue_name
FROM public.registrations r JOIN public.events e ON e.event_id=r.event_id JOIN public.clubs c ON c.club_id=e.club_id JOIN public.venues v ON v.venue_id=e.venue_id
WHERE r.student_id=%s AND (%s='all' OR r.status=%s) AND position(lower(%s) in lower(e.title))>0
ORDER BY e.start_time DESC,r.registration_id LIMIT %s OFFSET %s;
-- name: registrations.participants
SELECT r.registration_id,r.status,r.registered_at,s.student_number,u.full_name
FROM public.registrations r JOIN public.students s ON s.student_id=r.student_id JOIN public.users u ON u.user_id=s.user_id
WHERE r.event_id=%s AND (%s='all' OR r.status=%s)
AND (position(lower(%s) in lower(u.full_name))>0 OR position(lower(%s) in lower(s.student_number))>0)
ORDER BY u.full_name,r.registration_id LIMIT %s OFFSET %s;
