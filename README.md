# AI Job Discovery and Application Agent

A Streamlit-based job search assistant that discovers jobs from public feeds, filters for relevant opportunities, scores fit, stores results, sends Telegram alerts for strong matches, and drafts cover letters.

## Features

- Manual job entry with scoring and duplicate-aware saving.
- Automated job discovery from supported job board feeds.
- Filtering for recent jobs, U.S. remote roles, and Louisville-area hybrid or in-office roles.
- Fit scoring with configurable match threshold.
- Telegram notifications for high-match new jobs.
- Cover letter drafting for tracked jobs.
- SQLite-backed job tracking with status updates.
- Streamlit dashboard for discovery, review, and application workflow.

## Tech Stack

- Python
- Streamlit
- SQLite
- Pydantic
- Telegram Bot API

## Project Structure

```text
app/
├── config.py
├── db/
│   └── sqlite_db.py
├── jobs/
│   ├── manual_input.py
│   ├── parser.py
│   ├── schemas.py
│   ├── scorer.py
│   └── tracker.py
├── llm/
│   └── drafting.py
├── notifications/
│   └── telegram_bot.py
└── services/
    ├── discovery_service.py
    └── feed_discovery.py
```

## How It Works

1. Fetch jobs from configured feeds.
2. Remove duplicates and skip jobs without URLs.
3. Filter to recent jobs and preferred locations.
4. Score each job against the configured fit logic.
5. Save new jobs to SQLite.
6. Send Telegram alerts for high-match jobs.
7. Review, update status, and draft cover letters in Streamlit.

## Configuration

Set project configuration in `app/config.py` or environment variables, depending on your setup.

Typical settings include:

- `JOB_FEED_URLS`
- `MATCH_THRESHOLD`
- Telegram bot credentials
- Database path

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app/ui/streamlit_app.py
```

## Current Filters

The discovery pipeline is tuned to prioritize:

- Newly posted jobs, ideally within the last 24 hours.
- Remote roles limited to the United States.
- Hybrid or in-office roles in Louisville, KY and nearby cities.

## Roadmap

- Stronger location normalization.
- Better recency detection across job sources.
- Resume-aware scoring improvements.
- Scheduled background discovery runs.
- More source integrations.

## Notes

This project is intended to reduce job-search friction by surfacing relevant opportunities quickly so applications can be submitted early.