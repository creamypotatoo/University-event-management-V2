-- Runtime participation aggregates; dates apply to campus-local event start, not registration creation.
-- name: analytics.events
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT * FROM event_rollup ORDER BY start_time,event_id;
-- name: analytics.clubs
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT c.club_id,c.club_name,count(e.event_id) AS event_count,coalesce(sum(e.total_registrations),0) AS total_registrations,
coalesce(sum(e.occupied),0) AS occupied,coalesce(sum(e.attended),0) AS attended
FROM scoped_clubs c LEFT JOIN event_rollup e ON e.club_id=c.club_id GROUP BY c.club_id,c.club_name ORDER BY c.club_name,c.club_id;
-- name: analytics.monthly
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT date_trunc('month',start_time AT TIME ZONE 'Asia/Dhaka')::date AS month,count(*) AS event_count
FROM event_rollup GROUP BY date_trunc('month',start_time AT TIME ZONE 'Asia/Dhaka') ORDER BY month;
-- name: analytics.statuses
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT status,count(*) AS event_count FROM event_rollup GROUP BY status ORDER BY status;
-- name: analytics.popular
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT event_id,title,club_name,total_registrations FROM event_rollup
ORDER BY total_registrations DESC,event_id LIMIT 5;
-- name: analytics.summary
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
 AND (%s::timestamptz IS NULL OR e.start_time>=%s) AND (%s::timestamptz IS NULL OR e.start_time<%s)
), registration_totals AS (
 SELECT r.event_id,count(*) AS total_registrations,
 sum(CASE WHEN r.status='registered' THEN 1 ELSE 0 END) AS active_registrations,
 sum(CASE WHEN r.status='attended' THEN 1 ELSE 0 END) AS attended,
 sum(CASE WHEN r.status='cancelled' THEN 1 ELSE 0 END) AS cancelled_registrations
 FROM public.registrations r INNER JOIN scoped_events e ON e.event_id=r.event_id GROUP BY r.event_id
), event_counts AS (
 SELECT e.event_id,e.club_id,e.club_name,e.title,e.status,e.start_time,e.capacity,
 coalesce(r.total_registrations,0) AS total_registrations,coalesce(r.active_registrations,0) AS active_registrations,
 coalesce(r.attended,0) AS attended,coalesce(r.cancelled_registrations,0) AS cancelled_registrations,
 coalesce(r.active_registrations,0)+coalesce(r.attended,0) AS occupied
 FROM scoped_events e LEFT JOIN registration_totals r ON r.event_id=e.event_id
), event_rollup AS (
 SELECT *,round(100.0*occupied/capacity,1) AS occupancy_pct,
 CASE WHEN status='completed' THEN round(100.0*attended/NULLIF(occupied,0),1) END AS attendance_rate FROM event_counts
)
SELECT count(*) AS total_events,
 count(*) FILTER(WHERE status='scheduled' AND start_time>%s) AS upcoming_events,
 count(*) FILTER(WHERE status='completed') AS completed_events,count(*) FILTER(WHERE status='cancelled') AS cancelled_events,
 coalesce(sum(total_registrations),0) AS total_registrations,coalesce(sum(active_registrations),0) AS active_registrations,
 coalesce(sum(attended),0) AS attended,coalesce(sum(cancelled_registrations),0) AS cancelled_registrations,
 CASE WHEN sum(occupied) FILTER(WHERE status='completed')>0 THEN
 round(100.0*sum(attended) FILTER(WHERE status='completed')/sum(occupied) FILTER(WHERE status='completed'),1) END AS attendance_rate
 FROM event_rollup;
