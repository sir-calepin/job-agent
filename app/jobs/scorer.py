import json
from pathlib import Path

from app.llm.client import ask_llm
from app.llm.prompts import FIT_SCORER_SYSTEM


def load_candidate_profile():
    path = Path("data/processed/candidate_profile.txt")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Candidate profile not found."


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
    raw = ask_llm(FIT_SCORER_SYSTEM, user_prompt)

    try:
        cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        parsed["fit_score"] = float(parsed.get("fit_score", 0))
        parsed["matched_skills"] = parsed.get("matched_skills", [])
        parsed["reason"] = parsed.get("reason", "")
        return parsed
    except Exception:
        return {
            "fit_score": 0,
            "matched_skills": [],
            "reason": f"Parsing failed. Raw response: {raw}"
        }