import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.jobs.schemas import JobPosting
from app.services.generic_board_discovery import parse_generic_source, SourceDescriptor


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)"
}

GREENHOUSE_TIMEOUT = (5, 30)
LEVER_TIMEOUT = (5, 60)
ASHBY_TIMEOUT = (5, 30)
GENERIC_TIMEOUT = (8, 30)


class TimeoutSession(requests.Session):
    def __init__(self, default_timeout=(5, 30)):
        super().__init__()
        self.default_timeout = default_timeout

    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.default_timeout)
        return super().request(method, url, **kwargs)


def build_session():
    session = TimeoutSession(default_timeout=(5, 30))

    retry_strategy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=1.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "HEAD", "OPTIONS"]),
        respect_retry_after_header=True,
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


SESSION = build_session()


def parse_source(source_url):
    source_url = source_url.strip().strip('"').strip("'")

    if any(domain in source_url for domain in ["greenhouse.io", "boards-api.greenhouse.io"]):
        return parse_greenhouse(source_url)

    if any(domain in source_url for domain in ["lever.co", "api.lever.co", "api.eu.lever.co"]):
        return parse_lever(source_url)

    if any(domain in source_url for domain in ["ashbyhq.com", "api.ashbyhq.com"]):
        return parse_ashby(source_url)

    if any(domain in source_url for domain in ["indeed.com", "glassdoor.com", "welcometothejungle.com"]):
        site = detect_generic_site(source_url)
        return parse_generic_source(SourceDescriptor(source_type="generic_board", site=site, url=source_url))

    raise ValueError(f"Unsupported source URL: {source_url}")


def detect_generic_site(url):
    if "indeed.com" in url:
        return "indeed"
    if "glassdoor.com" in url:
        return "glassdoor"
    if "welcometothejungle.com" in url:
        return "wttj"
    return "generic"


def parse_greenhouse(url):
    response = SESSION.get(url, headers=DEFAULT_HEADERS, timeout=GREENHOUSE_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    jobs_data = data.get("jobs", []) if isinstance(data, dict) else []

    jobs = []
    company = extract_greenhouse_company(url)

    for item in jobs_data:
        title = (item.get("title") or "").strip()
        location_obj = item.get("location") or {}
        location = location_obj.get("name", "").strip() if isinstance(location_obj, dict) else "Unknown"
        job_url = (item.get("absolute_url") or "").strip()
        description = item.get("content") or ""
        posted_at = item.get("updated_at") or ""

        if not title or not job_url:
            continue

        jobs.append(
            JobPosting(
                source="greenhouse",
                title=title,
                company=company,
                location=location or "Unknown",
                url=job_url,
                description=description,
                posted_at=posted_at,
            )
        )

    return jobs


def parse_lever(url):
    if "mode=json" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}mode=json"

    response = SESSION.get(url, headers=DEFAULT_HEADERS, timeout=LEVER_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    jobs_data = data if isinstance(data, list) else []

    jobs = []
    company = extract_lever_company(url)

    for item in jobs_data:
        categories = item.get("categories") or {}
        title = (item.get("text") or "").strip()
        location = (categories.get("location") or "Unknown").strip()
        job_url = (item.get("hostedUrl") or item.get("applyUrl") or "").strip()
        description = item.get("descriptionPlain") or item.get("description") or ""
        posted_at = str(item.get("createdAt") or item.get("updatedAt") or "")

        if not title or not job_url:
            continue

        jobs.append(
            JobPosting(
                source="lever",
                title=title,
                company=company,
                location=location or "Unknown",
                url=job_url,
                description=description,
                posted_at=posted_at,
            )
        )

    return jobs


def parse_ashby(url):
    if "includeCompensation=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}includeCompensation=true"

    response = SESSION.get(url, headers=DEFAULT_HEADERS, timeout=ASHBY_TIMEOUT)
    response.raise_for_status()

    data = response.json()
    jobs_data = data.get("jobs", []) if isinstance(data, dict) else []

    jobs = []
    company = extract_ashby_company(url)

    for item in jobs_data:
        title = (item.get("title") or "").strip()
        location = (item.get("location") or "Unknown").strip()
        workplace_type = (item.get("workplaceType") or "").strip()
        is_remote = item.get("isRemote")
        job_url = (item.get("jobUrl") or item.get("applyUrl") or "").strip()
        description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
        posted_at = item.get("publishedAt") or ""

        if workplace_type and workplace_type.lower() == "remote" and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()

        if is_remote is True and "remote" not in location.lower():
            location = f"{location} (Remote)".strip()

        if not title or not job_url:
            continue

        jobs.append(
            JobPosting(
                source="ashby",
                title=title,
                company=company,
                location=location or "Unknown",
                url=job_url,
                description=description,
                posted_at=posted_at,
            )
        )

    return jobs


def extract_greenhouse_company(url):
    try:
        part = url.split("/boards/")[1]
        return part.split("/")[0]
    except Exception:
        return "Unknown"


def extract_lever_company(url):
    try:
        if "/postings/" in url:
            part = url.split("/postings/")[1]
            return part.split("?")[0].split("/")[0]

        if "/v0/postings/" in url:
            part = url.split("/v0/postings/")[1]
            return part.split("?")[0].split("/")[0]

        return "Unknown"
    except Exception:
        return "Unknown"


def extract_ashby_company(url):
    try:
        part = url.split("/job-board/")[1]
        return part.split("?")[0].split("/")[0]
    except Exception:
        return "Unknown"