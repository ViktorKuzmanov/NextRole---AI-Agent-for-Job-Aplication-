"""Runs the whole graph offline: fake job board, fake models, in-memory store."""

from langchain_core.runnables import RunnableLambda

from nextrole import graph as graph_module
from nextrole.graph import build_graph
from nextrole.models import Classification, JobPosting
from nextrole.sources import _to_text
from nextrole.store import Store


def job(n: int, title: str) -> JobPosting:
    return JobPosting(
        id=f"test:acme:{n}", source="test", company="acme", title=title,
        url=f"https://example.com/{n}", description="Build things.",
    )


POSTINGS = [
    job(1, "AI Engineer"),
    job(2, "Senior Solidity Engineer"),
    job(3, "Account Executive, AI"),  # no engineering word -> title screen drops it
    job(4, "ML Engineer, Research"),
    job(5, "Applied AI Engineer"),  # classifier raises on this one
]


def fake_classify(inputs: dict) -> Classification:
    title = inputs["title"]
    if title == "AI Engineer":
        return Classification(role="ai_engineer", fit_score=88, reason="Strong match.")
    if "Solidity" in title:
        return Classification(role="blockchain_developer", fit_score=55, reason="Too senior.")
    if "Applied" in title:
        raise RuntimeError("model unavailable")
    return Classification(role="skip", fit_score=0, reason="Research role.")


def run(monkeypatch, store, classify=fake_classify, postings=POSTINGS):
    monkeypatch.setattr(graph_module, "fetch_all", lambda companies: (postings, ["boom"]))
    app = build_graph(
        store=store,
        classifier=RunnableLambda(classify),
        writer=RunnableLambda(lambda inputs: f"Dear {inputs['company']} team, ..."),
        companies={},
    )
    return app.invoke({"limit": None})


def test_full_run_applies_only_to_good_matches(monkeypatch):
    store = Store(":memory:")
    final = run(monkeypatch, store)

    assert [j.id for j in final["candidates"]] == [f"test:acme:{n}" for n in (1, 2, 4, 5)]
    assert [a.job.title for a in final["applications"]] == ["AI Engineer"]
    assert final["applications"][0].status == "prepared"

    status = {r["id"]: r["status"] for r in store.rows()}
    assert status == {
        "test:acme:1": "prepared",
        "test:acme:2": "skipped",  # right role, score under the threshold
        "test:acme:4": "skipped",
    }
    # The fetch error and the classifier failure are both surfaced.
    assert final["errors"][0] == "boom"
    assert any("test:acme:5" in e for e in final["errors"])


def test_second_run_only_retries_what_failed(monkeypatch):
    store = Store(":memory:")
    run(monkeypatch, store)
    final = run(monkeypatch, store)
    assert [j.id for j in final["candidates"]] == ["test:acme:5"]


def test_no_matches_skips_apply(monkeypatch):
    store = Store(":memory:")
    skip = lambda inputs: Classification(role="skip", fit_score=0, reason="No.")
    final = run(monkeypatch, store, classify=skip)
    assert "applications" not in final
    assert {r["status"] for r in store.rows()} == {"skipped"}


def test_html_to_text():
    assert _to_text("&lt;p&gt;Hello &amp;amp; <b>bye</b>&lt;/p&gt;<ul><li>one</li></ul>") == (
        "Hello & bye\none"
    )
