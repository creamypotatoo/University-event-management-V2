-- PROPOSED persistent objects. Apply only after explicit user approval.
-- Normal aggregate views, not materialized; base tables/constraints are untouched.
-- No OR REPLACE, DROP, grants or automatic startup execution.
BEGIN;
DO $$ BEGIN
 IF current_database()<>'university_events_raw' THEN RAISE EXCEPTION 'Wrong database'; END IF;
END $$;
CREATE VIEW public.stage4_event_participation_summary AS
SELECT e.event_id,e.club_id,e.title,e.status,e.start_time,e.capacity,
 count(r.registration_id) AS total_registrations,
 count(r.registration_id) FILTER (WHERE r.status='registered') AS active_registrations,
 count(r.registration_id) FILTER (WHERE r.status='attended') AS attended,
 count(r.registration_id) FILTER (WHERE r.status='cancelled') AS cancelled_registrations,
 count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended')) AS occupied,
 round(100.0*count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended'))/e.capacity,1) AS occupancy_pct,
 CASE WHEN e.status='completed' THEN round(100.0*count(r.registration_id) FILTER (WHERE r.status='attended')/
 NULLIF(count(r.registration_id) FILTER (WHERE r.status IN ('registered','attended')),0),1) END AS attendance_rate
FROM public.events e LEFT JOIN public.registrations r ON r.event_id=e.event_id
GROUP BY e.event_id;
CREATE VIEW public.stage4_event_financial_summary AS
SELECT e.event_id,e.club_id,e.title,count(x.expense_id) AS expense_count,
 coalesce(sum(x.amount),0::numeric) AS total_expenses,
 avg(x.amount) AS average_expense,min(x.amount) AS minimum_expense,max(x.amount) AS maximum_expense
FROM public.events e LEFT JOIN public.event_expenses x ON x.event_id=e.event_id
GROUP BY e.event_id;
CREATE VIEW public.stage4_club_activity_summary AS
WITH participation AS (SELECT club_id,count(*) AS event_count,sum(total_registrations) AS total_registrations,
 sum(occupied) AS occupied,sum(attended) AS attended FROM public.stage4_event_participation_summary GROUP BY club_id),
finance AS (SELECT club_id,sum(total_expenses) AS total_expenses FROM public.stage4_event_financial_summary GROUP BY club_id)
SELECT c.club_id,c.club_name,c.is_active,coalesce(p.event_count,0) AS event_count,
 coalesce(p.total_registrations,0) AS total_registrations,coalesce(p.occupied,0) AS occupied,
 coalesce(p.attended,0) AS attended,coalesce(f.total_expenses,0::numeric) AS total_expenses
FROM public.clubs c LEFT JOIN participation p ON p.club_id=c.club_id LEFT JOIN finance f ON f.club_id=c.club_id;
COMMIT;
