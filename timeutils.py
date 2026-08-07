"""UTC clock helpers.

`datetime.utcnow()` is deprecated from Python 3.12 and returns a naive
datetime that only claims to be UTC. `datetime.now(timezone.utc)` is the
supported replacement, but every DateTime column here is naive — TIMESTAMP
WITHOUT TIME ZONE on PostgreSQL — and handing psycopg2 an aware value makes
PostgreSQL cast it through the session's TimeZone setting, shifting the
stored time whenever that setting is not UTC.

So these compute the time the supported way and then drop the tzinfo to match
the columns. Keeping it in one place means moving to timezone-aware columns
later is a change to this file rather than to seven models.

`timezone.utc` rather than the `datetime.UTC` alias because that alias needs
Python 3.11+ and the development virtualenv for this project is 3.9.
"""

from datetime import datetime, timezone


def utcnow():
    """Naive UTC now — the value `datetime.utcnow()` used to return."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(seconds):
    """Naive UTC from a POSIX timestamp, replacing `utcfromtimestamp`."""
    return datetime.fromtimestamp(seconds, timezone.utc).replace(tzinfo=None)
