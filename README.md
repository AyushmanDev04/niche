# Niche

A two-sided marketplace: a REST API (Flask + flask-smorest + SQLAlchemy) with a
role-aware console served from `static/`.

## Accounts

Registration picks a side, and the choice is permanent.

| | Customer | Shopkeeper | Admin |
| --- | --- | --- | --- |
| Browse and order | ✅ | ❌ | ❌ |
| Write reviews | ✅ | ❌ | ❌ |
| Open stores, sell items | ❌ | ✅ | ✅ |
| Read customer reviews | own only | own stores | all |
| Ban users, read activity log | ❌ | ❌ | ✅ |

Two rules drive the split:

- **Only customers review.** A shopkeeper rating the catalogue they compete in
  would distort it, so the endpoint rejects them — including for rival stores.
  Admins are excluded too: they moderate the marketplace rather than take part.
- **Customers cannot sell.** They cannot create stores or items, and cannot be
  added as store workers (which would otherwise be a way around the rule).

Shopkeepers get a read-only view of their feedback at
`GET /store/<id>/review`: every comment with its author, the mean rating as a
float, the 1–5 distribution, and a per-item breakdown. `average_rating` and
`review_count` are also returned inline on items and stores.

`is_admin` is a flag rather than a third role, so an admin also carries an
underlying role. `flask bootstrap-admin` creates admins as shopkeepers.

## Running locally

```bash
cp .env.example .env         # then fill in the secrets
python -c "import secrets; print(secrets.token_urlsafe(32))"   # for each key

docker compose up --build
docker compose exec web flask db upgrade
docker compose exec web flask bootstrap-admin    # optional, needs ADMIN_* vars
```

The console is at http://localhost:5000, the OpenAPI docs at
http://localhost:5000/api-docs/swagger-ui.

Without Docker:

```bash
pip install -r requirements.txt
flask db upgrade
flask run
```

## Tests

```bash
pytest
```

The suite runs on SQLite by default. To run it against PostgreSQL — which
matters, because SQLite does not enforce foreign keys and so cannot reproduce
the cascade-delete bugs — point it at a throwaway database:

```bash
TEST_DATABASE_URL=postgresql://postgres:pw@localhost:5432/nichetest pytest
```

## Deploying

Schema changes are owned by Alembic. Do not call `db.create_all()`: it creates
tables without stamping `alembic_version`, after which every later
`flask db upgrade` fails against tables that already exist.

Set as the release/pre-deploy command:

```bash
flask db upgrade && flask bootstrap-admin
```

### Required environment variables

| Variable | Notes |
| --- | --- |
| `JWT_SECRET_KEY` | Required. The app refuses to boot without it. |
| `SECRET_KEY` | Required. |
| `DATABASE_URL` | Defaults to local SQLite. |
| `CORS_ORIGINS` | Comma-separated allowed browser origins. |
| `GOOGLE_CLIENT_ID` | Optional, enables Google sign-in. |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Optional, used by `flask bootstrap-admin`. |
| `RATELIMIT_STORAGE_URI` | Optional Redis URL. Without it each gunicorn worker counts rate limits separately. |

The container binds `$PORT` (default 5000), which is what Render and most
other platforms inject.

## Security notes

- Only `static/` is web-reachable. Never set `static_folder="."` — that serves
  the entire project root, including `.env`.
- `.env` must never be committed. `.env.example` documents the shape instead.
- Debug mode belongs in `.flaskenv` (development only). The Werkzeug debugger
  is remote code execution if it is ever reachable in production.
