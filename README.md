# course-track-jobs

## Executive summary

**What this is.** A daily list of open job postings, sorted into the tracks of a university course. Each course
has a short list of job titles for each of its tracks. Once a day a server searches about 85,000 open postings
from about 715 company job boards for those titles and publishes what it finds here.

**Why read it.** To see which real jobs a course track leads to: how many are open today, which companies post
them, which are open to people at the start of a career, and what is new since yesterday.

**What it shows today.**

<!-- headline:start -->
### Digital Experience Engineering (INFO 7375)

Snapshot **2026-11-12**: 6,573 open postings matched, out of 85,017 searched. Files: [new today](courses/design-engineering/new-today.md), [full report](courses/design-engineering/report.md), [every posting](courses/design-engineering/jobs.csv).

| Track | Open postings | With an early-career title | New since the last run |
|---|---:|---:|---:|
| Track 1 – Creative | 3,305 | 67 | 48 |
| Track 2 – Creative Engineer | 70 | 4 | 0 |
| Track 3 – Engineer | 3,235 | 73 | 43 |
<!-- headline:end -->

**What to keep in mind.** Which track a job title belongs to is a proposal made by an AI. The course designers
have not confirmed it. A posting is listed because its title matched, not because anyone read the job
description. See [What limits these numbers](#what-limits-these-numbers).

## The files for each course

Everything for a course is in `courses/<course>/`.

| File | What it is |
|---|---|
| `new-today.md` | The short daily list: new postings in the course's core track, and new postings with an early-career title in any track |
| `report.md` | The full report for the newest day: counts per track, everything new, every open posting in the core track, every open early-career posting, and counts per job title |
| `jobs.csv` | Every open posting that matched, one row each |
| `counts.json` | The numbers behind the report |
| `reports/DATE.md` | The full report for each past day |
| `summary/DATE.json` | Each day's totals per track and per job title |
| `site.json` | What a website reads: track totals, counts per job title, and every posting that is new, has an early-career title, or is in the core track |

`courses/index.json` lists the courses and where each one's `site.json` is. A website can read these files
straight from GitHub (`https://raw.githubusercontent.com/nikbearbrown/course-track-jobs/main/courses/index.json`).

## Columns in jobs.csv

| Column | Meaning |
|---|---|
| `id` | The posting's id: job-board provider, company board, and the board's own id |
| `tracks` | The track or tracks the posting's title fits, separated by `;` |
| `title_groups` | The job-title groups the title matched, separated by `;` |
| `company` | The employer |
| `title` | The job title as posted |
| `locations` | The location text as posted, separated by `;` |
| `in_us` | `yes` when the location text names the United States, a US state, or one of a few large US cities |
| `early_career_title` | `yes` when the title has a word such as intern, new grad, graduate, junior or associate |
| `new_today` | `yes` when the posting was not in this list on the previous run |
| `first_seen` | The day the collector first saw the posting |
| `posted_at` | The posting date the job board gives, when it gives one |
| `url` | The link to the posting on the employer's job board |

The list holds facts only: company, title, location, dates and link. It holds no job-description text.

## How it works

1. **Collect.** A separate collector, [ai-jobs](https://github.com/nikbearbrown/ai-jobs), reads the public job
   boards (Greenhouse, Ashby, Lever, SmartRecruiters, Recruitee) of the companies on its list every morning.
2. **Search.** `course_tracks.py` reads that day's open postings and, for each file in `configs/`, matches each
   posting's title against the course's job-title patterns. It remembers what it listed before, so it can say
   what is new. It fetches nothing itself.
3. **Publish.** `publish.py` writes the files above, and the server commits and pushes them to this repo.

The server runs these steps at 05:05 UTC each day. [ops/README.md](ops/README.md) describes the setup.

## Adding a course

Add one file, `configs/<course-slug>.json`, in the same shape as
[configs/design-engineering.json](configs/design-engineering.json): the course name, its tracks, and for each
job title a pattern, a track, and one line saying what the job is. The next daily run searches for it. Its
first day is the starting point, so the first list of new postings appears the day after.

## What limits these numbers

1. **Company boards only.** The collector reads the boards of the companies on its list, mostly technology
   companies. It does not read LinkedIn, Indeed, or employers that use Workday.
2. **Titles, not job descriptions.** Some matched postings are the wrong kind of job, and jobs with plain titles
   such as Software Engineer are missed.
3. **Early-career means a word in the title.** A posting without one may still accept new graduates.
4. **"In the US" is read from the location text** and can miss a posting that gives only a small city.
5. **All countries.** The counts are for every country unless a line says otherwise.
6. **Proposed, not confirmed.** Which track a title belongs to is an AI-made proposal.
