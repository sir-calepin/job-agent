import json
import time
from pathlib import Path

from app.llm.client import ask_llm
from app.llm.prompts import FIT_SCORER_SYSTEM


PROFILE_PATH = Path("data/processed/candidate_profile.txt")
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 2


def load_candidate_profile():
    if PROFILE_PATH.exists():
        return PROFILE_PATH.read_text(encoding="utf-8")
    return "Candidate profile not found."


def clean_json_response(raw):
    if raw is None:
        return ""

    cleaned = str(raw).strip()

    if cleaned.startswith("```json"):
        cleaned = cleaned[len("```json"):].strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned[len("```"):].strip()

    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].strip()

    return cleaned


def default_score(reason):
    return {
        "fit_score": 0.0,
        "matched_skills": [],
        "reason": reason,
    }


def score_job(job):
    profile = load_candidate_profile()

    user_prompt = f"""
{profile}

Job title: {job.title}
Company: {job.company}
Location: {job.location}
Description:
{job.description}

Return ONLY valid JSON.
Do not add markdown.
Do not add explanation outside JSON.

Schema:
{{
  "fit_score": 0,
  "matched_skills": ["skill1", "skill2"],
  "reason": "short explanation"
}}
"""

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw = ask_llm(FIT_SCORER_SYSTEM, user_prompt)
            cleaned = clean_json_response(raw)
            parsed = json.loads(cleaned)

            fit_score = parsed.get("fit_score", 0)
            try:
                fit_score = float(fit_score)
            except Exception:
                fit_score = 0.0

            matched_skills = parsed.get("matched_skills", [])
            if not isinstance(matched_skills, list):
                matched_skills = [str(matched_skills)]

            reason = parsed.get("reason", "")
            if not isinstance(reason, str):
                reason = str(reason)

            return {
                "fit_score": fit_score,
                "matched_skills": matched_skills,
                "reason": reason.strip(),
            }

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                print(
                    f"[SCORER] attempt {attempt}/{MAX_RETRIES} failed for "
                    f"{getattr(job, 'url', '')}: {e}. Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                print(
                    f"[SCORER] failed after {MAX_RETRIES} attempts for "
                    f"{getattr(job, 'url', '')}: {e}"
                )

    return default_score(f"Scoring failed after retries: {last_error}")