# Docker Guide for the AMCOS Project

All commands are run in PowerShell from the project root: `C:\Users\VISTAR\Projects\NextJs\AMCOS`.
Docker Desktop must be running (whale icon in the system tray).

## 1. Concepts

| Term | What it is | In this project |
|---|---|---|
| **Docker** | A tool that runs software in isolated boxes with everything it needs (OS libraries, Python/Node, dependencies). | Everyone runs the exact same Postgres 17, Python 3.12 and Node 22, regardless of what's installed on the PC. |
| **Image** | A read-only *template*, like a class or an installer. Built from a Dockerfile or downloaded. | `postgres:17-alpine` (downloaded), `amcos-backend`, `amcos-frontend` (built by us). |
| **Container** | A *running instance* of an image, like an object created from a class. Disposable. | `amcos-db-1`, `amcos-backend-1`, `amcos-frontend-1`. |
| **Dockerfile** | Step-by-step recipe to build an image. | `backend/Dockerfile`, `frontend/Dockerfile`. |
| **Docker Compose** | Describes several containers and how they connect, in one file, started with one command. | `docker-compose.yml` |
| **Volume** | Storage managed by Docker that lives *outside* containers, so data survives when containers are deleted. | `amcos_pgdata` holds the PostgreSQL files. |
| **Bind mount** | A folder from your PC mapped into a container. | `./backend:/app` — you edit code in VS Code, the container sees it instantly and reloads. |
| **Network** | A private virtual network; containers on it find each other by service name. | `amcos_net`: backend reaches Postgres at host `db`. |
| **Port publishing** | `"8000:8000"` = PC port : container port. Lets your browser reach a container. | 5173 frontend, 8000 backend, 5432 database. |

### How the three containers talk
```
Browser ──localhost:5173──▶ frontend ──http://backend:8000──▶ backend ──db:5432──▶ db ──▶ volume amcos_pgdata
```
Inside a container, `localhost` means *that container*. That's why `DATABASE_URL` uses `db`, and the Vite proxy uses `backend`.

### Local vs Docker
- **Local:** you install Python, Node and PostgreSQL on Windows yourself; versions differ between machines; "works on my machine" problems.
- **Docker:** only Docker is needed; one command starts the whole system identically everywhere, and it is close to how a server would run it.

### Reading the Dockerfile (backend)
```dockerfile
FROM python:3.12-slim          # start from an official image with Python
WORKDIR /app                   # all following commands run in /app
COPY requirements.txt .        # copy only the dependency list first...
RUN pip install -r requirements.txt   # ...so this slow step is CACHED until requirements change
COPY . .                       # then copy the code
CMD ["uvicorn", ...]           # what runs when a container starts
```

### Database persistence
Postgres writes its files to `/var/lib/postgresql/data` *inside* the container, which we map to the named volume `amcos_pgdata`. Deleting/recreating the container doesn't touch the volume, so your data stays.

## 2. Everyday commands

| Command | What it does / when to use |
|---|---|
| `docker compose up --build` | Build images (if changed) and start everything, logs in this terminal. Ctrl+C stops. Use after changing a Dockerfile or `requirements.txt`/`package.json`. |
| `docker compose up -d` | Start in the background ("detached"). Terminal stays free. |
| `docker compose ps` | List the project's containers and their status/health. |
| `docker compose logs -f` | Follow logs of all services (Ctrl+C stops following, not the containers). |
| `docker compose logs -f backend` | Logs of one service only. First place to look when something breaks. |
| `docker compose restart backend` | Restart one service (e.g. after editing `.env`; note: `.env` changes need `up -d` to recreate). |
| `docker compose up -d --build backend` | Rebuild and recreate only the backend. |
| `docker compose exec backend pytest` | Run a command inside the running backend container (here: the tests). |
| `docker compose exec backend bash` | Open a shell inside the backend container. `exit` to leave. |
| `docker compose exec db psql -U amcos -d amcos_db` | Open the PostgreSQL shell. Try `\dt` (list tables), `\q` (quit). |
| `docker compose stop` | Stop containers, keep them. |
| `docker compose down` | Stop **and remove** containers and the network. **Data in the volume is kept.** Safe. |
| `docker compose down -v` | ⚠️ Also removes **named volumes** → **permanently deletes the local database**. Only use when you deliberately want an empty database, and back up first. |

Code changes: Python and React code reload automatically (bind mounts). You only need `--build` when dependencies or a Dockerfile change.

## 3. Migrations (from Phase 3)
```powershell
docker compose exec backend alembic upgrade head        # apply all migrations
docker compose exec backend alembic downgrade -1        # roll back the last one
docker compose exec backend alembic revision --autogenerate -m "describe change"
```

## 4. Backup and restore
```powershell
# Backup (creates backups\amcos_YYYYMMDD.sql on your PC)
New-Item -ItemType Directory -Force backups | Out-Null
docker compose exec -T db pg_dump -U amcos -d amcos_db --clean --if-exists > "backups\amcos_$(Get-Date -Format yyyyMMdd).sql"

# Restore (overwrites current data with the backup!)
Get-Content "backups\amcos_20261122.sql" | docker compose exec -T db psql -U amcos -d amcos_db
```
Replace `amcos` / `amcos_db` if you changed `POSTGRES_USER` / `POSTGRES_DB` in `.env`.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `failed to connect to the docker API ... dockerDesktopLinuxEngine` | Docker Desktop isn't running. Start it and wait until it says "Engine running". |
| `port is already allocated` (5432/8000/5173) | Another program uses that port (often a locally installed PostgreSQL). Stop it, or change the left number in `ports:` e.g. `"5433:5432"`. |
| Backend keeps restarting / `connection refused` to db | `docker compose logs db` — check credentials. If you changed `POSTGRES_PASSWORD` *after* the volume was first created, Postgres keeps the old password (the variables only apply on first initialization). |
| `password authentication failed` | `.env` `DATABASE_URL` password must match `POSTGRES_PASSWORD`. |
| A container shows `Exited` | `docker compose logs <service>` shows the error; fix, then `docker compose up -d`. |
| Frontend shows "Backend unreachable" | `docker compose ps` — is backend up? Open http://localhost:8000/api/v1/health directly. |
| Weird state after dependency changes | `docker compose up -d --build` (rebuild). |
