-- Standalone teaching examples, NOT executed by Flask.
-- Run only against university_events_raw after approved setup.
BEGIN READ ONLY;
DO $$ BEGIN
 IF current_database() <> 'university_events_raw' THEN
  RAISE EXCEPTION 'Wrong database';
 END IF;
END $$;
-- SELECT every club column.
SELECT * FROM public.clubs;
-- Projection: choose student columns without user passwords.
SELECT student_number, department, batch FROM public.students;
-- Read venue details.
SELECT venue_name, location, capacity FROM public.venues;
-- ORDER BY: upcoming/oldest start time first; ID breaks ties.
SELECT event_id, title, start_time FROM public.events ORDER BY start_time, event_id;
-- WHERE: select active clubs.
SELECT club_id, club_name FROM public.clubs WHERE is_active = true;
-- WHERE and ORDER BY: positive capacity threshold, largest first.
SELECT venue_name, capacity FROM public.venues WHERE capacity >= 100 ORDER BY capacity DESC, venue_id;
-- LIMIT: deterministic first ten events.
SELECT event_id, title, start_time FROM public.events ORDER BY start_time, event_id LIMIT 10;
COMMIT;
