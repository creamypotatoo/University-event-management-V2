"""Load trusted, named SQL statements; values always travel separately."""
from functools import lru_cache
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'sql' / 'queries'


@lru_cache(maxsize=1)
def statements():
    result = {}
    for path in sorted(ROOT.glob('*.sql')):
        parts = re.split(r'^-- name: ([a-z][a-z0-9_.]+)\s*$', path.read_text(encoding='utf-8'), flags=re.M)
        for name, body in zip(parts[1::2], parts[2::2]):
            if name in result or not body.strip():
                raise ValueError('Duplicate or empty SQL statement: ' + name)
            result[name] = body.strip().rstrip(';')
    return result


def load(name):
    return statements()[name]


def execute(conn, name, params=(), *, one=False):
    with conn.cursor() as cursor:
        cursor.execute(load(name), params)
        if cursor.description is None:
            return None
        return cursor.fetchone() if one else cursor.fetchall()


def read(name, params=(), *, one=False):
    from .db import transaction
    with transaction() as conn:
        return execute(conn, name, params, one=one)
