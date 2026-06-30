# PowerSys SaaS

A power-system analysis SaaS for consulting engineers, built on
[pandapower](https://www.pandapower.org/), Flask, Celery, and Socket.IO.

The flagship feature is **grid-feasibility analysis** for proposed
factories and data centres: given a candidate site (lat/lon) and a
load (MW), the platform finds the nearest utility substations,
estimates available headroom, voltage drop, and short-circuit comfort,
and returns a *feasible / feasible-with-upgrade / not-feasible* verdict
plus a ranked candidate list.

The platform also supports the standard pandapower analyses:

- AC / DC load flow with violation extraction
-Successfully validated using the 
**IEEE 9-Bus** and **IEEE 14-Bus** benchmark systems.
  - Correctly identifies voltage limit violations, line       loading violations, and network convergence status.
  - IEEE 9-Bus simulations converged successfully with all operating parameters within permissible limits.
  - IEEE 14-Bus simulations successfully detected bus overvoltage conditions (up to **1.09 p.u.**) and generated structured warning reports.
  - Successfully detected transmission line overloads (e.g., **112.25% loading**) and highlighted constraint violations in simulation reports.
  - Results include bus voltages, line loading percentages, transformer loading, active/reactive power flows, and downloadable PDF reports.
- IEC 60909 short-circuit analysis
- N-1 contingency scanning
- Optimal power flow
- Quasi-static time-series simulation

Results are streamed to the browser over Socket.IO and can be
exported as PDF or Excel reports.

> Built as an engineering portfolio project. Not production-validated.
> See `docs/` for architecture notes and limitations.

---

## Architecture

```
┌────────┐    HTTPS    ┌──────────┐    Redis     ┌────────┐
│ Client │────────────▶│   Web    │─────────────▶│ Worker │
└────────┘             │ (Flask)  │              │(Celery)│
   ▲   ▲               │          │              │        │
   │   │   Socket.IO   │          │              │        │
   │   └───────────────┤          │              │        │
   │                   └────┬─────┘              └───┬────┘
   │                        │                        │
   │                        ▼                        ▼
   │                  ┌─────────────┐         ┌──────────────┐
   └──── /reports ────│ PostgreSQL  │         │ pandapower   │
                      └─────────────┘         └──────────────┘
```

Code lives in domain packages: `Models/`, `Routes/`, `Services/`,
`Tasks/`, `Schemas/`, `Utils/`, `Sockets/`, `Tests/`.

---

## Quick start (Docker)

```bash
git clone https://github.com/YOUR_ORG/powersys
cd powersys
cp .env.example .env          # edit secrets
make up                       # postgres, redis, web, worker, beat
make seed                     # plans + IEEE networks + dev admin
```

App is at <http://localhost:5000/api/health>. Default admin:
`admin / Password1!`.

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app main create-db
flask --app main seed-db
make dev          # http://localhost:5000
# In a second terminal:
make worker
```

---

## API at a glance

| Area          | Verb  | Path                                            |
| ------------- | ----- | ----------------------------------------------- |
| Auth          | POST  | `/api/auth/register`, `/login`, `/logout`       |
| Networks      | CRUD  | `/api/networks/...` + element sub-CRUD          |
| Substations   | CRUD  | `/api/substations/`, `/nearby`, `/import-osm`   |
| Facilities    | CRUD  | `/api/facilities/...`                           |
| Feasibility   | POST  | `/api/facilities/<id>/feasibility`              |
| Analyses      | POST  | `/api/analyses/load-flow` `/short-circuit` …    |
| Reports       | CRUD  | `/api/reports/`, `/<id>/download`               |
| Admin         | GET   | `/api/admin/stats`, `/audit-logs`               |

Run `flask --app main routes-list` to print everything.

---

## Development

```bash
make test          # pytest
make lint          # ruff
make format        # ruff + black
make reset-db      # drop, recreate, reseed
```

Migrations use Alembic via Flask-Migrate:

```bash
flask db migrate -m "add new column"
flask db upgrade
```

---

## Deployment

Two free targets are pre-configured:

- **Fly.io** — `flyctl deploy --remote-only` (see `infra/fly.toml`)
- **Render** — apply `infra/render.yaml` as a Blueprint

For self-hosting, `docker compose --profile production up -d` brings
up nginx in front of the app stack with SSL terminated at the proxy.

---

## Licence

MIT. Pandapower is BSD-3.
