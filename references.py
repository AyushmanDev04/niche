"""User-facing reference codes (ORD-9F3A2C1B, CUST-7B2E01AA).

These are NOT a hash of the row's primary key. Hashing a small sequential
integer buys nothing: with order IDs running 1, 2, 3, ..., anyone can hash
every ID up to some generous bound and build a lookup table in well under a
second — the "hash" is fully reversible by brute force, regardless of which
hash function is used. Slow hashes (bcrypt/scrypt) don't fix this either; the
input space is the problem, not the function.

The actual fix is to not derive the reference from the ID at all: generate
`secrets.token_hex(n)` — real randomness from the OS CSPRNG — and store it as
its own column.
"""

import secrets

from db import db

_TOKEN_BYTES = 4
_MAX_ATTEMPTS = 5


def _generate(prefix):
    return f"{prefix}-{secrets.token_hex(_TOKEN_BYTES).upper()}"


def generate_unique_ref(model_cls, column_name, prefix):
    """A token not currently present in `column_name` on `model_cls`.

    This is check-then-generate, not lock-then-generate: there is a
    theoretical TOCTOU race between the existence check here and the row's
    eventual INSERT. That's an acceptable trade — the UNIQUE constraint on
    the column still makes a true collision impossible to persist, it would
    just surface as an IntegrityError for the caller to retry, which callers
    of this function already handle as part of normal insert-failure recovery.
    """
    column = getattr(model_cls, column_name)
    for _ in range(_MAX_ATTEMPTS):
        token = _generate(prefix)
        exists = db.session.query(model_cls.query.filter(column == token).exists()).scalar()
        if not exists:
            return token
    raise RuntimeError(f"Could not generate a unique {prefix} reference.")
