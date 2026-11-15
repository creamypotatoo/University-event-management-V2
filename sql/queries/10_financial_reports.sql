-- Runtime scoped financial aggregates; dates apply to expense_date. No registration join fanout.
-- name: finance.events
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT * FROM event_rollup ORDER BY title,event_id;
-- name: finance.clubs
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT c.club_id,c.club_name,count(e.event_id) AS event_count,coalesce(sum(e.total_expenses),0::numeric) AS total_expenses
FROM scoped_clubs c LEFT JOIN event_rollup e ON e.club_id=c.club_id GROUP BY c.club_id,c.club_name ORDER BY c.club_name,c.club_id;
-- name: finance.monthly
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT date_trunc('month',expense_date)::date AS month,sum(amount) AS total_expenses,count(*) AS expense_count
FROM filtered_expenses GROUP BY date_trunc('month',expense_date) ORDER BY month;
-- name: finance.highest
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT e.event_id,e.title,e.club_name,sum(x.amount) AS total_expenses FROM scoped_events e
INNER JOIN filtered_expenses x ON x.event_id=e.event_id GROUP BY e.event_id,e.title,e.club_name
HAVING sum(x.amount)>0 ORDER BY total_expenses DESC,e.event_id LIMIT 5;
-- name: finance.unrecorded
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT e.event_id,e.title,e.club_name FROM scoped_events e
WHERE NOT EXISTS(SELECT 1 FROM filtered_expenses x WHERE x.event_id=e.event_id) ORDER BY e.title,e.event_id;
-- name: finance.summary
WITH scoped_clubs AS (
 SELECT c.club_id,c.club_name FROM public.clubs c
 WHERE (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.club_admins a WHERE a.club_id=c.club_id AND a.user_id=%s))
 AND (%s::integer IS NULL OR c.club_id=%s)
 AND (%s::integer IS NULL OR EXISTS(SELECT 1 FROM public.events selected WHERE selected.club_id=c.club_id AND selected.event_id=%s))
), scoped_events AS (
 SELECT e.*,c.club_name FROM public.events e INNER JOIN scoped_clubs c ON c.club_id=e.club_id
 WHERE (%s::integer IS NULL OR e.event_id=%s)
), filtered_expenses AS (
 SELECT x.* FROM public.event_expenses x INNER JOIN scoped_events e ON e.event_id=x.event_id
 WHERE (%s::date IS NULL OR x.expense_date>=%s) AND (%s::date IS NULL OR x.expense_date<=%s)
), expense_totals AS (
 SELECT event_id,count(*) AS expense_count,sum(amount) AS total_expenses,
 avg(amount) AS average_expense,min(amount) AS minimum_expense,max(amount) AS maximum_expense
 FROM filtered_expenses GROUP BY event_id
), event_rollup AS (
 SELECT e.event_id,e.club_id,e.title,e.club_name,coalesce(x.expense_count,0) AS expense_count,
 coalesce(x.total_expenses,0::numeric) AS total_expenses,x.average_expense,x.minimum_expense,x.maximum_expense
 FROM scoped_events e LEFT JOIN expense_totals x ON x.event_id=e.event_id
)
SELECT coalesce(sum(total_expenses),0::numeric) AS total_expenses,coalesce(sum(expense_count),0) AS expense_count,count(*) AS event_count FROM event_rollup;
