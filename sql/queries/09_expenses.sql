-- Runtime expense CRUD. Every ID is bound and ownership is checked in transaction.
-- name: expenses.detail
SELECT expense_id,event_id,description,amount,expense_date FROM public.event_expenses WHERE event_id=%s AND expense_id=%s;
-- name: expenses.lock
SELECT expense_id,event_id,description,amount,expense_date FROM public.event_expenses WHERE event_id=%s AND expense_id=%s FOR UPDATE;
-- name: expenses.create
INSERT INTO public.event_expenses (event_id,description,amount,expense_date) VALUES (%s,%s,%s,%s) RETURNING expense_id;
-- name: expenses.edit
UPDATE public.event_expenses SET description=%s,amount=%s,expense_date=%s WHERE event_id=%s AND expense_id=%s RETURNING expense_id;
-- name: expenses.delete
DELETE FROM public.event_expenses WHERE event_id=%s AND expense_id=%s RETURNING expense_id;
-- name: expenses.list
SELECT expense_id,event_id,description,amount,expense_date FROM public.event_expenses
WHERE event_id=%s AND (%s::date IS NULL OR expense_date>=%s) AND (%s::date IS NULL OR expense_date<=%s)
AND position(lower(%s) in lower(description))>0 ORDER BY expense_date DESC,expense_id LIMIT %s OFFSET %s;
-- name: expenses.total
SELECT count(*) AS expense_count,coalesce(sum(amount),0::numeric) AS total_expenses FROM public.event_expenses
WHERE event_id=%s AND (%s::date IS NULL OR expense_date>=%s) AND (%s::date IS NULL OR expense_date<=%s)
AND position(lower(%s) in lower(description))>0;
