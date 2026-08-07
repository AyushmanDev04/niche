"""Celery application object.

Import-time configuration only — no Flask app is built here. Building one
eagerly would mean every process that imports this module (including the web
process, just to call `.delay()`) pays the cost of constructing a full Flask
app, and if CELERY_BROKER_URL/REDIS_URL aren't set yet (e.g. in production
before Redis is provisioned — see README), it needs to degrade rather than
fail to import at all.
"""

import os

from celery import Celery

BROKER_URL = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL")

celery_app = Celery(
    "niche",
    broker=BROKER_URL or "memory://",
    include=["tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=BROKER_URL is None,
    task_eager_propagates=False,
    broker_connection_retry_on_startup=True,
)
