"""Explicit psycopg transactions; reads default to read-only, writes opt in."""
from contextlib import contextmanager
import click
import psycopg
from psycopg.rows import dict_row
from flask import current_app


class Conflict(RuntimeError):
    pass


class DatabaseUnavailable(RuntimeError):
    pass


@contextmanager
def transaction(*, readonly=True):
    config = current_app.config
    if config['DB_NAME'] != 'university_events_raw':
        raise DatabaseUnavailable('Only university_events_raw is permitted.')
    conn = None
    try:
        conn = psycopg.connect(
            dbname=config['DB_NAME'], host=config['DB_HOST'],
            port=config['DB_PORT'], user=config['DB_USER'],
            password=config['DB_PASSWORD'], connect_timeout=config['DB_TIMEOUT'],
            row_factory=dict_row, autocommit=False,
            options=('-c default_transaction_read_only=on' if readonly else '-c default_transaction_read_only=off') + ' -c search_path=public -c statement_timeout=5000',
        )
        # Reports run several SELECTs on one stable snapshot. Seat-allocation writes
        # require READ COMMITTED so a waiter sees the winning registration.
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ if readonly else psycopg.IsolationLevel.READ_COMMITTED
        conn.read_only = readonly
        yield conn
        conn.commit()
    except psycopg.IntegrityError as exc:
        if conn is not None:
            conn.rollback()
        message = ('The venue booking conflicts with another event. Choose a different time or venue.'
                   if exc.sqlstate == '23P01' else 'Those details conflict with an existing record or database rule.')
        raise Conflict(message) from None
    except psycopg.Error as exc:
        if conn is not None:
            conn.rollback()
        if exc.sqlstate in {'40001', '40P01', '55P03'}:
            raise Conflict('Another request changed this record. Reload and try again.') from None
        current_app.logger.warning('PostgreSQL operation failed; details withheld.')
        raise DatabaseUnavailable('Database unavailable; check configuration and approved setup.') from None
    except BaseException:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


def fetch_all(statement, params=()):
    """Use %s placeholders and separate parameters, never string interpolation."""
    with transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall()


def check_connection():
    return fetch_all('SELECT current_database() AS database, 1 AS ok')[0]


def init_app(app):
    @app.cli.command('db-check')
    def db_check():
        """Read-only connection probe; never creates tables or databases."""
        try:
            row = check_connection()
        except DatabaseUnavailable as exc:
            raise click.ClickException(str(exc)) from None
        click.echo(f"Connected to {row['database']} (read-only).")
