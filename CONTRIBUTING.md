# Contributing

Thanks for helping improve the SaaS Template. Bug fixes, docs fixes, and
small improvements can go straight to a pull request. For a new feature or a
larger change, open an issue first so we can agree on the approach.
[ROADMAP.md](ROADMAP.md) lists known gaps that are good places to start.

Security problems: please do **not** open a public issue. See
[SECURITY.md](SECURITY.md).

## Dev setup

You need Docker (with Compose v2), Node 24, and Python 3.13 (for the codegen
scripts, which run on the host).

```bash
cp .env.example .env
docker compose up --build          # the backend applies migrations on start
docker compose exec backend python scripts/seed_dev.py   # optional dev superuser
```

The frontend is at http://localhost:21427 and the API docs at
http://localhost:21428/api/docs. The README covers the other services.

## Running the checks

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs all of these
on every pull request. Run them locally before you push:

```bash
# backend (inside Docker; install dev deps as root the first time)
docker compose exec -u root backend pip install -r requirements-dev.txt
docker compose exec backend python -m pytest
docker compose exec backend ruff check . && docker compose exec backend ruff format --check .

# frontend
cd frontend && npm ci && npx tsc -b && npx eslint . && npx prettier --check . \
  && npx vitest run && npm run build
python3 scripts/validate_tours.py frontend/src

# mobile
cd mobile && npm ci && npm run typecheck && npm test

# generated artifacts must be in sync with their sources
python3 scripts/gen_errors.py --check
python3 scripts/gen_policy.py --check
python3 scripts/gen_enums.py --check
python3 scripts/gen_events.py --check
python3 scripts/gen_brand.py --check
python3 scripts/check_env_examples.py
```

## Single sources of truth

Several files are generated. Edit the source, then run the generator without
`--check` and commit both:

| Edit this | Then run |
|---|---|
| `shared/errors.toml` (error codes and copy) | `python3 scripts/gen_errors.py` |
| `shared/policy.toml` (cross-stack limits, rate limits) | `python3 scripts/gen_policy.py` |
| backend domain enums | `python3 scripts/gen_enums.py` |
| `shared/events.toml` (analytics events) | `python3 scripts/gen_events.py` |
| `shared/brand.toml` (identity, theme) | `python3 scripts/gen_brand.py` |
| a new `Settings` field | document it in an `.env` example |

Error codes are permanent: deprecate a code, never reuse or renumber it.
Generated files are excluded from Ruff and Prettier, so format the generator,
not its output.

To fix formatting automatically: `ruff format .` and `ruff check --fix .` in
`backend/`, and `npx prettier --write .` in `frontend/`.

## Code conventions

The architecture rules are written down in
[docs/conventions.md](docs/conventions.md) and in the Architecture section of
[README.md](README.md). In short:

- One feature is one vertical slice: `backend/app/domains/<name>/` with
  `domain/`, `application/`, `infrastructure/`, `interface/`, mirrored in
  `frontend/src/features/<name>/`. Dependencies point inward only.
- Tenant-scoped tables carry `organization_id`, and repositories always
  filter by it.
- Use cases never commit; the request transaction does.
- Raise `AppError` subclasses with a catalog code; don't return ad-hoc errors.
- Unit-test use cases with in-memory fakes of their ports. Add a test for
  every bug you fix.
- Migrations run inside Docker
  (`docker compose exec backend alembic revision --autogenerate -m "..."`)
  and must be expand/contract safe, because the deploy runs them while the
  old version is still serving.
- UI work follows [DESIGN.md](DESIGN.md).

## Pull requests

- Keep each PR to one topic, and explain why the change is needed.
- Include tests, and update docs when behavior or setup changes.
- Never commit secrets, real customer data, or `.env` files.
- By contributing, you agree that your contribution is licensed under the
  [MIT License](LICENSE).
