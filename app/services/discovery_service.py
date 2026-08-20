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

CANADA_PROVINCE_NAMES = {
    "alberta", "british columbia", "manitoba", "new brunswick",
    "newfoundland and labrador", "nova scotia", "ontario",
    "prince edward island", "quebec", "saskatchewan",
    "northwest territories", "nunavut", "yukon"
}

CANADA_PROVINCE_ABBREVIATIONS = {
    "AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"
}

CANADA_CITY_TERMS = {
    "toronto", "vancouver", "montreal", "calgary",
    "ottawa", "edmonton", "winnipeg", "halifax"
}

RECENT_HOURS = 24

REMOTE_TERMS = [
    "remote",
    "work from home",
    "wfh",
    "telecommute",
    "telecommuting",
    "distributed",
    "home-based",
]

US_ALLOW_TERMS = [
    "united states",
    "u.s.",
    "u.s.a.",
    "usa",
    "us only",
    "u.s. only",
    "united states only",
    "us-based",
    "u.s.-based",
    "based in the us",
    "based in the u.s.",
    "anywhere in the us",
    "anywhere in the u.s.",
    "anywhere in the united states",
    "remote us",
    "remote, us",
    "remote - us",
    "remote united states",
    "remote, united states",
    "remote - united states",
]

CANADA_ALLOW_TERMS = [
    "canada",
    "canadian",
    "canada only",
    "remote canada",
    "remote, canada",
    "remote - canada",
    "anywhere in canada",
    "based in canada",
    "canada-based",
]

NON_US_CANADA_TERMS = [
    "india", "poland", "warsaw", "germany", "france", "spain", "italy",
    "netherlands", "portugal", "ireland", "uk", "united kingdom", "england",
    "scotland", "wales", "london", "europe", "emea", "apac", "asia pacific",
    "singapore", "philippines", "australia", "new zealand", "mexico",
    "brazil", "argentina", "colombia", "south africa"
]

JOB_INTEREST_INCLUDE_TERMS = [
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

JOB_INTEREST_EXCLUDE_TERMS = [
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
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_token(text, token):
    pattern = rf"\b{re.escape(token.lower())}\b"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


def has_any_token(text, tokens):
    return any(has_token(text, token) for token in tokens)


def has_us_state_reference(text):
    if any(has_token(text, state) for state in US_STATE_NAMES):
        return True

    upper_text = f" {text.upper()} "
    for abbr in US_STATE_ABBREVIATIONS:
        if re.search(rf"\b{re.escape(abbr)}\b", upper_text):
            return True

    return False


def has_canada_reference(text):
    if has_any_token(text, CANADA_PROVINCE_NAMES):
        return True

    if has_any_token(text, CANADA_CITY_TERMS):
        return True

    upper_text = f" {text.upper()} "
    for abbr in CANADA_PROVINCE_ABBREVIATIONS:
        if re.search(rf"\b{re.escape(abbr)}\b", upper_text):
            return True

    return has_any_token(text, ["canada", "canadian"])


def parse_recent_age(value):
    lowered = str(value).strip().lower()
    if not lowered:
        return None

    if lowered in {"just posted", "today"}:
        return datetime.now(timezone.utc)

    m = re.fullmatch(r"(\d+)\s*(h|d|w)\+?", lowered)
    if not m:
        return None

    amount = int(m.group(1))
    unit = m.group(2)

    if unit == "h":
        return datetime.now(timezone.utc) - timedelta(hours=amount)
    if unit == "d":
        return datetime.now(timezone.utc) - timedelta(days=amount)
    if unit == "w":
        return datetime.now(timezone.utc) - timedelta(weeks=amount)
    return None


def is_recent_job(posted_at):
    if not posted_at:
        return True

    try:
        value = str(posted_at).strip()
        if not value:
            return True

        relative_dt = parse_recent_age(value)
        if relative_dt is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=RECENT_HOURS)
            return relative_dt >= cutoff

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


def is_job_of_interest(title_text, description_text=""):
    combined = normalize_text(title_text, description_text)

    if any(term in combined for term in JOB_INTEREST_EXCLUDE_TERMS):
        return False

    return any(term in combined for term in JOB_INTEREST_INCLUDE_TERMS)


def is_us_remote(location_text, description_text=""):
    combined = normalize_text(location_text, description_text)

    if not has_any_token(combined, REMOTE_TERMS):
        return False

    if has_any_token(combined, NON_US_CANADA_TERMS):
        return False

    if has_any_token(combined, US_ALLOW_TERMS):
        return True

    if has_any_token(combined, CANADA_ALLOW_TERMS):
        return True

    if has_us_state_reference(combined):
        return True

    if has_canada_reference(combined):
        return True

    return False


def is_louisville_area_job(location_text, description_text=""):
    combined = normalize_text(location_text, description_text)

    if any(keyword in combined for keyword in LOUISVILLE_AREA_KEYWORDS):
        return True

    if has_token(combined, "louisville") and (
        has_token(combined, "ky") or has_token(combined, "kentucky")
    ):
        return True

    if has_token(combined, "jeffersonville") and (
        has_token(combined, "in") or has_token(combined, "indiana")
    ):
        return True

    if has_token(combined, "new albany") and (
        has_token(combined, "in") or has_token(combined, "indiana")
    ):
        return True

    if has_token(combined, "clarksville") and (
        has_token(combined, "in") or has_token(combined, "indiana")
    ):
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
    score_failed_total = 0
    save_failed_total = 0
    filtered_interest_total = 0
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
        job_url = str(getattr(job, "url", "") or "").strip()
        title = getattr(job, "title", "") or ""

        if not is_recent_job(posted_at):
            continue
        recent_total += 1

        if not is_job_of_interest(title, description):
            filtered_interest_total += 1
            continue

        if not (is_us_remote(location, description) or is_louisville_area_job(location, description)):
            continue
        preferred_total += 1

        try:
            score_result = score_job(job)
        except Exception as e:
            print(f"[DISCOVERY] score_job failed for {job_url}: {e}")
            score_failed_total += 1
            skipped_total += 1
            continue

        try:
            inserted = save_job(job, score_result)
        except Exception as e:
            print(f"[DISCOVERY] save_job failed for {job_url}: {e}")
            save_failed_total += 1
            skipped_total += 1
            continue

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
                f"URL: {job_url}"
            )
            try:
                send_telegram_message(message)
                alerted = True
                alerted_total += 1
            except Exception as e:
                print(f"[DISCOVERY] Telegram alert failed for {job_url}: {e}")

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
        "filtered_interest_total": filtered_interest_total,
        "preferred_total": preferred_total,
        "processed_total": processed_total,
        "inserted_total": inserted_total,
        "skipped_total": skipped_total,
        "alerted_total": alerted_total,
        "score_failed_total": score_failed_total,
        "save_failed_total": save_failed_total,
        "results": results,
    }

    print(
        f"Discovered: {discovered_total} | "
        f"Missing URL: {missing_url_total} | "
        f"Unique: {unique_total} | "
        f"Recent: {recent_total} | "
        f"Interest filtered: {filtered_interest_total} | "
        f"Preferred location: {preferred_total} | "
        f"Processed: {processed_total} | "
        f"New: {inserted_total} | "
        f"Duplicates skipped: {skipped_total} | "
        f"Score failed: {score_failed_total} | "
        f"Save failed: {save_failed_total} | "
        f"Alerts sent: {alerted_total}"
    )

    return summary
