"""Job sources: public ATS job-board APIs (no login, no scraping)."""

import html
import re

import httpx

from .models import JobPosting

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t]*\n\s*")


def _to_text(raw_html: str) -> str:
    text = html.unescape(html.unescape(raw_html or ""))
    text = re.sub(r"</(p|div|li|h\d|ul|ol)>|<br\s*/?>", "\n", text)
    return _WS.sub("\n", _TAG.sub("", text)).strip()


def fetch_greenhouse(client: httpx.Client, company: str) -> list[JobPosting]:
    r = client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs",
        params={"content": "true"},
    )
    r.raise_for_status()
    return [
        JobPosting(
            id=f"greenhouse:{company}:{j['id']}",
            source="greenhouse",
            company=company,
            title=j["title"].strip(),
            location=(j.get("location") or {}).get("name", ""),
            url=j["absolute_url"],
            apply_url=j["absolute_url"],
            description=_to_text(j.get("content", "")),
        )
        for j in r.json().get("jobs", [])
    ]


def fetch_lever(client: httpx.Client, company: str) -> list[JobPosting]:
    r = client.get(f"https://api.lever.co/v0/postings/{company}", params={"mode": "json"})
    r.raise_for_status()
    jobs = []
    for j in r.json():
        lists = "\n".join(
            f"{section.get('text', '')}\n{_to_text(section.get('content', ''))}"
            for section in j.get("lists", [])
        )
        jobs.append(
            JobPosting(
                id=f"lever:{company}:{j['id']}",
                source="lever",
                company=company,
                title=j["text"].strip(),
                location=(j.get("categories") or {}).get("location", "") or "",
                url=j["hostedUrl"],
                apply_url=j.get("applyUrl", j["hostedUrl"]),
                description=f"{j.get('descriptionPlain', '')}\n{lists}".strip(),
            )
        )
    return jobs


def fetch_ashby(client: httpx.Client, company: str) -> list[JobPosting]:
    r = client.get(f"https://api.ashbyhq.com/posting-api/job-board/{company}")
    r.raise_for_status()
    return [
        JobPosting(
            id=f"ashby:{company}:{j['id']}",
            source="ashby",
            company=company,
            title=j["title"].strip(),
            location=j.get("location", "") + (" (remote)" if j.get("isRemote") else ""),
            url=j["jobUrl"],
            apply_url=j.get("applyUrl", j["jobUrl"]),
            description=j.get("descriptionPlain") or _to_text(j.get("descriptionHtml", "")),
        )
        for j in r.json().get("jobs", [])
        if j.get("isListed", True)
    ]


FETCHERS = {"greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby}


def fetch_all(companies: dict[str, list[str]]) -> tuple[list[JobPosting], list[str]]:
    """Fetch every configured board. A failing board is reported, not fatal."""
    postings: list[JobPosting] = []
    errors: list[str] = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for ats, slugs in companies.items():
            for slug in slugs or []:
                try:
                    postings.extend(FETCHERS[ats](client, slug))
                except Exception as exc:  # one bad board must not kill the run
                    errors.append(f"fetch {ats}/{slug}: {type(exc).__name__}: {exc}")
    return postings, errors
