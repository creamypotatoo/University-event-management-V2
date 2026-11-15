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
-- INNER multi-table JOIN: venue/club labels without copying them into events.
SELECT e.event_id,e.title,c.club_name,v.venue_name,e.start_time
FROM pg_temp.events e INNER JOIN pg_temp.clubs c ON c.club_id=e.club_id
INNER JOIN pg_temp.venues v ON v.venue_id=e.venue_id ORDER BY e.start_time,e.event_id LIMIT 20;
-- LEFT JOIN and exact aggregates: include events without expenses.
SELECT e.event_id,e.title,count(x.expense_id) AS expense_count,coalesce(sum(x.amount),0::numeric) AS total_expenses,
 avg(x.amount) AS average_expense,min(x.amount) AS minimum_expense,max(x.amount) AS maximum_expense
FROM pg_temp.events e LEFT JOIN pg_temp.event_expenses x ON x.event_id=e.event_id GROUP BY e.event_id ORDER BY total_expenses DESC,e.event_id;
-- CTEs, CASE, COALESCE: child tables grouped separately to prevent join fanout.
WITH money AS (SELECT event_id,sum(amount) AS total FROM pg_temp.event_expenses GROUP BY event_id),
seats AS (SELECT event_id,count(*) AS registrations,sum(CASE WHEN status IN ('registered','attended') THEN 1 ELSE 0 END) AS occupied
 FROM pg_temp.registrations GROUP BY event_id)
SELECT e.event_id,e.title,coalesce(m.total,0::numeric) AS total_expenses,coalesce(s.registrations,0) AS total_registrations,
 coalesce(s.occupied,0) AS occupied,round(100.0*coalesce(s.occupied,0)/e.capacity,1) AS occupancy_pct
FROM pg_temp.events e LEFT JOIN money m ON m.event_id=e.event_id LEFT JOIN seats s ON s.event_id=e.event_id ORDER BY e.event_id;
-- HAVING answers a useful question: which clubs incurred strictly positive costs?
SELECT c.club_id,c.club_name,sum(x.amount) AS total_expenses FROM pg_temp.clubs c
INNER JOIN pg_temp.events e ON e.club_id=c.club_id INNER JOIN pg_temp.event_expenses x ON x.event_id=e.event_id
GROUP BY c.club_id,c.club_name HAVING sum(x.amount)>0 ORDER BY total_expenses DESC,c.club_id LIMIT 5;
-- Correlated NOT EXISTS: events missing expense records, useful for cost review.
SELECT e.event_id,e.title FROM pg_temp.events e
WHERE NOT EXISTS(SELECT 1 FROM pg_temp.event_expenses x WHERE x.event_id=e.event_id) ORDER BY e.event_id;
-- EXISTS and a correlated seat-count subquery: upcoming events and their current seat usage.
SELECT c.club_id,c.club_name FROM pg_temp.clubs c WHERE EXISTS(
 SELECT 1 FROM pg_temp.events e WHERE e.club_id=c.club_id AND e.status='scheduled' AND e.start_time>current_timestamp);
SELECT e.event_id,e.title,(SELECT count(*) FROM pg_temp.registrations r WHERE r.event_id=e.event_id AND r.status IN ('registered','attended')) AS occupied
FROM pg_temp.events e ORDER BY occupied DESC,e.event_id LIMIT 5;
-- Monthly expenses use expense_date; participation uses start_time AT TIME ZONE 'Asia/Dhaka'.
SELECT date_trunc('month',expense_date)::date AS month,sum(amount) AS total_expenses
FROM pg_temp.event_expenses GROUP BY date_trunc('month',expense_date) ORDER BY month;
CREATE TEMP VIEW stage4_event_participation_summary AS
SELECT e.event_id,e.club_id,e.title,e.status,e.start_time,e.capacity,
 count(r.registration_id) AS total_registrations,
 count(r.registration_id) FILTER (WHERE r.status='registered') AS active_registrations,
 count(r.registration_id) FILTER (WHERE r.status='attended') AS attended,
 count(r.registration_id) FILTER (WHERE r.status='cancelled') AS cancelled_registrations,
 count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended')) AS occupied,
 round(100.0*count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended'))/e.capacity,1) AS occupancy_pct,
 CASE WHEN e.status='completed' THEN round(100.0*count(r.registration_id) FILTER (WHERE r.status='attended')/
 NULLIF(count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended')),0),1) END AS attendance_rate
FROM pg_temp.events e LEFT JOIN pg_temp.registrations r ON r.event_id=e.event_id
GROUP BY e.event_id;
CREATE TEMP VIEW stage4_event_financial_summary AS
SELECT e.event_id,e.club_id,e.title,count(x.expense_id) AS expense_count,
 coalesce(sum(x.amount),0::numeric) AS total_expenses,
 avg(x.amount) AS average_expense,min(x.amount) AS minimum_expense,max(x.amount) AS maximum_expense
FROM pg_temp.events e LEFT JOIN pg_temp.event_expenses x ON x.event_id=e.event_id
GROUP BY e.event_id;
CREATE TEMP VIEW stage4_club_activity_summary AS
WITH participation AS (SELECT club_id,count(*) AS event_count,sum(total_registrations) AS total_registrations,
 sum(occupied) AS occupied,sum(attended) AS attended FROM pg_temp.stage4_event_participation_summary GROUP BY club_id),
finance AS (SELECT club_id,sum(total_expenses) AS total_expenses FROM pg_temp.stage4_event_financial_summary GROUP BY club_id)
SELECT c.club_id,c.club_name,c.is_active,coalesce(p.event_count,0) AS event_count,
 coalesce(p.total_registrations,0) AS total_registrations,coalesce(p.occupied,0) AS occupied,
 coalesce(p.attended,0) AS attended,coalesce(f.total_expenses,0::numeric) AS total_expenses
FROM pg_temp.clubs c LEFT JOIN participation p ON p.club_id=c.club_id LEFT JOIN finance f ON f.club_id=c.club_id;
SELECT event_id,total_expenses FROM pg_temp.stage4_event_financial_summary ORDER BY event_id;
SELECT event_id,total_registrations,occupied,occupancy_pct,attendance_rate FROM pg_temp.stage4_event_participation_summary ORDER BY event_id;
SELECT * FROM pg_temp.stage4_club_activity_summary;
ROLLBACK;
