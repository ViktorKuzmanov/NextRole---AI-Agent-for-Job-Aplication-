"""Data models shared by the graph nodes and the store."""

from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["ai_engineer", "blockchain_developer", "skip"]


class JobPosting(BaseModel):
    id: str  # "<ats>:<company>:<job id>", stable across runs
    source: str  # greenhouse | lever | ashby
    company: str
    title: str
    location: str = ""
    url: str
    apply_url: str = ""
    description: str = ""


class Classification(BaseModel):
    """The LLM's verdict on one posting (structured output schema)."""

    role: Role = Field(
        description="Which of my target roles this posting is, or 'skip' if neither fits."
    )
    fit_score: int = Field(
        description="0-100: how well my profile fits the posting's actual requirements."
    )
    reason: str = Field(description="One or two sentences justifying role and score.")


class ClassifiedJob(BaseModel):
    job: JobPosting
    classification: Classification


class Application(BaseModel):
    job: JobPosting
    classification: Classification
    cover_letter: str
    # prepared = dry run, nothing sent. submitted = actually sent to the company.
    status: Literal["prepared", "submitted", "failed"] = "prepared"
    submitted: dict = Field(default_factory=dict)  # exactly what was/would be sent
