-- STANDALONE READ-ONLY examples for pgAdmin Query Tool / psql.
-- Connect to university_events_raw. These are NOT auto-executed by Flask.
-- Runtime equivalents are named in sql/queries/09 through 12.
BEGIN READ ONLY;
DO $$ BEGIN
 IF current_database()<>'university_events_raw' THEN RAISE EXCEPTION 'Wrong database'; END IF;
END $$;
-- INNER multi-table JOIN: venue/club labels without copying them into events.
SELECT e.event_id,e.title,c.club_name,v.venue_name,e.start_time
FROM public.events e INNER JOIN public.clubs c ON c.club_id=e.club_id
INNER JOIN public.venues v ON v.venue_id=e.venue_id ORDER BY e.start_time,e.event_id LIMIT 20;
-- LEFT JOIN and exact aggregates: include events without expenses.
SELECT e.event_id,e.title,count(x.expense_id) AS expense_count,coalesce(sum(x.amount),0::numeric) AS total_expenses,
 avg(x.amount) AS average_expense,min(x.amount) AS minimum_expense,max(x.amount) AS maximum_expense
FROM public.events e LEFT JOIN public.event_expenses x ON x.event_id=e.event_id GROUP BY e.event_id ORDER BY total_expenses DESC,e.event_id;
-- CTEs, CASE, COALESCE: child tables grouped separately to prevent join fanout.
WITH money AS (SELECT event_id,sum(amount) AS total FROM public.event_expenses GROUP BY event_id),
seats AS (SELECT event_id,count(*) AS registrations,sum(CASE WHEN status IN ('registered','attended') THEN 1 ELSE 0 END) AS occupied
 FROM public.registrations GROUP BY event_id)
SELECT e.event_id,e.title,coalesce(m.total,0::numeric) AS total_expenses,coalesce(s.registrations,0) AS total_registrations,
 coalesce(s.occupied,0) AS occupied,round(100.0*coalesce(s.occupied,0)/e.capacity,1) AS occupancy_pct
FROM public.events e LEFT JOIN money m ON m.event_id=e.event_id LEFT JOIN seats s ON s.event_id=e.event_id ORDER BY e.event_id;
-- HAVING answers a useful question: which clubs incurred strictly positive costs?
SELECT c.club_id,c.club_name,sum(x.amount) AS total_expenses FROM public.clubs c
INNER JOIN public.events e ON e.club_id=c.club_id INNER JOIN public.event_expenses x ON x.event_id=e.event_id
GROUP BY c.club_id,c.club_name HAVING sum(x.amount)>0 ORDER BY total_expenses DESC,c.club_id LIMIT 5;
-- Correlated NOT EXISTS: events missing expense records, useful for cost review.
SELECT e.event_id,e.title FROM public.events e
WHERE NOT EXISTS(SELECT 1 FROM public.event_expenses x WHERE x.event_id=e.event_id) ORDER BY e.event_id;
-- EXISTS and a correlated seat-count subquery: upcoming events and their current seat usage.
SELECT c.club_id,c.club_name FROM public.clubs c WHERE EXISTS(
 SELECT 1 FROM public.events e WHERE e.club_id=c.club_id AND e.status='scheduled' AND e.start_time>current_timestamp);
SELECT e.event_id,e.title,(SELECT count(*) FROM public.registrations r WHERE r.event_id=e.event_id AND r.status IN ('registered','attended')) AS occupied
FROM public.events e ORDER BY occupied DESC,e.event_id LIMIT 5;
-- Monthly expenses use expense_date; participation uses start_time AT TIME ZONE 'Asia/Dhaka'.
SELECT date_trunc('month',expense_date)::date AS month,sum(amount) AS total_expenses
FROM public.event_expenses GROUP BY date_trunc('month',expense_date) ORDER BY month;
COMMIT;
