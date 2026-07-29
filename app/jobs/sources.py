from app.jobs.schemas import JobPosting

def load_sample_jobs():
    return [
        JobPosting(
            source="manual",
            title="Data Analyst",
            company="University Example",
            location="Louisville, KY",
            url="https://example.com/job1",
            description="Looking for a Data Analyst with SQL, Python, dashboarding, reporting, and higher education analytics experience.",
            posted_at="2026-07-28 01:00"
        ),
        JobPosting(
            source="manual",
            title="Business Analyst",
            company="AgriTech Insights",
            location="Remote",
            url="https://example.com/job2",
            description="Seeking a Business Analyst with analytics, stakeholder communication, Excel, Tableau, and process improvement skills.",
            posted_at="2026-07-28 01:20"
        )
    ]