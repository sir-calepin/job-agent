import re
from datetime import datetime, timedelta, timezone

from app.config import MATCH_THRESHOLD
from app.services.feed_discovery import fetch_feed_jobs
from app.jobs.scorer import score_job
from app.jobs.tracker import save_job
from app.notifications.telegram_bot import send_telegram_message


LOUISVILLE_AREA_KEYWORDS = {
    "louisville, ky",
    "louisville ky",
    "louisville metro",
    "jeffersonville, in",
    "jeffersonville in",
    "new albany, in",
    "new albany in",
    "clarksville, in",
    "clarksville in",
    "st. matthews, ky",
    "st. matthews ky",
    "st matthews, ky",
    "st matthews ky",
    "saint matthews, ky",
    "saint matthews ky",
    "lyndon, ky",
    "lyndon ky",
    "jeffersontown, ky",
    "jeffersontown ky",
    "shepherdsville, ky",
    "shepherdsville ky",
    "newburg, ky",
    "newburg ky",
    "okolona, ky",
    "okolona ky",
    "shively, ky",
    "shively ky",
    "prospect, ky",
    "prospect ky",
    "crestwood, ky",
    "crestwood ky",
    "la grange, ky",
    "la grange ky",
    "mount washington, ky",
    "mount washington ky",
}

US_STATE_NAMES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york",
    "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode island", "south carolina", "south dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west virginia", "wisconsin", "wyoming", "district of columbia"
}

US_STATE_ABBREVIATIONS = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
}

RECENT_HOURS = 24

NON_US_HINTS = {
    "canada", "ontario", "toronto", "vancouver",
    "united kingdom", "uk", "england", "scotland", "wales", "london",
    "ireland", "europe", "european union", "emea",
    "apac", "asia pacific", "india", "germany", "france", "spain",
    "australia", "new zealand", "singapore", "philippines",
    "mexico", "brazil", "argentina", "colombia"
}

REMOTE_TERMS = [
    "remote",
    "work from home",
    "wfh",
    "telecommute",
    "telecommuting",
    "distributed",
    "home-based",
]

EXPLICIT_US_TERMS = [
    "united states",
    "u.s.",
    "u.s.a.",
    "usa",
    "us-based",
    "u.s.-based",
    "based in the us",
    "based in the u.s.",
    "anywhere in the us",
    "anywhere in the u.s.",
    "anywhere in the united states",
    "remote - united states",
    "remote, united states",
    "remote us",
    "remote, us",
    "remote within the us",
    "must reside in the us",
    "must be based in the us",
    "eligible to work in the us",
    "authorized to work in the us",
    "united states only",
    "u.s. only",
    "us only",
]

STATE_RESTRICTION_PATTERNS = [
    "remote - ",
    "remote in ",
    "remote within ",
    "remote from ",
    "must reside in ",
    "must be located in ",
    "must live in ",
    "must be based in ",
    "eligible states",
    "hiring in ",
    "available in the following states",
    "open to candidates in ",
    "candidates must live in ",
]


def normalize_text(*parts):
    text = " ".join(str(part or "") for part in parts).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_us_state_reference(text):
    padded = f" {text.upper()} "
    if any(f" {abbr} " in padded for abbr in US_STATE_ABBREVIATIONS):
        return True
    return any(state in text for state in US_STATE_NAMES)


def is_recent_job(posted_at):
    if not posted_at:
        return True

    try:
        value = str(posted_at).strip()
        if not value:
            return True

        if value.isdigit():
            timestamp = int(value)
            if timestamp > 10_000_000_000:
                timestamp = timestamp / 1000
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            normalized = value.replace("Z", "+00:00")
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)
        return dt >= cutoff
    except Exception as e:
        print(f"[DISCOVERY DEBUG] failed to parse posted_at={posted_at!r}: {e}")
        return True


def is_us_remote(location_text, description_text=""):
    combined = normalize_text(location_text, description_text)

    has_remote = any(term in combined for term in REMOTE_TERMS)
    if not has_remote:
        return False

    if any(term in combined for term in EXPLICIT_US_TERMS):
        return True

    if any(term in combined for term in NON_US_HINTS):
        return False

    if any(pattern in combined for pattern in STATE_RESTRICTION_PATTERNS) and has_us_state_reference(combined):
        return True

    if "remote" in combined and has_us_state_reference(combined):
        return True

    return False


def is_louisville_area_job(location_text, description_text=""):
    combined = normalize_text(location_text, description_text)

    if any(keyword in combined for keyword in LOUISVILLE_AREA_KEYWORDS):
        return True

    if "louisville" in combined and ("ky" in combined or "kentucky" in combined):
        return True

    return False


def run_job_discovery():
    discovered_jobs = fetch_feed_jobs()

    discovered_total = len(discovered_jobs)
    missing_url_total = 0
    unique_total = 0
    recent_total = 0
    preferred_total = 0
    processed_total = 0
    inserted_total = 0
    skipped_total = 0
    alerted_total = 0
    results = []

    seen_urls = set()
    unique_jobs = []

    for job in discovered_jobs:
        url = str(getattr(job, "url", "") or "").strip()
        if not url:
            missing_url_total += 1
            continue
        if url in seen_urls:
            skipped_total += 1
            continue
        seen_urls.add(url)
        unique_jobs.append(job)

    unique_total = len(unique_jobs)

    for job in unique_jobs:
        location = getattr(job, "location", "") or ""
        description = getattr(job, "description", "") or ""
        posted_at = getattr(job, "posted_at", None)

        if not is_recent_job(posted_at):
            continue
        recent_total += 1

        if not (is_us_remote(location, description) or is_louisville_area_job(location, description)):
            continue
        preferred_total += 1

        score_result = score_job(job)
        inserted = save_job(job, score_result)
        processed_total += 1

        if inserted:
            inserted_total += 1
        else:
            skipped_total += 1

        alerted = False
        if inserted and score_result.get("fit_score", 0) >= MATCH_THRESHOLD:
            message = (
                f"High-match discovered job!\n"
                f"Title: {getattr(job, 'title', '')}\n"
                f"Company: {getattr(job, 'company', '')}\n"
                f"Location: {location}\n"
                f"Fit score: {score_result.get('fit_score', 0)}\n"
                f"URL: {getattr(job, 'url', '')}"
            )
            try:
                send_telegram_message(message)
                alerted = True
                alerted_total += 1
            except Exception as e:
                print(f"[DISCOVERY] Telegram alert failed for {getattr(job, 'url', '')}: {e}")

        results.append({
            "job": job,
            "score": score_result,
            "inserted": inserted,
            "alerted": alerted,
        })

    summary = {
        "discovered_total": discovered_total,
        "missing_url_total": missing_url_total,
        "unique_total": unique_total,
        "recent_total": recent_total,
        "preferred_total": preferred_total,
        "processed_total": processed_total,
        "inserted_total": inserted_total,
        "skipped_total": skipped_total,
        "alerted_total": alerted_total,
        "results": results,
    }

    print(
        f"Discovered: {discovered_total} | "
        f"Missing URL: {missing_url_total} | "
        f"Unique: {unique_total} | "
        f"Recent: {recent_total} | "
        f"Preferred location: {preferred_total} | "
        f"Processed: {processed_total} | "
        f"New: {inserted_total} | "
        f"Duplicates skipped: {skipped_total} | "
        f"Alerts sent: {alerted_total}"
    )

    return summary