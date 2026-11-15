-- Runtime event reads/writes. Never concatenate request values.
-- name: events.preview
SELECT event_id,club_id,venue_id FROM public.events WHERE event_id=%s;
-- name: events.club_share
SELECT club_id,is_active FROM public.clubs WHERE club_id=%s FOR SHARE;
-- name: events.venue_lock
SELECT venue_id,capacity FROM public.venues WHERE venue_id=%s FOR UPDATE;
-- name: events.lock
SELECT event_id,club_id,venue_id,title,description,start_time,end_time,capacity,status FROM public.events WHERE event_id=%s FOR UPDATE;
-- name: events.occupied
SELECT count(*) AS occupied FROM public.registrations WHERE event_id=%s AND status IN ('registered','attended');
-- name: events.overlap
SELECT event_id,title,start_time,end_time FROM public.events
WHERE venue_id=%s AND status<>'cancelled' AND start_time<%s AND end_time>%s
AND (%s::integer IS NULL OR event_id<>%s) ORDER BY start_time,event_id LIMIT 20;
-- name: events.create
INSERT INTO public.events (club_id,venue_id,title,description,start_time,end_time,capacity,status)
VALUES (%s,%s,%s,%s,%s,%s,%s,'scheduled') RETURNING event_id;
-- name: events.edit
UPDATE public.events SET venue_id=%s,title=%s,description=%s,start_time=%s,end_time=%s,capacity=%s WHERE event_id=%s RETURNING event_id;
-- name: events.status
UPDATE public.events SET status=%s WHERE event_id=%s RETURNING event_id;
-- name: events.detail
SELECT e.*,c.club_name,c.is_active AS club_active,v.venue_name,v.location,v.capacity AS venue_capacity,
(SELECT count(*) FROM public.registrations r WHERE r.event_id=e.event_id AND r.status IN ('registered','attended')) AS occupied
FROM public.events e JOIN public.clubs c ON c.club_id=e.club_id JOIN public.venues v ON v.venue_id=e.venue_id WHERE e.event_id=%s;
-- name: events.directory
SELECT e.*,c.club_name,c.is_active AS club_active,v.venue_name,
(SELECT count(*) FROM public.registrations r WHERE r.event_id=e.event_id AND r.status IN ('registered','attended')) AS occupied
FROM public.events e JOIN public.clubs c ON c.club_id=e.club_id JOIN public.venues v ON v.venue_id=e.venue_id
WHERE (%s='all' OR e.status=%s)
AND (%s='all' OR (%s='upcoming' AND e.start_time>%s) OR (%s='past' AND e.start_time<=%s))
AND (%s::integer IS NULL OR e.club_id=%s) AND (%s::integer IS NULL OR e.venue_id=%s)
AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
AND (position(lower(%s) in lower(e.title))>0 OR position(lower(%s) in lower(e.description))>0)
AND (%s::integer IS NULL OR EXISTS (SELECT 1 FROM public.club_admins a WHERE a.club_id=e.club_id AND a.user_id=%s))
ORDER BY e.start_time,e.event_id LIMIT %s OFFSET %s;
-- name: events.clubs
SELECT club_id,club_name,is_active FROM public.clubs ORDER BY club_name,club_id;
-- name: events.venues
SELECT venue_id,venue_name,capacity FROM public.venues ORDER BY venue_name,venue_id;
