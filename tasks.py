"""Background tasks. Currently: order confirmation email.

Two execution modes, both going through the same task function:

- A real Celery worker (separate process, `celery -A celery_app worker`)
  picks this up off Redis, with no Flask request or app context of its own —
  it builds one Flask app once per worker process (_get_worker_app, cached)
  and reuses it for every task that process handles.
- Eager mode (celery_app.py sets this when no broker is configured) runs the
  task function inline, inside the web request that called `.delay()`, which
  already has an app context — pushing a second one would be redundant and
  wrong, so the task checks `has_app_context()` first and reuses what's there.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText

from flask import has_app_context

from celery_app import celery_app
from db import db

logger = logging.getLogger("niche.tasks")

_worker_app = None


def _get_worker_app():
    """Build the Flask app once per worker process, not once per task."""
    global _worker_app
    if _worker_app is None:
        from app import create_app

        _worker_app = create_app()
    return _worker_app


class EmailSender:
    def send(self, to, subject, body):
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    """Default backend: log instead of send. Safe with no SMTP configured —
    which is the state of this project today — and useful in development
    regardless, since it never fails and never depends on network access."""

    def send(self, to, subject, body):
        logger.info("EMAIL to=%s subject=%r\n%s", to, subject, body)


class SMTPEmailSender(EmailSender):
    def __init__(self, host, port, username, password, use_tls=True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

    def send(self, to, subject, body):
        message = MIMEText(body)
        message["Subject"] = subject
        message["From"] = self.username or "no-reply@niche.local"
        message["To"] = to

        with smtplib.SMTP(self.host, self.port, timeout=10) as server:
            if self.use_tls:
                server.starttls()
            if self.username:
                server.login(self.username, self.password)
            server.sendmail(message["From"], [to], message.as_string())


def _build_sender():
    host = os.getenv("SMTP_HOST")
    if not host:
        return ConsoleEmailSender()
    return SMTPEmailSender(
        host=host,
        port=int(os.getenv("SMTP_PORT", "587")),
        username=os.getenv("SMTP_USERNAME", ""),
        password=os.getenv("SMTP_PASSWORD", ""),
        use_tls=os.getenv("SMTP_USE_TLS", "true").lower() != "false",
    )


def _send_order_confirmation(order_id):
    from models import OrderModel

    order = db.session.get(OrderModel, order_id)
    if order is None:
        logger.warning("send_order_confirmation_email: order %s no longer exists", order_id)
        return

    user = order.user
    if not user or not user.email:
        logger.info(
            "send_order_confirmation_email: %s has no email on file, skipping",
            order.reference,
        )
        return

    item_name = order.item.name if order.item else "your item"
    body = (
        f"Hi {user.username},\n\n"
        f"Your order {order.reference} has been placed.\n"
        f"{order.quantity} x {item_name} — total {order.total}\n\n"
        f"We'll notify you as it moves through preparation and delivery."
    )
    _build_sender().send(user.email, f"Order confirmed: {order.reference}", body)


@celery_app.task(
    name="niche.send_order_confirmation_email",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def send_order_confirmation_email(self, order_id):
    if has_app_context():
        try:
            _send_order_confirmation(order_id)
        except Exception:  # noqa: BLE001
            logger.exception(
                "send_order_confirmation_email failed for order %s (eager mode, not retrying)",
                order_id,
            )
        return

    app = _get_worker_app()
    with app.app_context():
        try:
            _send_order_confirmation(order_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("send_order_confirmation_email failed for order %s", order_id)
            raise self.retry(exc=exc)
