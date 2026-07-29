from pydantic import BaseModel

class JobPosting(BaseModel):
    source: str
    title: str
    company: str = "Unknown"
    location: str = "Unknown"
    url: str
    description: str = ""
    posted_at: str = ""