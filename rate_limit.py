"""Shared rate limiter.

Defined in its own module so resource blueprints can decorate routes without
importing the application factory (which would be circular).

Note the storage backend: the default is in-process memory, which under
gunicorn means each worker counts separately — an N-worker deploy effectively
multiplies every limit by N. Set RATELIMIT_STORAGE_URI to a Redis URL in
production to make limits global.
"""

import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
    # Nothing is limited unless a route opts in via @limiter.limit(...).
    default_limits=[],
)
