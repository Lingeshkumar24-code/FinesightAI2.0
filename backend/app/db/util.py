from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.engine import Row
from sqlalchemy.orm import DeclarativeBase


def as_dict(obj) -> dict:
    if isinstance(obj, Row):
        data = dict(obj._mapping)
    elif isinstance(obj, DeclarativeBase):
        data = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    elif isinstance(obj, dict):
        data = dict(obj)
    else:
        data = {}
    return {
        key: value.isoformat() if isinstance(value, (datetime, date)) else value
        for key, value in data.items()
    }


def iso(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)
