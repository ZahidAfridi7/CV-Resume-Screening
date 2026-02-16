# CV Resume Screening System — Architecture

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT (Next.js)                                │
│  Upload CVs │ JD Input │ Results Table │ Filtering │ Analytics Dashboard     │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API GATEWAY (FastAPI)                                 │
│  JWT Auth │ Rate Limiting │ Request Validation │ CORS                        │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                                    │
                    ▼                                    ▼
┌──────────────────────────────┐    ┌──────────────────────────────────────────┐
│   Sync API (upload metadata,  │    │   Celery Workers (async)                  │
│   JD submit, ranked results,  │    │   • Extract text (PDF/DOCX)               │
│   auth, analytics)            │    │   • Normalize & embed                     │
└──────────────────────────────┘    │   • Store in PostgreSQL + pgvector        │
                    │                └──────────────────────────────────────────┘
                    │                                    │
                    ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector  │  Redis (Celery broker + result backend)             │
└─────────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  OpenAI API (embeddings only — text-embedding-3-small)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Frontend**: Next.js SPA; talks to FastAPI via Axios; React Query for cache/refetch.
- **Backend**: FastAPI with clean layers: routers → services → repositories. No LLM calls; embeddings only.
- **Processing**: Upload returns immediately; Celery tasks process files (extract → normalize → embed → store). JD submission triggers embedding + pgvector similarity query; results are returned synchronously (single vector op is fast).
- **Data**: PostgreSQL for resumes, job descriptions, batches, users; pgvector for embedding column; Redis for Celery.

---

## 2. Database Schema Design

### Tables

| Table | Purpose |
|-------|--------|
| `users` | JWT auth: email, hashed password, created_at |
| `upload_batches` | One per bulk upload: id, user_id, created_at, status (pending/processing/completed/failed) |
| `resumes` | One per CV: id, batch_id, filename, extracted_text (nullable), embedding (vector), status, created_at, file_size, error_message |
| `job_descriptions` | JD submissions: id, user_id, title, raw_text, embedding (vector), created_at |
| `screening_runs` | One per “rank CVs for this JD” run: id, jd_id, batch_id (optional), created_at |
| `screening_results` | Ranked results: id, run_id, resume_id, similarity_score, rank_position |

### pgvector

- **Embedding model**: OpenAI `text-embedding-3-small` (1536 dimensions).
- **Index**: IVFFlat or HNSW on `resumes.embedding` and `job_descriptions.embedding` for fast similarity search.
- **Similarity**: Cosine distance `<=>`; score = `1 - (embedding <=> :jd_vector)`.

### Entity Relationship (conceptual)

```
users 1──* upload_batches
users 1──* job_descriptions
upload_batches 1──* resumes
job_descriptions 1──* screening_runs
screening_runs 1──* screening_results *──1 resumes
```

---

## 3. File Tree Structure

```
CV-Resume-Screening/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── v1/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── router.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── uploads.py
│   │   │   │   ├── job_descriptions.py
│   │   │   │   ├── screening.py
│   │   │   │   └── analytics.py
│   │   ├── deps.py
│   │   ├── schemas/
│   │   │   ├── auth.py
│   │   │   ├── uploads.py
│   │   │   ├── job_descriptions.py
│   │   │   ├── screening.py
│   │   │   └── analytics.py
│   │   ├── models/
│   │   │   └── ...
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── extraction/
│   │   │   ├── embedding/
│   │   │   └── ranking/
│   │   └── core/
│   │       ├── security.py
│   │       └── text_normalizer.py
│   ├── celery_app.py
│   ├── tasks/
│   │   └── process_resume.py
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   └── ...
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── docs/
    ├── ARCHITECTURE.md
    └── API.md
```

---

## 4. API Contract Summary

- **Auth**: `POST /api/v1/auth/register`, `POST /api/v1/auth/login` → JWT.
- **Upload**: `POST /api/v1/uploads/batch` (multipart: files[] + optional batch_name) → `{ batch_id, status: "pending" }`.
- **Batches**: `GET /api/v1/uploads/batches` (paginated), `GET /api/v1/uploads/batches/{id}`.
- **JD**: `POST /api/v1/job-descriptions` (title, raw_text) → `{ id, ... }`; `GET /api/v1/job-descriptions` (paginated).
- **Screening**: `POST /api/v1/screening/rank` (jd_id, batch_id?, limit?, min_score?) → `{ run_id, results: [{ resume_id, similarity_score, rank_position, ... }] }`; `GET /api/v1/screening/runs` (paginated).
- **Analytics**: `GET /api/v1/analytics/dashboard` (batch_id?, jd_id?, date_from?, date_to?) → aggregates for dashboard.

All list endpoints support `page`, `page_size`; protected routes use `Authorization: Bearer <token>`.

---

## 5. Deployment Strategy

- **Local**: `docker-compose up` (app, celery worker, celery beat if needed, PostgreSQL, Redis). Run migrations; seed optional.
- **Production**: Same stack; scale Celery workers horizontally; use managed PostgreSQL (e.g. RDS) with pgvector; Redis (ElastiCache or equivalent); env-based config (DATABASE_URL, REDIS_URL, OPENAI_API_KEY, JWT_SECRET); reverse proxy (e.g. Nginx) in front of FastAPI.

---

## 6. Scalability Considerations

- **10k CVs/day**: Celery with multiple workers; chunk uploads (e.g. 100 files per batch) to avoid timeouts; queue per priority if needed.
- **pgvector**: HNSW index for low-latency similarity at scale; tune `ef_search` and index build parameters.
- **API**: Stateless FastAPI; horizontal scaling behind a load balancer; rate limiting per user/IP.
- **File storage**: Store files in object storage (S3/MinIO); DB holds metadata and vector only; workers read from object storage.

---

## 7. Security Considerations

- **Auth**: JWT with short expiry; refresh token optional; password hashing (bcrypt).
- **Input**: Validate file types (PDF/DOCX) and size limits; sanitize JD text length; parameterized queries only.
- **Secrets**: DATABASE_URL, OPENAI_API_KEY, JWT_SECRET in env; never in code.
- **CORS**: Restrict to frontend origin in production.
- **Rate limiting**: Per-user and per-IP to prevent abuse.
