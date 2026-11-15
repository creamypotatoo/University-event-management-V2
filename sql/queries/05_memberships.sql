-- Club row must be locked before every membership transition.
-- name: memberships.mine_one
SELECT membership_id,club_id,student_id,joined_at,status FROM public.club_memberships WHERE club_id=%s AND student_id=%s;
-- name: memberships.mine
SELECT m.membership_id,m.joined_at,m.status,c.club_id,c.club_name,c.is_active
FROM public.club_memberships m JOIN public.clubs c ON c.club_id=m.club_id
WHERE m.student_id=%s ORDER BY m.joined_at DESC,m.membership_id LIMIT %s OFFSET %s;
-- name: memberships.join
INSERT INTO public.club_memberships (club_id,student_id) VALUES (%s,%s)
ON CONFLICT (club_id,student_id) DO UPDATE SET status='active' RETURNING membership_id;
-- name: memberships.leave
UPDATE public.club_memberships SET status='cancelled' WHERE club_id=%s AND student_id=%s RETURNING membership_id;
-- name: memberships.members
SELECT m.membership_id,m.status,m.joined_at,s.student_number,u.full_name
FROM public.club_memberships m JOIN public.students s ON s.student_id=m.student_id JOIN public.users u ON u.user_id=s.user_id
WHERE m.club_id=%s ORDER BY u.full_name,m.membership_id LIMIT %s OFFSET %s;
-- name: memberships.status
UPDATE public.club_memberships SET status=%s WHERE club_id=%s AND membership_id=%s RETURNING membership_id;
