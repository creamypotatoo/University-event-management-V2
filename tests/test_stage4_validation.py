import csv
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
import pytest
from werkzeug.exceptions import Forbidden
from types import SimpleNamespace
from app.report_validation import expense_input
from app.csv_export import safe_cell,csv_response
from app.report_queries import scope


@pytest.mark.parametrize('amount',['','-1','+1','1e2','NaN','Infinity','1,000','1.001','10000000000','9999999999.999','??','1.','.' ])
def test_invalid_amounts(amount):
    _,display,errors=expense_input(dict(description='Expense',amount=amount,expense_date='2026-01-01'))
    assert 'amount' in errors and display['amount']==amount


@pytest.mark.parametrize('amount,expected',[('0',Decimal('0.00')),('0.01',Decimal('0.01')),('1.2',Decimal('1.20')),('9999999999.99',Decimal('9999999999.99'))])
def test_exact_amounts(amount,expected):
    values,_,errors=expense_input(dict(description='Expense',amount=amount,expense_date='2026-01-01'))
    assert not errors and values['amount']==expected and isinstance(values['amount'],Decimal)


@pytest.mark.parametrize('field,value',[('description',''),('description','x'*256),('description','bad\x00'),('expense_date','bad'),('expense_date','20260101'),('expense_date','2026-02-30')])
def test_expense_text_and_dates(field,value):
    form=dict(description='Expense',amount='1',expense_date='2026-01-01');form[field]=value
    assert field in expense_input(form)[2]


@pytest.mark.parametrize('value',['=1+1',' +SUM(A1)','-1+2','@formula','\t=1','\ntext','\ufeff=1','\uff1d1+1','\u2003=1'])
def test_csv_formula_neutralization(value):
    assert safe_cell(value)=="'"+value


def test_csv_exact_numeric_quoting_unicode_and_empty(app):
    assert safe_cell(Decimal('10.10'))=='10.10'
    assert safe_cell(None)=='' and safe_cell(12)=='12'
    assert safe_cell('Hello, world')=='Hello, world'
    with app.app_context():
        response=csv_response('fixed.csv',['description','amount'],[['Comma, "quote"\nUnicode \u09ac',Decimal('0.10')]])
    assert response.content_type=='text/csv; charset=utf-8'
    rows=list(csv.reader(StringIO(response.data.decode('utf-8'))))
    assert rows[1]==['Comma, "quote"\nUnicode \u09ac','0.10']
    assert b'\r\n' in response.data and 'attachment' in response.headers['Content-Disposition']


@pytest.mark.parametrize('role',['student','unknown'])
def test_query_scope_rejects_non_managers(role):
    with pytest.raises(Forbidden):scope(SimpleNamespace(role=role,user_id=1))


@pytest.mark.parametrize('path',['/reports','/reports/financial','/reports/analytics','/reports/financial.csv','/reports/participation.csv','/events/1/expenses','/events/1/expenses/new','/events/1/expenses/1/edit','/events/1/expenses/1/delete','/clubs/1/financial'])
def test_private_reporting_routes_redirect_anonymous(app,path):
    with patch('app.db.psycopg.connect') as connect:
        response=app.test_client().get(path)
    assert response.status_code==302 and '/auth/login' in response.location
    connect.assert_not_called()


@pytest.mark.parametrize('readonly',[True,False])
def test_report_snapshot_and_write_isolation_are_explicit(app,readonly):
    from unittest.mock import MagicMock
    import psycopg
    from app import db
    conn=MagicMock()
    with app.app_context(),patch('app.db.psycopg.connect',return_value=conn):
        with db.transaction(readonly=readonly):pass
    assert conn.isolation_level==(psycopg.IsolationLevel.REPEATABLE_READ if readonly else psycopg.IsolationLevel.READ_COMMITTED)
