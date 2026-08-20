import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st


INTEREST_INCLUDE_TERMS = [
    "data analyst",
    "data analytics",
    "analytics analyst",
    "business intelligence",
    "bi analyst",
    "reporting analyst",
    "insights analyst",
    "operations analyst",
    "research analyst",
    "market research",
    "marketing analyst",
    "product analyst",
    "sql analyst",
    "dashboard",
    "tableau",
    "power bi",
    "data quality",
    "data governance",
]

INTEREST_EXCLUDE_TERMS = [
    "software engineer",
    "senior software engineer",
    "staff engineer",
    "frontend",
    "backend",
    "full stack",
    "full-stack",
    "devops",
    "site reliability",
    "sre",
    "designer",
    "product designer",
    "recruiter",
    "sales",
    "account executive",
    "customer success",
    "attorney",
    "legal",
]


def normalize_text(*parts):
    text = " ".join(str(part or "") for part in parts).lower()
    return re.sub(r"\s+", " ", text).strip()


def is_job_of_interest(title, description=""):
    combined = normalize_text(title, description)

    if any(term in combined for term in INTEREST_EXCLUDE_TERMS):
        return False

    return any(term in combined for term in INTEREST_INCLUDE_TERMS)


def parse_posted_at(value):
    """
    Return a UTC datetime when possible.
    Return None for unknown, invalid, or relative date formats.
    """
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    lowered = text.lower()
    now = datetime.now(timezone.utc)

    if lowered in {"just posted", "today"}:
        return now

    relative_match = re.fullmatch(r"(\d+)\s*(h|d|w)\+?", lowered)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)

        if unit == "h":
            return now - timedelta(hours=amount)
        if unit == "d":
            return now - timedelta(days=amount)
        if unit == "w":
            return now - timedelta(weeks=amount)

    try:
        parsed = pd.to_datetime(text, errors="coerce", utc=True)

        if pd.isna(parsed):
            return None

        return parsed.to_pydatetime()
    except Exception:
        return None


def is_recent_posted_at(value, max_age_hours=24):
    posted_dt = parse_posted_at(value)

    # Keep jobs with unknown dates visible. Your backend already handles
    # recency more carefully, and hiding unknown dates can hide good listings.
    if posted_dt is None:
        return True

    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    return posted_dt >= cutoff


def add_job_filters_sidebar():
    st.sidebar.header("Job filters")

    show_only_relevant = st.sidebar.checkbox(
        "Only relevant jobs",
        value=True,
        help="Show data analytics, BI, research, reporting, and related roles.",
    )

    show_only_recent = st.sidebar.checkbox(
        "Only recent jobs",
        value=False,
        help="Show roles posted within the previous 24 hours when a date is available.",
    )

    hide_saved = st.sidebar.checkbox(
        "Hide saved jobs",
        value=False,
        help="Hide jobs whose status is Saved.",
    )

    role_groups = {
        "Data Analyst": [
            "data analyst",
            "data analytics",
            "analytics analyst",
        ],
        "BI / Reporting": [
            "business intelligence",
            "bi analyst",
            "reporting analyst",
            "dashboard",
            "tableau",
            "power bi",
        ],
        "Research / Insights": [
            "research analyst",
            "insights analyst",
            "market research",
            "marketing analyst",
            "product analyst",
        ],
        "Operations / Data Ops": [
            "operations analyst",
            "data quality",
            "data governance",
            "sql analyst",
        ],
    }

    selected_groups = st.sidebar.multiselect(
        "Role groups",
        options=list(role_groups.keys()),
        default=list(role_groups.keys()),
    )

    active_terms = []
    for group in selected_groups:
        active_terms.extend(role_groups[group])

    title_search = st.sidebar.text_input(
        "Title contains",
        value="",
        placeholder="Example: Power BI or research",
    )

    return {
        "show_only_relevant": show_only_relevant,
        "show_only_recent": show_only_recent,
        "hide_saved": hide_saved,
        "active_terms": active_terms,
        "title_search": title_search,
    }


def apply_job_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """
    Apply sidebar filter settings to the tracked-jobs DataFrame.

    Expected columns:
    job_id, title, company, location, posted_at, fit_score,
    matched_skills, status, url, description
    """
    if df.empty:
        return df.copy()

    result = df.copy()

    if filters.get("hide_saved") and "status" in result.columns:
        status = result["status"].fillna("").astype(str).str.lower()
        result = result[status.ne("saved")]

    if filters.get("show_only_recent") and "posted_at" in result.columns:
        recent_mask = result["posted_at"].apply(is_recent_posted_at)
        result = result[recent_mask]

    if filters.get("show_only_relevant"):
        result = result[
            result.apply(
                lambda row: is_job_of_interest(
                    row.get("title", ""),
                    row.get("description", ""),
                ),
                axis=1,
            )
        ]

    active_terms = filters.get("active_terms") or []
    if active_terms and "title" in result.columns:
        title_mask = result["title"].fillna("").astype(str).str.lower().apply(
            lambda title: any(term in title for term in active_terms)
        )
        result = result[title_mask]

    title_search = str(filters.get("title_search") or "").strip().lower()
    if title_search and "title" in result.columns:
        result = result[
            result["title"]
            .fillna("")
            .astype(str)
            .str.lower()
            .str.contains(re.escape(title_search), na=False)
        ]

    return result