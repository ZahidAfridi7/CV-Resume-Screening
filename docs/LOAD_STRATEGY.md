# Load Strategy for 10k CVs/day

## Target

- **10,000 CVs per day** ≈ 7 CVs/minute average, ~420/hour.
- API must not block: upload returns immediately; processing is async (Celery).

## How We Scale

1. **Celery workers**  
   - Run multiple workers: `celery -A celery_app worker -l info -c 4`.  
   - Each worker processes one task at a time; 4 workers ≈ 4x throughput.

2. **Batching**  
   - Each upload creates one batch; each file is one Celery task.  
   - For 10k/day, spread uploads (e.g. 100–500 files per batch) to avoid one huge batch; workers drain the queue.

3. **Queue depth**  
   - Redis holds the queue. Monitor queue length; add workers if it grows.

4. **PostgreSQL + pgvector**  
   - Add HNSW index on `resumes.embedding` for fast similarity at scale.  
   - Example (run in migration or manually):
     ```sql
     CREATE INDEX IF NOT EXISTS idx_resumes_embedding_hnsw ON resumes USING hnsw (embedding vector_cosine_ops);
     ```

5. **File storage**  
   - For production, store files in object storage (S3/MinIO); DB keeps only metadata and vector.  
   - Workers read from object storage by `file_path`.

## Load Simulation (10k CVs)

- **Option A – script:**  
  - Use a script to POST many batches (e.g. 100 files per request, 100 requests = 10k files).  
  - Space requests (e.g. 1 request every few seconds) to simulate a day.

- **Option B – parallel clients:**  
  - Use `locust` or `k6` to define: (1) login, (2) upload batch with N files.  
  - Ramp up to target rate and run for 24h (or a shorter run scaled to 10k).

- **Verify:**  
  - Celery queue length stays bounded.  
  - DB connections and CPU on app/Celery/PostgreSQL stay within limits.

## Edge Cases (handled in code / tests)

| Case            | Handling |
|-----------------|----------|
| Empty CV        | Extraction returns ""; normalizer returns ""; embed returns zero vector; resume marked processed or failed per policy. |
| Corrupted file  | Extraction raises `ExtractionError`; task catches, marks resume failed, stores error_message. |
| Very large JD    | Normalizer truncates to 8000 chars before embedding. |
| Duplicate CV    | No dedup by content; same file uploaded twice = two resumes. Optional: add content hash and skip or flag duplicates. |
