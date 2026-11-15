-- STANDALONE DEMONSTRATION ONLY; Flask never loads this file.
-- Run only against university_events_raw after creating your own demo records:
-- psql -X -d university_events_raw -v event_id=123 -v student_id=456 -f sql/demonstrations/01_registration_locks.sql
-- Only SELECTs/locks; no registrations are changed. Always ROLLBACK.
\set ON_ERROR_STOP on
\if :{?event_id}
\else
\echo 'Supply -v event_id=<your event id> and -v student_id=<your student id>.'
\quit
\endif
\if :{?student_id}
\else
\echo 'Supply -v student_id=<your student id>.'
\quit
\endif
BEGIN;
DO $$ BEGIN
 IF current_database()<>'university_events_raw' THEN
  RAISE EXCEPTION 'Wrong database';
 END IF;
END $$;
-- 1. Shared club lock blocks deactivation/assignment changes, allows other readers.
SELECT club_id,is_active FROM public.clubs
WHERE club_id=(SELECT club_id FROM public.events WHERE event_id=:'event_id'::integer) FOR SHARE;
-- 2. Exclusive event lock serializes seat allocation. Another registration waits here.
SELECT event_id,capacity,start_time,status FROM public.events WHERE event_id=:'event_id'::integer FOR UPDATE;
-- 3. Capacity is checked AFTER acquiring the event lock in the same transaction.
SELECT count(*) AS occupied FROM public.registrations
WHERE event_id=:'event_id'::integer AND status IN ('registered','attended');
-- 4. Existing lifetime row is locked before returning/idempotent/reactivation decisions.
SELECT registration_id,status,registered_at FROM public.registrations
WHERE event_id=:'event_id'::integer AND student_id=:'student_id'::integer FOR UPDATE;
-- The application checks eligibility/deadline, then uses registrations.create/update
-- from 08_registrations_attendance.sql and COMMIT. This teaching script changes
-- nothing. See app/event_services.py for the actual tested algorithm.
ROLLBACK;
