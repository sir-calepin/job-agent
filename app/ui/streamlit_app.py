from pathlib import Path
import sys
import json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app.config import MATCH_THRESHOLD
from app.db.sqlite_db import init_db
from app.jobs.manual_input import create_manual_job
from app.jobs.scorer import score_job
from app.jobs.tracker import save_job, fetch_jobs, fetch_job_by_id, update_job_status
from app.llm.drafting import draft_cover_letter
from app.notifications.telegram_bot import send_telegram_message
from app.services.discovery_service import run_job_discovery

st.set_page_config(page_title="AI Job Agent", layout="wide")
init_db()

if "drafts" not in st.session_state:
    st.session_state["drafts"] = {}

if "last_discovery_summary" not in st.session_state:
    st.session_state["last_discovery_summary"] = None

st.title("AI Job Discovery and Application Agent")
st.write("Discover jobs, score fit, receive Telegram alerts, and draft application materials.")

st.subheader("Add Job Manually")

with st.form("manual_job_form"):
    source = st.text_input("Source", value="manual")
    title = st.text_input("Job Title")
    company = st.text_input("Company")
    location = st.text_input("Location")
    url = st.text_input("Job URL")
    posted_at = st.text_input("Posted At")
    description = st.text_area("Job Description", height=200)

    submitted = st.form_submit_button("Score and Save Job")

    if submitted:
        if not title.strip() or not company.strip() or not url.strip():
            st.error("Job Title, Company, and Job URL are required.")
        else:
            clean_source = source.strip()
            clean_title = title.strip()
            clean_company = company.strip()
            clean_location = location.strip()
            clean_url = url.strip()
            clean_posted_at = posted_at.strip()
            clean_description = description.strip()

            job = create_manual_job(
                clean_source,
                clean_title,
                clean_company,
                clean_location,
                clean_url,
                clean_description,
                clean_posted_at,
            )
            score_result = score_job(job)
            inserted = save_job(job, score_result)

            if inserted:
                st.success(f"Saved job with fit score {score_result.get('fit_score', 0)}")
            else:
                st.warning("This job already exists and was skipped as a duplicate.")

            st.json(score_result, expanded=False)

            if inserted and score_result.get("fit_score", 0) >= MATCH_THRESHOLD:
                msg = (
                    f"High-match manual job saved!\n"
                    f"Title: {clean_title}\n"
                    f"Company: {clean_company}\n"
                    f"Location: {clean_location}\n"
                    f"Fit score: {score_result.get('fit_score', 0)}\n"
                    f"URL: {clean_url}"
                )
                send_telegram_message(msg)

if st.button("Run Job Discovery"):
    with st.spinner("Discovering and scoring jobs...", show_time=True):
        summary = run_job_discovery()
    st.session_state["last_discovery_summary"] = summary

discovery_summary = st.session_state["last_discovery_summary"]

if discovery_summary:
    st.subheader("Discovery Results")
    st.success(
    f"Discovered: {discovery_summary.get('discovered_total', 0)} | "
    f"Missing URL: {discovery_summary.get('missing_url_total', 0)} | "
    f"Unique: {discovery_summary.get('unique_total', 0)} | "
    f"Recent: {discovery_summary.get('recent_total', 0)} | "
    f"Preferred location: {discovery_summary.get('preferred_total', 0)} | "
    f"Processed: {discovery_summary.get('processed_total', 0)} | "
    f"New: {discovery_summary.get('inserted_total', 0)} | "
    f"Duplicates skipped: {discovery_summary.get('skipped_total', 0)} | "
    f"Alerts sent: {discovery_summary.get('alerted_total', 0)}"
)

    preview_data = []
    for item in discovery_summary.get("results", [])[:10]:
        job = item.get("job")
        score = item.get("score", {})
        preview_data.append(
            {
                "title": getattr(job, "title", ""),
                "company": getattr(job, "company", ""),
                "location": getattr(job, "location", ""),
                "fit_score": score.get("fit_score", 0),
                "inserted": item.get("inserted", False),
                "url": getattr(job, "url", ""),
            }
        )

    if preview_data:
        st.json(preview_data, expanded=False)

st.subheader("Tracked Jobs")

jobs = fetch_jobs()

if not jobs:
    st.info("No tracked jobs yet. Add one manually or run job discovery.")
else:
    min_score = st.slider(
        "Minimum fit score to display",
        min_value=0,
        max_value=100,
        value=int(MATCH_THRESHOLD),
        step=5,
    )

    show_limit = st.selectbox(
        "Jobs to display",
        [10, 25, 50, 100, 250],
        index=1,
    )

    filtered_jobs = [row for row in jobs if (row[5] or 0) >= min_score]
    jobs_to_show = filtered_jobs[:show_limit]

    st.caption(
        f"Showing {len(jobs_to_show)} of {len(filtered_jobs)} jobs "
        f"with fit score >= {min_score}. Total tracked jobs: {len(jobs)}."
    )

    if not jobs_to_show:
        st.warning("No tracked jobs match the current score filter.")
    else:
        for row in jobs_to_show:
            job_id, title, company, location, posted_at, fit_score, matched_skills, status, url = row

            with st.expander(f"{title} | {company} | Score: {fit_score}"):
                st.write(f"Location: {location}")
                st.write(f"Posted at: {posted_at or 'Unknown'}")
                st.write(f"Status: {status}")

                parsed_skills = matched_skills
                try:
                    parsed_skills = json.loads(matched_skills) if matched_skills else []
                except Exception:
                    pass

                if isinstance(parsed_skills, list):
                    st.write("Matched skills:", ", ".join(parsed_skills) if parsed_skills else "None")
                else:
                    st.write(f"Matched skills: {parsed_skills}")

                if url:
                    st.markdown(f"[Open Job Posting]({url})")

                if st.button(f"Draft Cover Letter for Job {job_id}", key=f"draft_{job_id}"):
                    with st.spinner("Drafting cover letter...", show_time=True):
                        job_row = fetch_job_by_id(job_id)
                        if job_row:
                            _, t, c, loc, u, desc, p, fs, ms, s = job_row
                            st.session_state["drafts"][job_id] = draft_cover_letter(t, c, desc)

                if job_id in st.session_state["drafts"]:
                    st.text_area(
                        "Cover Letter Draft",
                        st.session_state["drafts"][job_id],
                        height=300,
                        key=f"draft_box_{job_id}"
                    )

                status_options = ["new", "saved", "applied", "interviewing", "rejected"]
                current_index = status_options.index(status) if status in status_options else 0

                with st.form(key=f"status_form_{job_id}"):
                    new_status = st.selectbox(
                        f"Update status for job {job_id}",
                        status_options,
                        index=current_index,
                        key=f"status_{job_id}"
                    )

                    status_submitted = st.form_submit_button("Save Status")

                    if status_submitted:
                        updated = update_job_status(job_id, new_status)
                        if updated:
                            st.success(f"Status updated to: {new_status}")
                        else:
                            st.warning("No status update was applied.")
                        st.rerun()