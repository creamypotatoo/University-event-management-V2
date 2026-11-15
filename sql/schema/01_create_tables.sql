-- Fresh university_events_raw database only. Run via psql with ON_ERROR_STOP.
BEGIN;
DO $$ BEGIN
  IF current_database() <> 'university_events_raw' THEN
    RAISE EXCEPTION 'Refusing database other than university_events_raw';
  END IF;
END $$;
CREATE TABLE public.users (
    user_id SERIAL NOT NULL CONSTRAINT pk_users PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    CONSTRAINT ck_users_valid_role CHECK (role IN ('student', 'club_admin', 'system_admin')),
    CONSTRAINT ck_users_full_name_not_blank CHECK (length(trim(full_name)) > 0),
    CONSTRAINT ck_users_normalized_email CHECK (length(trim(email)) > 0 AND email = lower(trim(email))),
    CONSTRAINT ck_users_password_hash_not_blank CHECK (length(trim(password_hash)) > 0)
);

CREATE TABLE public.students (
    student_id SERIAL NOT NULL CONSTRAINT pk_students PRIMARY KEY,
    user_id INTEGER NOT NULL CONSTRAINT fk_students_user_id_users REFERENCES public.users (user_id) ON DELETE RESTRICT CONSTRAINT uq_students_user_id UNIQUE,
    student_number VARCHAR(40) NOT NULL CONSTRAINT uq_students_student_number UNIQUE,
    department VARCHAR(100) NOT NULL,
    batch VARCHAR(30) NOT NULL,
    CONSTRAINT ck_students_student_number_not_blank CHECK (length(trim(student_number)) > 0),
    CONSTRAINT ck_students_department_not_blank CHECK (length(trim(department)) > 0),
    CONSTRAINT ck_students_batch_not_blank CHECK (length(trim(batch)) > 0)
);

CREATE TABLE public.clubs (
    club_id SERIAL NOT NULL CONSTRAINT pk_clubs PRIMARY KEY,
    club_name VARCHAR(150) NOT NULL CONSTRAINT uq_clubs_club_name UNIQUE,
    description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_clubs_club_name_not_blank CHECK (length(trim(club_name)) > 0)
);

CREATE TABLE public.club_memberships (
    membership_id SERIAL NOT NULL CONSTRAINT pk_club_memberships PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_club_memberships_club_id_clubs REFERENCES public.clubs (club_id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL CONSTRAINT fk_club_memberships_student_id_students REFERENCES public.students (student_id) ON DELETE RESTRICT,
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    CONSTRAINT uq_club_memberships_club_student UNIQUE (club_id, student_id),
    CONSTRAINT ck_club_memberships_valid_status CHECK (status IN ('active', 'cancelled'))
);

CREATE TABLE public.club_admins (
    club_admin_id SERIAL NOT NULL CONSTRAINT pk_club_admins PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_club_admins_club_id_clubs REFERENCES public.clubs (club_id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL CONSTRAINT fk_club_admins_user_id_users REFERENCES public.users (user_id) ON DELETE RESTRICT,
    CONSTRAINT uq_club_admins_club_user UNIQUE (club_id, user_id)
);

CREATE TABLE public.venues (
    venue_id SERIAL NOT NULL CONSTRAINT pk_venues PRIMARY KEY,
    venue_name VARCHAR(150) NOT NULL CONSTRAINT uq_venues_venue_name UNIQUE,
    location VARCHAR(255) NOT NULL,
    capacity INTEGER NOT NULL,
    CONSTRAINT ck_venues_positive_capacity CHECK (capacity > 0),
    CONSTRAINT ck_venues_venue_name_not_blank CHECK (length(trim(venue_name)) > 0),
    CONSTRAINT ck_venues_location_not_blank CHECK (length(trim(location)) > 0)
);

CREATE TABLE public.events (
    event_id SERIAL NOT NULL CONSTRAINT pk_events PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_events_club_id_clubs REFERENCES public.clubs (club_id) ON DELETE RESTRICT,
    venue_id INTEGER NOT NULL CONSTRAINT fk_events_venue_id_venues REFERENCES public.venues (venue_id) ON DELETE RESTRICT,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    capacity INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
    CONSTRAINT ck_events_positive_capacity CHECK (capacity > 0),
    CONSTRAINT ck_events_valid_time_range CHECK (end_time > start_time),
    CONSTRAINT ck_events_valid_status CHECK (status IN ('scheduled', 'completed', 'cancelled')),
    CONSTRAINT ck_events_title_not_blank CHECK (length(trim(title)) > 0)
);

CREATE TABLE public.registrations (
    registration_id SERIAL NOT NULL CONSTRAINT pk_registrations PRIMARY KEY,
    event_id INTEGER NOT NULL CONSTRAINT fk_registrations_event_id_events REFERENCES public.events (event_id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL CONSTRAINT fk_registrations_student_id_students REFERENCES public.students (student_id) ON DELETE RESTRICT,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'registered',
    CONSTRAINT uq_registrations_event_student UNIQUE (event_id, student_id),
    CONSTRAINT ck_registrations_valid_status CHECK (status IN ('registered', 'cancelled', 'attended'))
);

CREATE TABLE public.event_expenses (
    expense_id SERIAL NOT NULL CONSTRAINT pk_event_expenses PRIMARY KEY,
    event_id INTEGER NOT NULL CONSTRAINT fk_event_expenses_event_id_events REFERENCES public.events (event_id) ON DELETE RESTRICT,
    description VARCHAR(255) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    expense_date DATE NOT NULL,
    CONSTRAINT ck_event_expenses_nonnegative_amount CHECK (amount >= 0),
    CONSTRAINT ck_event_expenses_description_not_blank CHECK (length(trim(description)) > 0)
);
COMMIT;
