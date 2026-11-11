# Ant Design Pro Admin API

FastAPI backend for the admin console (users, settings, attachments, notifications).

Local development uses **PostgreSQL 18.6** on `127.0.0.1:5433` (Homebrew `postgresql@18`). PostgreSQL 16 on 5432 is left untouched for other projects.

## Run

```bash
cd backend
uv sync
createdb -p 5433 ant_design_pro_admin 2>/dev/null || true
psql -p 5433 -d ant_design_pro_admin -f scripts/migrate_20261110_user_profile.sql
cp .env.example .env
uv run uvicorn app.main:app --reload --port 9000
```

OpenAPI: http://127.0.0.1:9000/docs

The first start creates tables and seeds demo data. Existing databases must run `scripts/migrate_20261110_user_profile.sql` once for the user profile/department/role fields. For production, switch to Alembic migrations and PostgreSQL managed service.

## Auth

- `POST /api/v1/auth/login` -> JWT access token + HttpOnly refresh cookie.
- `GET /api/v1/auth/me` -> user, tenant, roles, permissions.
- Demo accounts: `admin / ant.design` (admin), `lisi / Antd@123456` (operator).
- Set a strong `JWT_SECRET` and `COOKIE_SECURE=true` before production.

## API prefix

All endpoints are under `/api/v1`. The frontend dev proxy forwards `/api/v1` to `http://127.0.0.1:9000`.
