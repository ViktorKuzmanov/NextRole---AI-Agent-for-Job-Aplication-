"""The NextRole LangGraph workflow.

    fetch_jobs -> prefilter -> classify -+-> apply -> record -> END
                                         |             ^
                                         +-- no match --+
"""

import operator
import re
from typing import Annotated, TypedDict

from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from . import config
from .chains import build_classifier, build_cover_letter_writer
from .models import Application, Classification, ClassifiedJob, JobPosting
from .sources import fetch_all
from .store import Store

# Cheap title screen so the LLM only reads postings that could plausibly match.
TITLE_HINT = re.compile(
    r"\b(ai|ml|llm|genai|machine learning|agent\w*|applied|nlp|prompt|"
    r"blockchain|solidity|smart contracts?|web3|protocol|crypto\w*|defi|evm)\b",
    re.IGNORECASE,
)
TITLE_ENGINEERING = re.compile(r"engineer|developer|programmer|architect", re.IGNORECASE)


class State(TypedDict, total=False):
    limit: int | None  # input: max postings to classify this run
    postings: list[JobPosting]
    candidates: list[JobPosting]
    classified: list[ClassifiedJob]
    applications: list[Application]
    errors: Annotated[list[str], operator.add]  # every node may append


def _job_inputs(job: JobPosting) -> dict:
    return job.model_dump(include={"company", "title", "location", "description"})


def build_graph(
    store: Store | None = None,
    classifier: Runnable | None = None,
    writer: Runnable | None = None,
    companies: dict[str, list[str]] | None = None,
):
    """Compile the workflow. Dependencies are injectable so tests can run the
    whole graph with fake models and no network."""
    store = store or Store(config.DB_PATH)

    def fetch_jobs(state: State) -> dict:
        postings, errors = fetch_all(companies or config.load_companies())
        return {"postings": postings, "errors": errors}

    def prefilter(state: State) -> dict:
        seen = store.seen_ids()
        candidates = [
            job
            for job in state["postings"]
            if job.id not in seen
            and TITLE_HINT.search(job.title)
            and TITLE_ENGINEERING.search(job.title)
        ]
        return {"candidates": candidates[: state.get("limit") or None]}

    def classify(state: State) -> dict:
        nonlocal classifier
        jobs = state["candidates"]
        if not jobs:
            return {"classified": []}
        classifier = classifier or build_classifier()
        results = classifier.batch(
            [_job_inputs(job) for job in jobs],
            config={"max_concurrency": 4},
            return_exceptions=True,
        )
        classified, errors = [], []
        for job, result in zip(jobs, results):
            if isinstance(result, Classification):
                classified.append(ClassifiedJob(job=job, classification=result))
            else:  # not recorded, so the next run retries it
                errors.append(f"classify {job.id}: {result!r}")
        return {"classified": classified, "errors": errors}

    def matches(state: State) -> list[ClassifiedJob]:
        return [
            item
            for item in state["classified"]
            if item.classification.role != "skip"
            and item.classification.fit_score >= config.MIN_SCORE
        ]

    def route_after_classify(state: State) -> str:
        return "apply" if matches(state) else "record"

    def apply(state: State) -> dict:
        """v1 dry run: assemble the full application package (cover letter and
        the exact form data) without sending anything to the company."""
        nonlocal writer
        writer = writer or build_cover_letter_writer()
        selected = matches(state)
        letters = writer.batch(
            [_job_inputs(item.job) for item in selected],
            config={"max_concurrency": 4},
            return_exceptions=True,
        )
        profile = config.load_profile()
        applications, errors = [], []
        for item, letter in zip(selected, letters):
            if not isinstance(letter, str):
                errors.append(f"cover letter {item.job.id}: {letter!r}")
                continue
            applications.append(
                Application(
                    job=item.job,
                    classification=item.classification,
                    cover_letter=letter,
                    status="prepared",
                    submitted={
                        "apply_url": item.job.apply_url,
                        "name": profile.get("name", ""),
                        "email": profile.get("email", ""),
                        "links": profile.get("links", {}),
                        "cv": profile.get("cv_path", ""),
                        "cover_letter": letter,
                    },
                )
            )
        return {"applications": applications, "errors": errors}

    def record(state: State) -> dict:
        applications = state.get("applications", [])
        applied_ids = {a.job.id for a in applications}
        # A match whose cover letter failed is left unrecorded so it is retried.
        failed_ids = {m.job.id for m in matches(state)} - applied_ids
        store.save(
            [c for c in state["classified"] if c.job.id not in failed_ids], applications
        )
        return {}

    graph = StateGraph(State)
    graph.add_node("fetch_jobs", fetch_jobs)
    graph.add_node("prefilter", prefilter)
    graph.add_node("classify", classify)
    graph.add_node("apply", apply)
    graph.add_node("record", record)
    graph.add_edge(START, "fetch_jobs")
    graph.add_edge("fetch_jobs", "prefilter")
    graph.add_edge("prefilter", "classify")
    graph.add_conditional_edges("classify", route_after_classify, ["apply", "record"])
    graph.add_edge("apply", "record")
    graph.add_edge("record", END)
    return graph.compile()
