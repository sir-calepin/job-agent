import re
from dataclasses import dataclass
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from app.jobs.schemas import JobPosting


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)"
}

SEARCH_TERMS = [
    "data analyst",
    "business intelligence analyst",
    "analytics analyst",
    "reporting analyst",
    "insights analyst",
    "research analyst",
    "market research",
    "product analyst",
    "operations analyst",
]

INDEED_SEARCH_URLS = [
    f"https://www.indeed.com/jobs?q={quote_plus(term)}&l=United+States"
    for term in SEARCH_TERMS
]

GLASSDOOR_SEARCH_URLS = [
    f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(term)}&locT=C&locId=1188570&locKeyword=United%20States"
    for term in SEARCH_TERMS
]

WTTJ_SEARCH_URLS = [
    f"https://www.welcometothejungle.com/en/jobs?query={quote_plus(term)}&refinementList%5Blocations.country_code%5D%5B0%5D=US"
    for term in SEARCH_TERMS
]

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


@dataclass
class SourceDescriptor:
    source_type: str
    site: str
    url: str



def discover_generic_sources():
    sources = []

    for url in INDEED_SEARCH_URLS:
        sources.append(SourceDescriptor(source_type="generic_board", site="indeed", url=url))

    for url in GLASSDOOR_SEARCH_URLS:
        sources.append(SourceDescriptor(source_type="generic_board", site="glassdoor", url=url))

    for url in WTTJ_SEARCH_URLS:
        sources.append(SourceDescriptor(source_type="generic_board", site="wttj", url=url))

    return sources



def parse_generic_source(source):
    if source.site == "indeed":
        return parse_indeed(source.url)
    if source.site == "glassdoor":
        return parse_glassdoor(source.url)
    if source.site == "wttj":
        return parse_wttj(source.url)
    return []



def fetch_html(url):
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=(8, 30))
    response.raise_for_status()
    return response.text



def clean_text(value):
    return re.sub(r"\s+", " ", (value or "")).strip()



def absolute_url(base_url, href):
    if not href:
        return ""
    return urljoin(base_url, href)



def extract_href(card, fallback_selector=None):
    href = card.get("href") or ""
    if href:
        return href
    if fallback_selector:
        link = card.select_one(fallback_selector)
        if link:
            return link.get("href") or ""
    return ""



def is_job_of_interest(title_text, description_text=""):
    combined = clean_text(f"{title_text} {description_text}").lower()
    if any(term in combined for term in INTEREST_EXCLUDE_TERMS):
        return False
    return any(term in combined for term in INTEREST_INCLUDE_TERMS)



def _build_job(source, title, company, location, url, description="", posted_at=""):
    if not title or not url:
        return None
    if not is_job_of_interest(title, description):
        return None
    return JobPosting(
        source=source,
        title=title,
        company=company or "Unknown",
        location=location or "Unknown",
        url=url,
        description=description or "",
        posted_at=posted_at or "",
    )



def parse_indeed(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()

    cards = soup.select("a.tapItem, div.job_seen_beacon, a.jcs-JobTitle")

    for card in cards:
        title_el = card.select_one("h2, a.jcs-JobTitle, [data-testid='job-title']")
        title = clean_text(title_el.get_text(" ")) if title_el else clean_text(card.get_text(" "))
        href = extract_href(card, "a")
        job_url = absolute_url(url, href)

        if not title or not job_url or job_url in seen:
            continue

        seen.add(job_url)

        location_el = card.select_one(".companyLocation, .metadata, [data-testid='text-location']")
        company_el = card.select_one(".companyName, [data-testid='company-name']")
        date_el = card.select_one("time, .date, [data-testid='myJobsStateDate']")

        job = _build_job(
            source="indeed",
            title=title,
            company=clean_text(company_el.get_text(" ")) if company_el else "Unknown",
            location=clean_text(location_el.get_text(" ")) if location_el else "Unknown",
            url=job_url,
            description="",
            posted_at=clean_text(date_el.get_text(" ")) if date_el else "",
        )
        if job:
            jobs.append(job)

    return jobs



def parse_glassdoor(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()

    cards = soup.select("li.react-job-listing, article, a.jobLink, div.JobCard_jobCard__, div.jobCard")

    for card in cards:
        title_el = card.select_one("a, h3, [data-test='job-title'], .jobTitle")
        if not title_el:
            continue

        title = clean_text(title_el.get_text(" "))
        href = title_el.get("href") or card.get("href") or ""
        job_url = absolute_url(url, href)

        if not title or not job_url or job_url in seen:
            continue

        seen.add(job_url)

        company_el = card.select_one("[data-test='employer-name'], .employerName, .companyName")
        location_el = card.select_one("[data-test='job-location'], .location, .companyLocation")
        date_el = card.select_one("time, [data-test='job-age'], .jobAge")
        desc_el = card.select_one("[data-test='job-snippet'], .jobDescriptionContent, p")

        job = _build_job(
            source="glassdoor",
            title=title,
            company=clean_text(company_el.get_text(" ")) if company_el else "Unknown",
            location=clean_text(location_el.get_text(" ")) if location_el else "Unknown",
            url=job_url,
            description=clean_text(desc_el.get_text(" ")) if desc_el else "",
            posted_at=clean_text(date_el.get_text(" ")) if date_el else "",
        )
        if job:
            jobs.append(job)

    return jobs



def parse_wttj(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    seen = set()

    cards = soup.select("article, li, a[href*='/jobs/'], a[href*='/en/jobs/']")

    for card in cards:
        link = card if card.name == "a" else card.select_one("a[href*='/jobs/'], a[href*='/en/jobs/']")
        if not link:
            continue

        title = clean_text(link.get_text(" "))
        href = link.get("href") or ""
        job_url = absolute_url(url, href)

        if not title or not job_url or job_url in seen:
            continue

        seen.add(job_url)

        company_el = card.select_one("[data-testid='company-name'], .company, .companyName")
        location_el = card.select_one("[data-testid='job-location'], .location")
        date_el = card.select_one("time, .date")
        desc_el = card.select_one("p, .description")

        job = _build_job(
            source="wttj",
            title=title,
            company=clean_text(company_el.get_text(" ")) if company_el else "Unknown",
            location=clean_text(location_el.get_text(" ")) if location_el else "Unknown",
            url=job_url,
            description=clean_text(desc_el.get_text(" ")) if desc_el else "",
            posted_at=clean_text(date_el.get_text(" ")) if date_el else "",
        )
        if job:
            jobs.append(job)

    return jobs