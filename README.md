# AMCOS Produce Intake & Farmer Payment Tracking System

Docs: [Architecture](docs/ARCHITECTURE.md) · [Docker guide](docs/DOCKER_GUIDE.md)

## Running locally without Docker (current setup)

The backend runs in a Python virtual environment and uses the hosted Neon PostgreSQL
database `amcos_db` (configured in `backend/.env`, which Git ignores).

```powershell
cd C:\Users\VISTAR\Projects\NextJs\AMCOS\backend
.\.venv\Scripts\Activate.ps1            # activate the virtual environment (prompt shows (.venv))

alembic upgrade head                     # apply database migrations
python -m scripts.bootstrap              # sync roles & permissions (safe to repeat)
python -m scripts.seed_dev               # DEV ONLY: demo AMCOS, centres, crops, users, farmers
python -m scripts.set_password manager@demo.amcos.test   # choose a password for a user
python -m scripts.create_admin --email you@example.org --name "Your Name"   # real admin

uvicorn app.main:app --reload            # API at http://localhost:8000/docs
pytest                                   # run tests
```

Frontend (second terminal):
```powershell
cd C:\Users\VISTAR\Projects\NextJs\AMCOS\frontend
npm run dev                              # http://localhost:5173
```

## Testing offline mode (PWA)

The service worker only exists in a **production build** (in `npm run dev` it is
disabled so code changes appear immediately). To test offline behaviour:

```powershell
cd C:\Users\VISTAR\Projects\NextJs\AMCOS\frontend
npm run build
npm run preview          # http://localhost:4173 (proxies /api to the backend on :8000)
```

1. Open http://localhost:4173, log in as a clerk, open **Record delivery** once (this caches centres, crops and farmers).
2. DevTools (F12) → **Network** → set throttling to **Offline** (or stop the backend).
3. Reload: the app still opens; the header shows **Offline**.
4. Record a delivery: you get an `OFF-XXXX-0001` receipt; **Sync status** shows it as *Waiting to upload*.
5. Set Network back to **No throttling**: within seconds the record becomes *On server* with an official receipt number.

What the device stores and the offline security model are documented in
[docs/ARCHITECTURE.md §6](docs/ARCHITECTURE.md) and at the top of `frontend/src/offline/db.ts`.

## SMS notifications

`SMS_PROVIDER=mock` (the default) records every message as **simulated** — nothing is sent
to phones. Numbers ending in `000` simulate a failure so the retry path can be tested.
To connect a real gateway, add a class implementing `SmsProvider` in
`backend/app/integrations/sms/` using the provider's documented API and credentials
(kept in `.env`), register it in `get_provider()`, then set `SMS_PROVIDER` accordingly.
Messages are queued in the same transaction as the delivery/payment and sent after commit.

## Migration commands
```powershell
alembic revision --autogenerate -m "describe change"   # after editing models; REVIEW the file
alembic upgrade head                                    # apply
alembic downgrade -1                                    # undo last migration (drops its tables/data!)
alembic history                                         # list migrations
```

## Switching to Docker later
Run `docker compose up --build` from the project root. Inside Docker the backend
uses the `DATABASE_URL` from the root `.env` (the local `db` container); `backend/.env`
is only used when running without Docker.
