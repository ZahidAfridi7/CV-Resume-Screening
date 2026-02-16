"""
Ranking: compute cosine similarity between JD embedding and resume embeddings.
Uses pgvector <=> (cosine distance); similarity = 1 - distance.
"""
import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class RankingService:
    """Rank resumes by similarity to a JD embedding."""

    @staticmethod
    async def rank_resumes(
        session: AsyncSession,
        jd_embedding: list[float],
        batch_id: UUID | None = None,
        limit: int = 50,
        min_score: float | None = None,
    ) -> list[tuple[UUID, str, float, int, UUID]]:
        """
        Return list of (resume_id, filename, similarity_score, rank_position, batch_id).
        Uses cosine distance: 1 - (embedding <=> :jd_vector).
        """
        if not jd_embedding:
            logger.warning("Empty JD embedding, returning no results")
            return []

        logger.info(
            "rank_resumes: batch_id=%s limit=%s min_score=%s embedding_dim=%d",
            batch_id, limit, min_score, len(jd_embedding),
        )

        # Diagnostic: count resumes by criteria to help debug empty results
        diag_sql = text("""
            SELECT
                (SELECT COUNT(*) FROM resumes) AS total,
                (SELECT COUNT(*) FROM resumes WHERE status = 'processed') AS processed,
                (SELECT COUNT(*) FROM resumes WHERE embedding IS NOT NULL) AS with_embedding,
                (SELECT COUNT(*) FROM resumes WHERE status = 'processed' AND embedding IS NOT NULL) AS eligible
        """)
        diag_result = await session.execute(diag_sql)
        diag_row = diag_result.fetchone()
        logger.info(
            "Resume counts: total=%d processed=%d with_embedding=%d eligible=%d",
            diag_row[0], diag_row[1], diag_row[2], diag_row[3],
        )
        if batch_id:
            batch_count_sql = text(
                "SELECT COUNT(*) FROM resumes WHERE batch_id = :bid AND status = 'processed' AND embedding IS NOT NULL"
            )
            batch_result = await session.execute(batch_count_sql, {"bid": str(batch_id)})
            in_batch = batch_result.scalar() or 0
            logger.info("Resumes in batch %s (processed+embedding): %d", batch_id, in_batch)

        # pgvector: <=> is cosine distance; 1 - distance = similarity
        # Filter: status = 'processed', embedding IS NOT NULL; optional batch_id
        embedding_str = "[" + ",".join(str(x) for x in jd_embedding) + "]"

        batch_filter = "AND r.batch_id = :batch_id" if batch_id else ""
        min_score_filter = "AND (1 - (r.embedding <=> CAST(:embedding AS vector))) >= :min_score" if min_score is not None else ""

        sql = text(f"""
            SELECT r.id, r.filename, (1 - (r.embedding <=> CAST(:embedding AS vector))) AS similarity, r.batch_id
            FROM resumes r
            WHERE r.status = 'processed'
              AND r.embedding IS NOT NULL
              {batch_filter}
              {min_score_filter}
            ORDER BY r.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)
        params: dict = {
            "embedding": embedding_str,
            "limit": limit,
        }
        if batch_id:
            params["batch_id"] = str(batch_id)
        if min_score is not None:
            params["min_score"] = min_score

        result = await session.execute(sql, params)
        rows = result.fetchall()
        logger.info("Query returned %d rows", len(rows))

        out: list[tuple[UUID, str, float, int, UUID]] = []
        for rank_pos, (resume_id, filename, similarity, bid) in enumerate(rows, start=1):
            sim_float = float(similarity) if isinstance(similarity, Decimal) else similarity
            out.append((resume_id, filename, sim_float, rank_pos, bid))
            logger.debug("CV #%d: id=%s file=%s score=%.4f", rank_pos, resume_id, filename, sim_float)
        return out
