from app.jobs.schemas import JobPosting

def create_manual_job(source, title, company, location, url, description, posted_at=""):
    return JobPosting(
        source=source or "manual",
        title=title,
        company=company,
        location=location,
        url=url,
        description=description,
        posted_at=posted_at
    )