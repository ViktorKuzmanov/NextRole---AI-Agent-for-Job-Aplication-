# NextRole

NextRole is an AI agent that applies to jobs for me. It finds job postings that fit my profile, decides which ones are a good match, submits my CV and a cover letter, and keeps a record I can review in a dashboard web app. The goal is that I never apply by hand; I only check what NextRole has applied to.

## Why this project exists

- **Save time.** Job hunting is repetitive. NextRole does the searching and applying automatically.
- **Learn.** I am building this to learn **LangChain** and **LangGraph** hands-on.
- **Portfolio.** I want to present NextRole as an AI engineering project when applying for AI Engineer positions.

## Who it applies for

NextRole applies on my behalf for two kinds of roles:

1. **AI Engineer** (primary). I have been building AI-powered applications recently and this is the area I want to work in.
2. **Blockchain Developer** (secondary). I have prior experience as a blockchain developer, so these roles are also a fit.

Everything else is skipped.

## Version 1 (current scope)

Version 1 is deliberately small. Each step is a node in a LangGraph workflow. We build them one at a time.

### 1. Get job postings

Collect new job postings from a source.

**Open question:** should v1 take the LinkedIn job alert emails I already receive, or read postings directly from a job board such as Crypto Job List?

**Decision for v1:** start with a **job board**, not LinkedIn emails. Reasons:

- A job board gives us a clean list of postings. Many boards expose an RSS feed or a JSON API, so we do not even need to scrape HTML.
- LinkedIn emails only contain links back to LinkedIn. Applying on LinkedIn itself requires a logged-in session, is heavily protected against bots, and automating it violates LinkedIn's terms of service, which can get the account restricted.
- Job board "Apply" buttons usually lead to a small number of applicant tracking systems (Greenhouse, Lever, Ashby, Workable). Their forms are predictable, which makes automatic applying realistic.

LinkedIn emails can be added later as a **second source of links only** (see Future versions). NextRole would read the job links from the email and apply through the company's own careers page, never through LinkedIn automation.

#### Sources

**Primary: ATS job APIs.** Most companies post their jobs on an applicant tracking system that exposes every open job as public JSON. No login and no scraping is needed, and the posting and the application form live on the same ATS, so the Apply step does not have to follow redirects. NextRole keeps a list of target companies (AI labs, AI startups, crypto companies) and polls their boards:

| ATS | Public endpoint |
|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true` |
| Lever | `https://api.lever.co/v0/postings/{company}?mode=json` |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{company}` |
| Workable | `https://apply.workable.com/api/v1/widget/accounts/{company}` |

**Secondary: Hacker News "Who is hiring?"** A monthly thread where many AI and LLM startups post engineering roles. It is readable through the Algolia HN API. Posts are free text, so the LLM parses them into postings.

**Company discovery (manual, not automated).** These sites have many AI startups but no open API and they block bots. I use them by hand to find AI and crypto companies, then add those companies to the ATS list above:

- Wellfound
- Y Combinator Work at a Startup (most recent YC companies are AI startups)

**Blockchain Developer roles: web3 job boards.**

- web3.career (JSON API, needs a free token)
- Crypto Job List (RSS feed)
- findweb3.com (https://findweb3.com/jobs; check whether it has a feed before building against it)

**Avoid:** LinkedIn, Indeed and Glassdoor (automating them breaks their terms of service and they block bots), and boards that only redirect to an external apply link without structured data.

**v1 plan:** Greenhouse, Lever and Ashby for 20–50 hand-picked AI and crypto companies, plus the monthly Hacker News thread and the web3 job boards. Every endpoint above must be checked to confirm it still works before building against it.

### 2. Classify jobs

For each posting, an LLM reads the job requirements and decides whether I am a good fit, based on my profile (skills, experience, the two target roles above). Output per posting:

- target role: `ai_engineer`, `blockchain_developer`, or `skip`
- fit score and a short reason

Only postings that pass this step move on.

### 3. Apply

Submit an application to each selected posting:

- upload my CV
- submit a cover letter

Credentials and personal details (name, email, links) are **hardcoded for v1**. They will move to environment variables / secrets before anything runs in CI.

### 4. Run on a schedule

A cron job on **GitHub Actions** triggers the agent, for example **3 times per day**. Each run fetches new postings, classifies them, applies, and saves the results.

### 5. Dashboard

A small web app that shows:

- how many postings NextRole applied to
- for each application: the job, company, role type, date, fit score and reason, and exactly what information was submitted (which CV, which cover letter, the form answers)

## Future versions

These are planned features. We implement them step by step, after v1 works end to end, not all at once.

- **CV as PDF, and multiple CVs.** Submit the CV as a PDF document, and choose between several CVs depending on the type of posting (one for AI Engineer roles, one for Blockchain Developer roles, and so on).
- **Custom CV and cover letter per job.** Generate a tailored CV and cover letter for every posting, based on the specific job description.
- **Human in the loop.** For postings that are an especially good match, notify me before applying so I can approve or edit the application first.
- **Video applications.** If a posting allows a video, pick one of my pre-recorded videos (AI Engineer video or Blockchain Developer video) and attach it.
- **Apply to a link I send.** I keep seeing jobs on social media. I should be able to send NextRole a link to a posting and have it apply on its own.

## Suggested architecture (to be refined)

```
GitHub Actions cron (3x/day)
        |
        v
  LangGraph workflow
  fetch_jobs -> classify -> apply -> record
        |                                |
   job board feed / API          SQLite / JSON store
                                         |
                                         v
                                    Dashboard
```

- **LangGraph** for the workflow: each step above is a node, with state carrying the list of postings and their status.
- **LangChain** for the LLM calls (classification, later cover-letter generation).
- **Playwright** for filling application forms in a real browser.
- **SQLite or a JSON file** as the store for v1, read by the dashboard.
- **Dashboard**: a simple web app (FastAPI + a small frontend, or Streamlit) reading the store.

## Roadmap

| Step | What | Status |
|------|------|--------|
| 1 | Fetch postings from one job board | planned |
| 2 | Classify postings against my profile | planned |
| 3 | Apply with CV + cover letter (hardcoded details) | planned |
| 4 | GitHub Actions cron, 3x/day | planned |
| 5 | Dashboard of applications | planned |
| 6+ | Future versions listed above | later |

## Notes and caveats
- Every application is logged so I can always see what was sent, to whom, and when.
