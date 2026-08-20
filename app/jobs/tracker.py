import json

from app.db.sqlite_db import get_connection


print("SAVE_JOB VERSION: ON CONFLICT + SAFE CLOSE")


def save_job(job, score_result):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass

        matched_skills = score_result.get("matched_skills", [])
        if not isinstance(matched_skills, str):
            matched_skills = json.dumps(matched_skills)

        cur.execute(
            """
            INSERT INTO jobs (
                title,
                company,
                location,
                url,
                description,
                posted_at,
                fit_score,
                matched_skills,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO NOTHING
            """,
            (
                job.title,
                job.company,
                job.location,
                job.url,
                job.description,
                job.posted_at,
                score_result.get("fit_score", 0),
                matched_skills,
                "new",
            ),
        )

        inserted = cur.rowcount > 0
        conn.commit()
        return inserted

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()


def fetch_jobs():
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass

        rows = cur.execute(
            """
            SELECT id, title, company, location, posted_at, fit_score, matched_skills, status, url
            FROM jobs
            ORDER BY id DESC
            """
        ).fetchall()

        return rows

    finally:
        if conn is not None:
            conn.close()


def fetch_job_by_id(job_id):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass

        row = cur.execute(
            """
            SELECT id, title, company, location, url, description, posted_at, fit_score, matched_skills, status
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

        return row

    finally:
        if conn is not None:
            conn.close()


def update_job_status(job_id, status):
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        try:
            cur.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass

        cur.execute(
            """
            UPDATE jobs
            SET status = ?
            WHERE id = ?
            """,
            (status, job_id),
        )

        updated = cur.rowcount > 0
        conn.commit()
        return updated

    except Exception:
        if conn is not None:
            conn.rollback()
        raise

    finally:
        if conn is not None:
            conn.close()