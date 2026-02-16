# API Contract — CV Resume Screening System

Base URL: `/api/v1`. All protected routes require header: `Authorization: Bearer <access_token>`.

---

## Auth

| Method | Path | Description | Body |
|--------|------|-------------|------|
| POST | `/auth/register` | Register user | `{ "email": string, "password": string }` |
| POST | `/auth/login` | Login | `{ "email": string, "password": string }` → `{ "access_token", "token_type": "bearer" }` |

---

## Uploads

| Method | Path | Description | Body / Params |
|--------|------|-------------|----------------|
| POST | `/uploads/batch` | Create batch, enqueue processing | `multipart/form-data`: `files[]` (PDF/DOCX), optional `batch_name` |
| GET | `/uploads/batches` | List batches (paginated) | Query: `page`, `page_size` |
| GET | `/uploads/batches/{batch_id}` | Get batch + resume summaries | Path: `batch_id` |

**Response (POST /uploads/batch):**  
`{ "batch_id": "uuid", "status": "pending", "file_count": number }`

---

## Job Descriptions

| Method | Path | Description | Body |
|--------|------|-------------|------|
| POST | `/job-descriptions` | Create JD | `{ "title": string, "raw_text": string }` |
| GET | `/job-descriptions` | List JDs (paginated) | Query: `page`, `page_size` |
| GET | `/job-descriptions/{jd_id}` | Get one JD | — |

---

## Screening

| Method | Path | Description | Body |
|--------|------|-------------|------|
| POST | `/screening/rank` | Rank CVs by JD | `{ "jd_id": uuid, "batch_id"?: uuid, "limit"?: number, "min_score"?: float }` |
| GET | `/screening/runs` | List screening runs (paginated) | Query: `page`, `page_size`, optional `jd_id` |
| GET | `/screening/runs/{run_id}` | Get run + results (paginated) | Query: `page`, `page_size` |

**Response (POST /screening/rank):**  
`{ "run_id": uuid, "jd_id": uuid, "results": [{ "resume_id", "similarity_score", "rank_position", "filename", ... }], "total_count": number }`

---

## Analytics

| Method | Path | Description | Query |
|--------|------|-------------|-------|
| GET | `/analytics/dashboard` | Aggregates for dashboard | `batch_id?`, `jd_id?`, `date_from?`, `date_to?` |

**Response:**  
`{ "total_resumes": number, "total_batches": number, "total_jds": number, "total_runs": number, "resumes_by_status": {...}, "uploads_by_date": [...] }`

---

## Pagination

List endpoints return:  
`{ "items": [...], "total": number, "page": number, "page_size": number, "pages": number }`

---

## Errors

- `401 Unauthorized`: Missing or invalid token.
- `422 Unprocessable Entity`: Validation error (body/query).
- `404 Not Found`: Resource not found.
- `413 Payload Too Large`: File(s) exceed size limit.
