#!/usr/bin/env bash
# Daily run on the server (user: jobs). Searches the day's job postings for each course's tracks, then publishes
# the results to this repo. It fetches nothing from any employer: it reads the file the ai-jobs collector wrote.
# The only network use is git (pull at the start, push at the end).
#
#   COURSE_TRACKS_DATA        where the daily postings are   (default /home/jobs/ai-jobs/data/jobs)
#   COURSE_TRACKS_STATE       where results and memory live  (default /home/jobs/course-tracks/out; never in git)
#   COURSE_TRACKS_NO_PUBLISH  set to 1 to search and build the files but not commit or push
#
# Halt: touch /home/jobs/course-tracks/STOP   (the run exits quietly; remove the file to resume)
set -euo pipefail
cd "$(dirname "$0")/.."
DATA=${COURSE_TRACKS_DATA:-/home/jobs/ai-jobs/data/jobs}
STATE=${COURSE_TRACKS_STATE:-/home/jobs/course-tracks/out}
STOP=/home/jobs/course-tracks/STOP
if [ -e "$STOP" ]; then echo "STOP file present ($STOP); not running"; exit 0; fi

echo "== $(date -u +%FT%TZ) course-track-jobs daily run =="
# a failed pull must not stop the search: the results are still written to $STATE and published on a later run
git pull --rebase --autostash --quiet || echo "git pull failed; using the checkout as it is"

python3 -I course_tracks.py --data "$DATA" --configs configs --out "$STATE"
python3 -I publish.py --out "$STATE" --repo .

if [ "${COURSE_TRACKS_NO_PUBLISH:-0}" = "1" ]; then echo "no-publish mode: files built, nothing committed"; exit 0; fi
git add -- courses README.md
if git diff --cached --quiet; then echo "nothing new to commit"; else
  SNAP=$(ls "$DATA" | grep -E '^20[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort | tail -1)
  git commit -q -m "Daily course-track job search, snapshot $SNAP"
fi
# push whatever is not on GitHub yet, including a commit left behind by a run whose push failed
if [ -n "$(git log --oneline '@{u}..' 2>/dev/null)" ]; then
  git pull --rebase --quiet
  git push --quiet
  echo "pushed to GitHub"
fi
echo "== done $(date -u +%FT%TZ) =="
