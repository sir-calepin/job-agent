from app.llm.client import ask_llm
from app.llm.prompts import COVER_LETTER_SYSTEM

from pathlib import Path

def load_candidate_profile():
    path = Path("data/processed/candidate_profile.txt")
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "Candidate profile not found."

profile = load_candidate_profile()

def draft_cover_letter(job_title: str, company: str, description: str):
    user_prompt = f"""
{profile}

Draft a tailored cover letter for this role.

Job title: {job_title}
Company: {company}
Job description:
{description}
"""
    return ask_llm(COVER_LETTER_SYSTEM, user_prompt)