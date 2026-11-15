import re

EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",re.ASCII)
STUDENT_NUMBER = re.compile(r'[A-Za-z0-9][A-Za-z0-9/_-]{2,39}',re.ASCII)
PROFILE_FIELDS=[('full_name','Full name',150),('department','Department',100),('batch','Batch',30)]
CLUB_FIELDS=[('club_name','Club name',150),('description','Description',5000)]
VENUE_FIELDS=[('venue_name','Venue name',150),('location','Location',255),('capacity','Capacity',10)]
REGISTER_FIELDS=[('full_name','Full name',150),('email','Email',254),('student_number','Student number',40),('department','Department',100),('batch','Batch',30)]


def valid_email(value):
    if len(value)>254 or EMAIL.fullmatch(value) is None:
        return False
    local,domain=value.rsplit('@',1)
    return len(local)<=64 and not local.startswith('.') and not local.endswith('.') and '..' not in local and all(len(label)<=63 for label in domain.split('.'))


def valid_password(value):
    return 12<=len(value)<=128 and not value.isspace() and all(c.isprintable() for c in value)


def fields(form,spec):
    values={name:form.get(name,'').strip() for name,_,_ in spec}
    errors={}
    for name,label,maximum in spec:
        value=values[name]
        if not 1<=len(value)<=maximum or not all(c.isprintable() or (name=='description' and c in '\n\r\t') for c in value):
            errors[name]=f'{label}: enter 1 to {maximum} printable characters.'
    return values,errors


def registration(form):
    values,errors=fields(form,REGISTER_FIELDS)
    values['email']=values['email'].lower()
    if not valid_email(values['email']): errors['email']='Enter a valid email address.'
    if STUDENT_NUMBER.fullmatch(values['student_number']) is None: errors['student_number']='Use 3 to 40 letters/numbers, slash, underscore or hyphen.'
    if not valid_password(form.get('password','')): errors['password']='Use a passphrase of 12 to 128 printable characters.'
    if form.get('password')!=form.get('confirm_password'): errors['confirm_password']='Passwords must match.'
    return values,errors


def venue(form):
    values,errors=fields(form,VENUE_FIELDS)
    raw=values['capacity']
    if not raw.isascii() or not raw.isdigit() or len(raw)>10 or not 1<=int(raw)<=2147483647:
        errors['capacity']='Capacity must be a whole number from 1 to 2147483647.'
    return values,errors
