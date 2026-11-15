-- Fresh university_events_raw database only. Run via psql with ON_ERROR_STOP.
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'university_events_raw' THEN
    RAISE EXCEPTION 'Refusing database other than university_events_raw';
  END IF;
END $$;
CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public;
ALTER TABLE public.events ADD CONSTRAINT ex_events_venue_time
EXCLUDE USING gist (venue_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
WHERE (status <> 'cancelled');
CREATE UNIQUE INDEX uq_users_email ON public.users (email);
CREATE INDEX ix_users_full_name ON public.users (full_name);
CREATE INDEX ix_students_department ON public.students (department);
CREATE INDEX ix_club_memberships_student_id ON public.club_memberships (student_id);
CREATE INDEX ix_club_admins_user_id ON public.club_admins (user_id);
CREATE INDEX ix_events_club_id ON public.events (club_id);
CREATE INDEX ix_events_venue_id ON public.events (venue_id);
CREATE INDEX ix_events_title ON public.events (title);
CREATE INDEX ix_events_start_time ON public.events (start_time);
CREATE INDEX ix_events_status ON public.events (status);
CREATE INDEX ix_registrations_student_id ON public.registrations (student_id);
CREATE INDEX ix_registrations_event_status ON public.registrations (event_id, status);
CREATE INDEX ix_event_expenses_event_id ON public.event_expenses (event_id);
CREATE INDEX ix_event_expenses_expense_date ON public.event_expenses (expense_date);
COMMIT;
