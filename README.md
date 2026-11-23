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
