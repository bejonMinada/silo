# Backend

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Environment

Configuration is environment-driven:

- `APP_ENV` (`development` | `test` | `production`)
- `DATABASE_URL` (defaults to `sqlite:///./silo.db`)
- `JWT_SECRET_KEY` (required non-default in production)
- `COMPANY_DOMAIN`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `CORS_ALLOWED_ORIGINS` (comma-separated)
- `MAX_REQUEST_BODY_BYTES`
- `RATE_LIMIT_REQUESTS_PER_MINUTE`
- `RATE_LIMIT_WINDOW_SECONDS`
- `CREATE_SCHEMA_ON_STARTUP` (defaults to true outside production)
- `ENABLE_SEED_ENDPOINT` (defaults to true outside production)

Example:

```bash
export APP_ENV=development
export JWT_SECRET_KEY=local-dev-secret-key
export CORS_ALLOWED_ORIGINS=http://localhost:5173
uvicorn app.main:app --reload
```

## Notes

- Schema auto-creation is controlled by `CREATE_SCHEMA_ON_STARTUP`; disable it in production and run migrations as part of deployment.
- `/api/seed` is admin-protected and should be disabled in production with `ENABLE_SEED_ENDPOINT=false`.
