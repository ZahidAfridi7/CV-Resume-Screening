# CV Resume Screening System

Production-grade CV screening platform: bulk upload PDF/DOCX, one Job Description (JD), semantic similarity via embeddings (no LLM scoring), ranking, filtering, and analytics. Scales to 10k+ CVs/day.

## Stack

- **Backend:** Python 3.11, FastAPI, PostgreSQL + pgvector, SQLAlchemy (async), Alembic, Celery + Redis
- **Frontend:** Next.js (TypeScript, TailwindCSS, Axios, React Query, Recharts)
- **Embeddings:** OpenAI `text-embedding-3-small` (embeddings only)

## Quick start (local)

### 1. Environment

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY, optionally JWT_SECRET_KEY, DATABASE_URL, REDIS_URL
```

### 2. Database and migrations

```bash
cd backend
pip install -r requirements.txt
# PostgreSQL with pgvector running locally (or use Docker for DB only)
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cv_screening
alembic upgrade head
```

### 3. Run backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal, run Celery:

```bash
cd backend
celery -A celery_app worker -l info
```

### 4. Run frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Register, then upload CVs, add a Job Description, and use **Rank CVs** to see results and analytics.

---

## Run with Docker

From the repo root:

```bash
cp .env.example .env
# Set OPENAI_API_KEY (and optionally JWT_SECRET_KEY) in .env
docker compose up -d
```

This starts:

- **PostgreSQL** (pgvector) on port 5432
- **Redis** on port 6379
- **Backend** (FastAPI + migrations) on port 8000
- **Celery worker** (processes CVs)

Then run the frontend locally (so it can talk to the backend):

```bash
cd frontend && npm install && npm run dev
```

API: [http://localhost:8000](http://localhost:8000). Docs: [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Environment variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL URL with asyncpg, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis URL for Celery, e.g. `redis://localhost:6379/0` |
| `OPENAI_API_KEY` | OpenAI API key (embeddings only) |
| `JWT_SECRET_KEY` | Secret for JWT (use a long random value in production) |

See `.env.example` for a template.

---

## Tests

Backend unit tests (text normalizer, extraction, embedding, ranking):

```bash
cd backend
pip install -r requirements.txt
pytest
```

Optional: set `OPENAI_API_KEY` to run the live embedding test in `test_embedding.py`.

---

## Project layout

```
CV-Resume-Screening/
├── backend/           # FastAPI, Celery, Alembic
│   ├── app/
│   │   ├── api/v1/    # Auth, uploads, JDs, screening, analytics
│   │   ├── core/      # Security, text normalizer
│   │   ├── db/        # Session, base
│   │   ├── models/    # User, UploadBatch, Resume, JobDescription, Screening*
│   │   ├── repositories/
│   │   ├── schemas/
│   │   ├── services/  # Extraction, embedding, ranking
│   │   └── tasks/     # Celery: process_resume
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/          # Next.js (dashboard, upload, JD, rank, analytics)
├── docs/              # ARCHITECTURE.md, API.md, LOAD_STRATEGY.md, STATUS.md
├── docker-compose.yml
└── .env.example
```

---

## Production

- Use a managed PostgreSQL with pgvector (e.g. RDS, Neon) and set `DATABASE_URL`.
- Use managed Redis (e.g. ElastiCache) and set `REDIS_URL`.
- Run multiple Celery workers; scale behind a load balancer.
- Serve frontend (e.g. Vercel or same host via Nginx) and point API requests to the backend.
- Keep `JWT_SECRET_KEY` and `OPENAI_API_KEY` in env only; never commit them.

See **docs/ARCHITECTURE.md** for deployment and scalability notes, and **docs/LOAD_STRATEGY.md** for 10k CVs/day and edge cases.
