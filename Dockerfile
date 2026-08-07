FROM python:3.11-slim

# Don't buffer stdout — logs show up in Render/Docker immediately.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# psycopg2-binary ships wheels, but keep build tooling out of the final image.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

# Render (and most PaaS) inject the port to listen on via $PORT. The old
# hardcoded :80 ignored that, and EXPOSE said 5000 while gunicorn bound 80.
ENV PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --access-logfile - 'app:create_app()'"]
