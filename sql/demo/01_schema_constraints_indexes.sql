-- EDUCATIONAL ONLY: every writable relation below is session-local pg_temp.
-- No live public table rows are inserted, updated or deleted.
BEGIN;
DO $$ BEGIN IF current_database()<>'university_events_raw' THEN RAISE EXCEPTION 'Wrong database'; END IF; END $$;
CREATE TEMP TABLE users (

    user_id SERIAL NOT NULL CONSTRAINT pk_users PRIMARY KEY,
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(254) NOT NULL,
    password_hash VARCHAR(512) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'student',
    CONSTRAINT ck_users_valid_role CHECK (role IN ('student', 'club_admin', 'system_admin')),
    CONSTRAINT ck_users_full_name_not_blank CHECK (length(trim(full_name)) > 0),
    CONSTRAINT ck_users_normalized_email CHECK (length(trim(email)) > 0 AND email = lower(trim(email))),
    CONSTRAINT ck_users_password_hash_not_blank CHECK (length(trim(password_hash)) > 0)
) ON COMMIT DROP;
CREATE TEMP TABLE students (

    student_id SERIAL NOT NULL CONSTRAINT pk_students PRIMARY KEY,
    user_id INTEGER NOT NULL CONSTRAINT fk_students_user_id_users REFERENCES pg_temp.users (user_id) ON DELETE RESTRICT CONSTRAINT uq_students_user_id UNIQUE,
    student_number VARCHAR(40) NOT NULL CONSTRAINT uq_students_student_number UNIQUE,
    department VARCHAR(100) NOT NULL,
    batch VARCHAR(30) NOT NULL,
    CONSTRAINT ck_students_student_number_not_blank CHECK (length(trim(student_number)) > 0),
    CONSTRAINT ck_students_department_not_blank CHECK (length(trim(department)) > 0),
    CONSTRAINT ck_students_batch_not_blank CHECK (length(trim(batch)) > 0)
) ON COMMIT DROP;
CREATE TEMP TABLE clubs (

    club_id SERIAL NOT NULL CONSTRAINT pk_clubs PRIMARY KEY,
    club_name VARCHAR(150) NOT NULL CONSTRAINT uq_clubs_club_name UNIQUE,
    description TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    CONSTRAINT ck_clubs_club_name_not_blank CHECK (length(trim(club_name)) > 0)
) ON COMMIT DROP;
CREATE TEMP TABLE club_memberships (

    membership_id SERIAL NOT NULL CONSTRAINT pk_club_memberships PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_club_memberships_club_id_clubs REFERENCES pg_temp.clubs (club_id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL CONSTRAINT fk_club_memberships_student_id_students REFERENCES pg_temp.students (student_id) ON DELETE RESTRICT,
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    CONSTRAINT uq_club_memberships_club_student UNIQUE (club_id, student_id),
    CONSTRAINT ck_club_memberships_valid_status CHECK (status IN ('active', 'cancelled'))
) ON COMMIT DROP;
CREATE TEMP TABLE club_admins (

    club_admin_id SERIAL NOT NULL CONSTRAINT pk_club_admins PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_club_admins_club_id_clubs REFERENCES pg_temp.clubs (club_id) ON DELETE RESTRICT,
    user_id INTEGER NOT NULL CONSTRAINT fk_club_admins_user_id_users REFERENCES pg_temp.users (user_id) ON DELETE RESTRICT,
    CONSTRAINT uq_club_admins_club_user UNIQUE (club_id, user_id)
) ON COMMIT DROP;
CREATE TEMP TABLE venues (

    venue_id SERIAL NOT NULL CONSTRAINT pk_venues PRIMARY KEY,
    venue_name VARCHAR(150) NOT NULL CONSTRAINT uq_venues_venue_name UNIQUE,
    location VARCHAR(255) NOT NULL,
    capacity INTEGER NOT NULL,
    CONSTRAINT ck_venues_positive_capacity CHECK (capacity > 0),
    CONSTRAINT ck_venues_venue_name_not_blank CHECK (length(trim(venue_name)) > 0),
    CONSTRAINT ck_venues_location_not_blank CHECK (length(trim(location)) > 0)
) ON COMMIT DROP;
CREATE TEMP TABLE events (

    event_id SERIAL NOT NULL CONSTRAINT pk_events PRIMARY KEY,
    club_id INTEGER NOT NULL CONSTRAINT fk_events_club_id_clubs REFERENCES pg_temp.clubs (club_id) ON DELETE RESTRICT,
    venue_id INTEGER NOT NULL CONSTRAINT fk_events_venue_id_venues REFERENCES pg_temp.venues (venue_id) ON DELETE RESTRICT,
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
) ON COMMIT DROP;
CREATE TEMP TABLE registrations (

    registration_id SERIAL NOT NULL CONSTRAINT pk_registrations PRIMARY KEY,
    event_id INTEGER NOT NULL CONSTRAINT fk_registrations_event_id_events REFERENCES pg_temp.events (event_id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL CONSTRAINT fk_registrations_student_id_students REFERENCES pg_temp.students (student_id) ON DELETE RESTRICT,
    registered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    status VARCHAR(20) NOT NULL DEFAULT 'registered',
    CONSTRAINT uq_registrations_event_student UNIQUE (event_id, student_id),
    CONSTRAINT ck_registrations_valid_status CHECK (status IN ('registered', 'cancelled', 'attended'))
) ON COMMIT DROP;
CREATE TEMP TABLE event_expenses (

    expense_id SERIAL NOT NULL CONSTRAINT pk_event_expenses PRIMARY KEY,
    event_id INTEGER NOT NULL CONSTRAINT fk_event_expenses_event_id_events REFERENCES pg_temp.events (event_id) ON DELETE RESTRICT,
    description VARCHAR(255) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    expense_date DATE NOT NULL,
    CONSTRAINT ck_event_expenses_nonnegative_amount CHECK (amount >= 0),
    CONSTRAINT ck_event_expenses_description_not_blank CHECK (length(trim(description)) > 0)
) ON COMMIT DROP;
ALTER TABLE pg_temp.events ADD CONSTRAINT ex_events_venue_time
EXCLUDE USING gist (venue_id WITH =, tstzrange(start_time, end_time, '[)') WITH &&)
WHERE (status <> 'cancelled');
CREATE UNIQUE INDEX uq_users_email ON pg_temp.users (email);
CREATE INDEX ix_users_full_name ON pg_temp.users (full_name);
CREATE INDEX ix_students_department ON pg_temp.students (department);
CREATE INDEX ix_club_memberships_student_id ON pg_temp.club_memberships (student_id);
CREATE INDEX ix_club_admins_user_id ON pg_temp.club_admins (user_id);
CREATE INDEX ix_events_club_id ON pg_temp.events (club_id);
CREATE INDEX ix_events_venue_id ON pg_temp.events (venue_id);
CREATE INDEX ix_events_title ON pg_temp.events (title);
CREATE INDEX ix_events_start_time ON pg_temp.events (start_time);
CREATE INDEX ix_events_status ON pg_temp.events (status);
CREATE INDEX ix_registrations_student_id ON pg_temp.registrations (student_id);
CREATE INDEX ix_registrations_event_status ON pg_temp.registrations (event_id, status);
CREATE INDEX ix_event_expenses_event_id ON pg_temp.event_expenses (event_id);
CREATE INDEX ix_event_expenses_expense_date ON pg_temp.event_expenses (expense_date);

INSERT INTO pg_temp.users (user_id,full_name,email,password_hash,role) VALUES
 (1,'Demo Student One (Fictional)','one@example.invalid','unusable-demo-hash','student'),
 (2,'Demo Student Two (Fictional)','two@example.invalid','unusable-demo-hash','student'),
 (3,'Demo Club Admin (Fictional)','admin@example.invalid','unusable-demo-hash','club_admin');
INSERT INTO pg_temp.students (student_id,user_id,student_number,department,batch) VALUES
 (1,1,'TEMP-001','Computer Science','2026'),(2,2,'TEMP-002','Arts','2026');
INSERT INTO pg_temp.clubs (club_id,club_name,description) VALUES (1,'Temporary Robotics Club','Fictional temporary teaching record');
INSERT INTO pg_temp.club_memberships (membership_id,club_id,student_id) VALUES (1,1,1);
INSERT INTO pg_temp.club_admins (club_admin_id,club_id,user_id) VALUES (1,1,3);
INSERT INTO pg_temp.venues (venue_id,venue_name,location,capacity) VALUES (1,'Temporary Hall','Fictional demo campus',50);
INSERT INTO pg_temp.events (event_id,club_id,venue_id,title,description,start_time,end_time,capacity,status) VALUES
 (1,1,1,'Temporary completed workshop','Temporary only','2020-01-01T10:00:00+06:00','2020-01-01T12:00:00+06:00',2,'completed'),
 (2,1,1,'Temporary upcoming seminar','Temporary only','2040-01-01T10:00:00+06:00','2040-01-01T12:00:00+06:00',3,'scheduled');
INSERT INTO pg_temp.registrations (registration_id,event_id,student_id,status) VALUES (1,1,1,'registered'),(2,1,2,'attended');
INSERT INTO pg_temp.event_expenses (expense_id,event_id,description,amount,expense_date) VALUES
 (1,1,'Temporary supplies',10.10,'2020-01-01'),(2,1,'Temporary handouts',20.20,'2020-01-01');
-- Each failed write is confined to a PL/pgSQL exception subtransaction.
DO $$ BEGIN
 BEGIN INSERT INTO pg_temp.venues VALUES (99,'Invalid','Demo',0); RAISE EXCEPTION 'CHECK failed to protect capacity';
 EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: positive venue capacity CHECK'; END;
 BEGIN INSERT INTO pg_temp.users VALUES (99,'Duplicate','one@example.invalid','unusable-demo-hash','student'); RAISE EXCEPTION 'UNIQUE failed';
 EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'PASS: normalized unique email'; END;
 BEGIN INSERT INTO pg_temp.students VALUES (99,999,'TEMP-999','Test','2026'); RAISE EXCEPTION 'FK failed';
 EXCEPTION WHEN foreign_key_violation THEN RAISE NOTICE 'PASS: student user FOREIGN KEY'; END;
 BEGIN INSERT INTO pg_temp.registrations (registration_id,event_id,student_id) VALUES (99,1,1); RAISE EXCEPTION 'Lifetime uniqueness failed';
 EXCEPTION WHEN unique_violation THEN RAISE NOTICE 'PASS: event/student lifetime UNIQUE'; END;
 BEGIN INSERT INTO pg_temp.event_expenses VALUES (99,1,'Invalid',-1,'2020-01-01'); RAISE EXCEPTION 'Amount CHECK failed';
 EXCEPTION WHEN check_violation THEN RAISE NOTICE 'PASS: nonnegative exact amount CHECK'; END;
 BEGIN INSERT INTO pg_temp.events (event_id,club_id,venue_id,title,description,start_time,end_time,capacity) VALUES
 (99,1,1,'Overlap','Demo','2040-01-01T11:00:00+06:00','2040-01-01T13:00:00+06:00',1); RAISE EXCEPTION 'Exclusion failed';
 EXCEPTION WHEN exclusion_violation THEN RAISE NOTICE 'PASS: GiST venue-overlap exclusion'; END;
END $$;
SELECT c.relname,con.conname,con.contype,pg_get_constraintdef(con.oid) AS definition
FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid WHERE c.relnamespace=pg_my_temp_schema() ORDER BY c.relname,con.contype,con.conname;
SELECT indexname,indexdef FROM pg_indexes WHERE schemaname=(SELECT nspname FROM pg_namespace WHERE oid=pg_my_temp_schema()) ORDER BY indexname;
ROLLBACK;
