from pathlib import Path
import sys
import json
from io import BytesIO

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.config import MATCH_THRESHOLD
from app.db.sqlite_db import init_db
from app.jobs.manual_input import create_manual_job
from app.jobs.scorer import score_job
from app.jobs.tracker import save_job, fetch_jobs, fetch_job_by_id, update_job_status
from app.llm.drafting import draft_cover_letter
from app.notifications.telegram_bot import send_telegram_message
from app.services.discovery_service import run_job_discovery
from app.services.streamlit_job_filters import add_job_filters_sidebar, apply_job_filters


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
        f"Interest filtered: {discovery_summary.get('filtered_interest_total', 0)} | "
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
    jobs_rows = []
    for row in jobs:
        job_id, title, company, location, posted_at, fit_score, matched_skills, status, url = row
        jobs_rows.append(
            {
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": location,
                "posted_at": posted_at,
                "fit_score": float(fit_score or 0),
                "matched_skills": matched_skills,
                "status": status,
                "url": url,
                "description": "",
            }
        )

    jobs_df = pd.DataFrame(jobs_rows)

    filters = add_job_filters_sidebar()
    min_score = st.sidebar.slider(
        "Minimum fit score",
        min_value=0,
        max_value=100,
        value=int(MATCH_THRESHOLD),
        step=5,
    )
    show_limit = st.sidebar.selectbox(
        "Jobs to display",
        [10, 25, 50, 100, 250],
        index=1,
    )
    filters["min_score"] = min_score
    filters["show_limit"] = show_limit

    filtered_df = apply_job_filters(jobs_df, filters)
    filtered_df = filtered_df[filtered_df["fit_score"] >= min_score]
    filtered_df = filtered_df.sort_values(by=["fit_score", "job_id"], ascending=[False, False])
    filtered_df = filtered_df.head(show_limit)

    export_df = filtered_df.drop(columns=["description"], errors="ignore")
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Export filtered jobs to CSV",
        data=csv_bytes,
        file_name="filtered-jobs.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.caption(
        f"Showing {len(filtered_df)} of {len(jobs_df)} tracked jobs "
        f"with fit score >= {min_score}."
    )

    if filtered_df.empty:
        st.warning("No tracked jobs match the current filters.")
    else:
        for _, row in filtered_df.iterrows():
            job_id = row["job_id"]
            title = row["title"]
            company = row["company"]
            location = row["location"]
            posted_at = row["posted_at"]
            fit_score = row["fit_score"]
            matched_skills = row["matched_skills"]
            status = row["status"]
            url = row["url"]

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