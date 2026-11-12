"""Command line entry point: `nextrole run | fetch | list | graph`."""

import argparse

from . import config
from .graph import TITLE_ENGINEERING, TITLE_HINT, build_graph
from .sources import fetch_all
from .store import Store


def cmd_run(args) -> None:
    final = build_graph().invoke({"limit": args.limit})
    classified = final.get("classified", [])
    applications = final.get("applications", [])
    print(f"fetched     {len(final.get('postings', []))} postings")
    print(f"candidates  {len(final.get('candidates', []))} new, passed the title screen")
    print(f"classified  {len(classified)}")
    print(f"prepared    {len(applications)} applications (dry run, nothing was sent)")
    for app in applications:
        c = app.classification
        print(f"  [{c.fit_score:>3}] {c.role:<20} {app.job.company}: {app.job.title}")
        print(f"        {app.job.url}")
    for err in final.get("errors", []):
        print(f"  ! {err}")


def cmd_fetch(args) -> None:
    """Fetch only, no LLM calls: shows what the title screen would let through."""
    postings, errors = fetch_all(config.load_companies())
    hits = [
        p for p in postings if TITLE_HINT.search(p.title) and TITLE_ENGINEERING.search(p.title)
    ]
    for p in hits:
        print(f"{p.company:<14} {p.title}  ({p.location})")
    print(f"\n{len(postings)} postings fetched, {len(hits)} pass the title screen")
    for err in errors:
        print(f"  ! {err}")


def cmd_list(args) -> None:
    rows = Store(config.DB_PATH).rows(args.status)
    for r in rows:
        print(
            f"{r['created_at'][:10]}  {r['status']:<9} [{r['fit_score']:>3}] "
            f"{r['role']:<20} {r['company']}: {r['title']}"
        )
        if args.verbose:
            print(f"    {r['url']}\n    {r['reason']}")
            if r["cover_letter"]:
                print("\n" + r["cover_letter"] + "\n")
    print(f"\n{len(rows)} rows")


def cmd_graph(args) -> None:
    print(build_graph(store=Store(":memory:")).get_graph().draw_mermaid())


def main() -> None:
    parser = argparse.ArgumentParser(prog="nextrole")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the full workflow once")
    run.add_argument("--limit", type=int, help="classify at most N postings (caps LLM cost)")
    run.set_defaults(func=cmd_run)

    sub.add_parser("fetch", help="fetch postings and show the title screen, no LLM").set_defaults(
        func=cmd_fetch
    )

    ls = sub.add_parser("list", help="show recorded postings")
    ls.add_argument("--status", choices=["skipped", "prepared", "submitted", "failed"])
    ls.add_argument("-v", "--verbose", action="store_true")
    ls.set_defaults(func=cmd_list)

    sub.add_parser("graph", help="print the workflow as a Mermaid diagram").set_defaults(
        func=cmd_graph
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
