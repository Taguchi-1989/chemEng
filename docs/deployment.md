# ChemEng Deployment Guide

This project currently supports two practical deployment patterns:

1. Render as the main Python web service
2. Vercel + external backend proxy

For the current codebase, the simplest production-style route is Render.

## Render

Render can be used in two ways.

1. Dashboard route
2. `render.yaml` route

Recommended operation:

1. Create the service once from the Render dashboard and confirm it boots correctly.
2. After the settings are confirmed, keep `render.yaml` in sync and treat it as the source of truth.

### Route 1: Render Dashboard

Create a new Web Service and use the following values.

| Setting | Value |
| --- | --- |
| Runtime | Python |
| Build Command | `pip install --upgrade pip && pip install -r requirements_full.txt && pip install -e .` |
| Start Command | `uvicorn chemeng.interface.api:app --host 0.0.0.0 --port $PORT` |
| Health Check Path | `/api` |
| Python Version | `3.10.14` |

Notes:

- The service must bind to `0.0.0.0`.
- The service must listen on Render's `$PORT`.
- `requirements_full.txt` is used so the calculation engines match the local environment more closely.

### Route 2: Blueprint / `render.yaml`

This repository already includes [`render.yaml`](/d:/dev/chemEng/render.yaml).

Use it when:

- you want reproducible infra settings in Git
- you want teammates to redeploy with the same commands
- you want to reduce dashboard drift

Current `render.yaml` behavior:

- installs `requirements_full.txt`
- installs the package with `pip install -e .`
- starts `uvicorn chemeng.interface.api:app`
- binds to `0.0.0.0`
- listens on `$PORT`
- health-checks `/api`

## Local Verification Before Deploy

Run either of the following locally:

```bash
python server.py
```

or

```bash
python -m chemeng --api
```

Then verify:

```bash
curl http://localhost:8000/api
curl http://localhost:8000/docs
```

## Render-Specific Checks

If Render deployment fails, check these first:

1. The start command is using `$PORT`, not a fixed `8000`.
2. The server is binding to `0.0.0.0`, not `127.0.0.1`.
3. The build command installs `requirements_full.txt`.
4. The health check path is `/api`.

## Vercel + External Backend

The repo still includes the Vercel proxy route in [`api/index.py`](/d:/dev/chemEng/api/index.py).

Use this route when:

- the frontend is hosted separately
- a lightweight proxy is enough on the edge
- the heavy Python backend runs elsewhere

That route depends on:

- `BACKEND_URL`
- a reachable backend server
- proxy-safe CORS settings

## Operational Recommendation

For this repository, use this order:

1. First deploy from the Render dashboard.
2. Confirm boot, health check, and static assets.
3. Keep the confirmed settings in `render.yaml`.
4. Use the Vercel proxy route only when you intentionally want split hosting.
