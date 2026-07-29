import requests

from app.jobs.schemas import JobPosting

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)"
}


def parse_source(source_url):
    source_url = source_url.strip()

    if "greenhouse.io" in source_url or "boards-api.greenhouse.io" in source_url:
        return parse_greenhouse(source_url)

    if "lever.co" in source_url or "api.lever.co" in source_url or "api.eu.lever.co" in source_url:
        return parse_lever(source_url)

    raise ValueError(f"Unsupported source URL: {source_url}")


def parse_greenhouse(url):
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(5, 20))
    response.raise_for_status()

    data = response.json()
    jobs_data = data.get("jobs", []) if isinstance(data, dict) else []

    jobs = []
    for item in jobs_data:
        title = (item.get("title") or "").strip()

        location_obj = item.get("location") or {}
        location = location_obj.get("name", "").strip() if isinstance(location_obj, dict) else "Unknown"

        job_url = (item.get("absolute_url") or "").strip()
        description = item.get("content") or ""
        posted_at = item.get("updated_at") or ""
        company = extract_greenhouse_company(url)

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

    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(5, 20))
    response.raise_for_status()

    data = response.json()
    jobs_data = data if isinstance(data, list) else []

    jobs = []
    for item in jobs_data:
        categories = item.get("categories") or {}

        title = (item.get("text") or "").strip()
        location = (categories.get("location") or "Unknown").strip()
        job_url = (item.get("hostedUrl") or item.get("applyUrl") or "").strip()
        description = item.get("descriptionPlain") or item.get("description") or ""
        posted_at = str(item.get("createdAt") or item.get("updatedAt") or "")
        company = extract_lever_company(url)

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
        return "Unknown"
    except Exception:
        return "Unknown"