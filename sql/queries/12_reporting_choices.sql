-- Choices are scoped too, so forms cannot leak other clubs/events.
-- name: reports.clubs
SELECT c.club_id,c.club_name FROM public.clubs c WHERE (%s::integer IS NULL OR EXISTS(
SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s)) ORDER BY c.club_name,c.club_id;
-- name: reports.events
SELECT e.event_id,e.club_id,e.title FROM public.events e WHERE (%s::integer IS NULL OR EXISTS(
SELECT 1 FROM public.club_admins a WHERE a.club_id=e.club_id AND a.user_id=%s)) ORDER BY e.title,e.event_id;
-- name: reports.personal
SELECT count(*) AS total,
 count(*) FILTER(WHERE r.status='registered') AS registered,count(*) FILTER(WHERE r.status='attended') AS attended,
 count(*) FILTER(WHERE r.status='cancelled') AS cancelled,
 count(*) FILTER(WHERE r.status='registered' AND e.status='scheduled' AND e.start_time>%s) AS upcoming,
 count(*) FILTER(WHERE r.status IN ('registered','attended') AND e.status<>'cancelled' AND e.start_time<=%s) AS past
FROM public.registrations r INNER JOIN public.events e ON e.event_id=r.event_id WHERE r.student_id=%s;
