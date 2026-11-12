# Running on the server

## Executive summary

**What this is.** How the daily search runs on the server and how to check, stop or change it.

**Why read it.** You need it only if you look after the server. To read the job lists, use the files in
`courses/` instead.

**The short version.** One timer starts one script, `ops/run-daily.sh`, at 05:05 UTC each day. The script pulls
this repo, searches the day's postings, writes the files in `courses/`, and pushes them to GitHub. It runs as
the user `jobs`, the owner of the postings file it reads.

## Where things are

| Thing | Where |
|---|---|
| Clone of this repo | `/home/jobs/course-tracks/repo` |
| Results and memory of what was listed | `/home/jobs/course-tracks/out` (never in git) |
| The postings it reads | `/home/jobs/ai-jobs/data/jobs/DATE/jobs.jsonl`, written by the ai-jobs collector at 04:30 UTC |
| Schedule | `course-tracks-daily.timer`, 05:05 UTC each day |
| Deploy key | `/home/jobs/.ssh/id_ed25519_course_track_jobs`, registered on this repo only, with write access |
| Commits | signed `course-track-jobs (ubuntu-4gb-bbc-1)` |

The clone uses its own key through `core.sshCommand` in its git config, because the `jobs` user's default key
belongs to a different repo and GitHub allows a deploy key on one repo only.

## Everyday commands

See the last run:

```bash
ssh hetz 'sudo journalctl -u course-tracks-daily.service -n 20 --no-pager'
```

Run it now instead of waiting for the timer:

```bash
ssh hetz 'sudo systemctl start course-tracks-daily.service'
```

Stop the daily run without removing anything (delete the file to resume):

```bash
ssh hetz 'sudo -u jobs touch /home/jobs/course-tracks/STOP'
```

## What happens when something fails

- **GitHub cannot be reached at the start.** The search still runs with the code and course files already on
  the server.
- **The push fails.** The run ends with an error in the log. The results are kept, and the next run pushes them.
- **The day's postings are not ready.** The script uses the newest postings file it finds. If that is
  yesterday's, nothing changes and nothing is pushed.

## Setting it up on a new server

1. Clone this repo to `/home/jobs/course-tracks/repo` as the user that owns the postings file.
2. Make a key for this repo only, add its public half to the repo as a deploy key with write access, and point
   the clone at it with `git config core.sshCommand`.
3. Copy `ops/course-tracks-daily.service` and `ops/course-tracks-daily.timer` to `/etc/systemd/system/`, then
   enable the timer.
