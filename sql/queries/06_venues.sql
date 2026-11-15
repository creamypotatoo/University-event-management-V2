-- name: venues.directory
SELECT venue_id,venue_name,location,capacity FROM public.venues ORDER BY venue_name,venue_id LIMIT %s OFFSET %s;
-- name: venues.detail
SELECT venue_id,venue_name,location,capacity FROM public.venues WHERE venue_id=%s;
-- name: venues.lock
SELECT venue_id,venue_name,location,capacity FROM public.venues WHERE venue_id=%s FOR UPDATE;
-- name: venues.create
INSERT INTO public.venues (venue_name,location,capacity) VALUES (%s,%s,%s) RETURNING venue_id;
-- name: venues.edit
UPDATE public.venues SET venue_name=%s,location=%s,capacity=%s WHERE venue_id=%s RETURNING venue_id;
-- name: venues.capacity_guard
SELECT event_id FROM public.events WHERE venue_id=%s AND status<>'cancelled' AND capacity>%s LIMIT 1;
