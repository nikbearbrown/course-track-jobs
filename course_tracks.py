#!/usr/bin/env python3
"""course_tracks.py: daily search of a job-postings snapshot for the job titles of each course track.

    python3 -I course_tracks.py --data /home/jobs/ai-jobs/data/jobs --configs configs --out out [--date 2026-11-11]

Reads the newest DATA/DATE/jobs.jsonl that the ai-jobs daily run wrote (read-only; this script fetches nothing).
For every configs/<course>.json it writes out/<course>/DATE/{counts.json, matches.jsonl, report.md}, refreshes
out/<course>/latest.md and latest-counts.json, and remembers which postings it has already listed in
out/<course>/seen.json, so each day's report can say what is new. publish.py then turns out/ into the files this
repo publishes. Which track a title belongs to is an AI-made proposal held in the config file. Stdlib only."""
import argparse, collections, glob, json, os, re, sys

US_STATES = "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split()
US_NAMES = ("Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|"
            "Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|"
            "North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|"
            "Wisconsin|Wyoming|San Francisco|Seattle|Boston|Chicago|Austin|Los Angeles|Denver|Atlanta|Palo Alto|Mountain View|Bay Area|NYC")
# the ai-jobs seisfit.py rule (country code, "United States", ", CA") plus full state names and a few large US cities
US_RX = re.compile(r"(United States|\bUSA?\b|U\.S\.|, (" + "|".join(US_STATES) + r")\b|\b(" + US_NAMES + r")\b)")
KEEP_MATCH_DAYS = 30   # matches.jsonl (about 3 MB a day) is kept this many days; counts.json and report.md are kept for good
LIST_CAP = 60          # most rows shown in one "new today" table; the rest are in jobs.csv


def is_us(r):
    return "US" in (r.get("country_codes") or []) or any(US_RX.search(l or "") for l in (r.get("locations") or []))


def newest_snapshot(data, date):
    if date:
        return date
    days = sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(data, "20*", "jobs.jsonl")))
    if not days:
        sys.exit(f"no jobs.jsonl under {data}")
    return days[-1]


def write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def cell(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def run(cfg, slug, postings, date, n_file, out_root):
    rows = cfg["rows"]; tracks = cfg["tracks"]
    pats = [re.compile(r["pattern"], re.I) for r in rows]
    hw = re.compile(cfg["hardware_words"], re.I); hw_co = set(cfg["hardware_companies"])
    early_yes = re.compile(cfg["early_words"], re.I); early_not = re.compile(cfg["early_not"], re.I)
    early = lambda t: bool(early_yes.search(t)) and not early_not.search(t)

    hit = [[] for _ in rows]; per_track = collections.defaultdict(set); per_early = collections.defaultdict(set)
    per_also = collections.defaultdict(set); matches = {}
    for r in postings:
        t = (r.get("title") or "").strip(); co = r.get("company") or ""
        for i, row in enumerate(rows):
            if pats[i].search(t) and not (row["hw"] and (hw.search(t) or co in hw_co)):
                e = early(t); hit[i].append((t, co)); per_track[row["track"]].add(r["id"])
                if e: per_early[row["track"]].add(r["id"])
                if row.get("also"): per_also[row["also"]].add(r["id"])
                m = matches.setdefault(r["id"], dict(id=r["id"], company=co, title=t, locations=r.get("locations") or [], us=is_us(r),
                                                     url=r.get("url") or r.get("apply_url"), first_seen=r.get("first_seen"), posted_at=r.get("posted_at"),
                                                     early_career_title=e, tracks=[], rows=[]))
                if row["track"] not in m["tracks"]: m["tracks"].append(row["track"])
                m["rows"].append(row["title"])

    counts = dict(course=cfg["course"], snapshot=date, postings_in_file=n_file, open_postings=len(postings),
                  track_totals={k: len(v) for k, v in per_track.items()}, track_early={k: len(v) for k, v in per_early.items()},
                  track_also={k: len(v - per_track[k]) for k, v in per_also.items()}, rows=[])
    for i, row in enumerate(rows):
        cos = collections.Counter(c for _, c in hit[i]); e = sorted({(c, t) for t, c in hit[i] if early(t)})
        counts["rows"].append(dict(title=row["title"], track=row["track"], postings=len(hit[i]), companies=len(cos), early=sum(1 for t, _ in hit[i] if early(t)),
                                   top_companies=[c for c, _ in cos.most_common(5)], early_examples=[f"{c}: {t}" for c, t in e][:40],
                                   all_matches=sorted(f"{c}: {t}" for t, c in hit[i]) if len(hit[i]) <= 80 else None,
                                   examples=[t for t, _ in collections.Counter(t for t, _ in hit[i]).most_common(4)]))

    cdir = os.path.join(out_root, slug); ddir = os.path.join(cdir, date); os.makedirs(ddir, exist_ok=True)
    seen_path = os.path.join(cdir, "seen.json")
    state = json.load(open(seen_path, encoding="utf-8")) if os.path.exists(seen_path) else None
    first_run = state is None
    if state and state.get("last_snapshot") == date:           # same snapshot run again: compare with the day before, change no state
        seen = set(state.get("seen_before_last", [])); prev = state.get("previous_snapshot")
    else:
        seen = set(state["seen"]) if state else set(); prev = state.get("last_snapshot") if state else None
    new = [m for i, m in matches.items() if i not in seen]
    for i, m in matches.items(): m["new"] = (not first_run) and i not in seen
    closed = len(set(state["open_last"]) - set(matches)) if state and state.get("last_snapshot") != date and "open_last" in state else None
    core = set(cfg.get("core_track") or [])
    counts.update(matched=len(matches), first_run=first_run, previous_snapshot=prev, new=None if first_run else len(new), closed=closed,
                  track_new=None if first_run else {t: sum(1 for m in new if t in m["tracks"]) for t in tracks})
    key = lambda m: (not m["early_career_title"], m["company"].lower(), m["title"].lower())

    def tbl(ms, cap=None):
        ms = sorted(ms, key=key); shown = ms[:cap] if cap else ms
        L = ["| Company | Job title | Location | Early-career | In the US | Link |", "|---|---|---|---|---|---|"]
        for m in shown:
            L.append(f"| {cell(m['company'])} | {cell(m['title'])} | {cell('; '.join(m['locations'])[:70])} | {'yes' if m['early_career_title'] else ''} | {'yes' if m['us'] else ''} | [posting]({m['url']}) |")
        if cap and len(ms) > cap: L.append(f"\n{len(ms) - cap} more are in `jobs.csv` (the rows marked new).")
        return L

    name = lambda t: tracks[t]["name"]
    o = [f"# {cfg['course']}: job search by track, {date}", "", "## Executive summary", "",
         f"**What this is.** The day's search of {len(postings):,} open job postings for the {len(rows)} job titles mapped to this course's tracks. A server runs it each morning on postings it has already collected from company job boards.", "",
         "**Why read it.** To see what is open now for each track, what appeared since the last run, and which postings are open to people at the start of a career.", "",
         "**What it found.**", ""]
    for t in tracks:
        n_new = sum(1 for m in new if t in m["tracks"])
        o.append(f"- **{name(t)}:** {counts['track_totals'].get(t, 0):,} open postings, {counts['track_early'].get(t, 0)} with an early-career word in the title"
                 + ("." if first_run else f"; {n_new} new since {prev}."))
    if first_run:
        o.append(f"- **First run.** Every posting counts as new on a first run, so there is no \"new\" list today. {len(matches):,} postings were recorded as the starting point.")
    elif closed is not None:
        o.append(f"- **Closed since {prev}:** {closed} postings that matched last time are no longer open.")
    o += ["- **The track of each title is a proposal made by an AI.** The course designers have not confirmed it.", ""]

    if not first_run:
        o += [f"## New since {prev}", ""]
        for t in tracks:
            ms = [m for m in new if t in m["tracks"]]
            o += [f"### {name(t)} ({len(ms)} new)", ""] + (tbl(ms, None if t in core else LIST_CAP) if ms else ["None."]) + [""]
    for t in tracks:
        if t in core:
            ms = [m for m in matches.values() if t in m["tracks"]]
            o += [f"## Every open posting in {name(t)} ({len(ms)})", ""] + tbl(ms) + [""]
    ec = [m for m in matches.values() if m["early_career_title"]]
    o += [f"## Every open early-career posting, all tracks ({len(ec)}; {sum(1 for m in ec if m['us'])} in the US)", ""]
    for t in tracks:
        ms = [m for m in ec if t in m["tracks"]]
        o += [f"### {name(t)} ({len(ms)})", ""] + (tbl(ms) if ms else ["None."]) + [""]
    o += ["## Open postings by job title", ""]
    for t in tracks:
        o += [f"### {name(t)}", "", "| Job title | Open postings | Companies | Early-career titles | Who posts it |", "|---|---:|---:|---:|---|"]
        for r in sorted((r for r in counts["rows"] if r["track"] == t), key=lambda r: (-r["postings"], r["title"])):
            o.append(f"| {r['title']} | {r['postings']:,} | {r['companies']} | {r['early']} | {', '.join(r['top_companies'][:4])} |")
        o.append("")
    o += ["## What limits these numbers", "",
          "1. **Company boards only.** Greenhouse, Ashby, Lever, SmartRecruiters and Recruitee boards of the companies on the collector's list. No LinkedIn, Indeed or Workday employers.",
          "2. **Titles, not job descriptions.** A posting is listed because its title matched. Some are the wrong kind of job, and jobs with plain titles such as Software Engineer are missed.",
          "3. **Early-career means a word in the title** (intern, new grad, graduate, junior, associate, early career). A posting without one may still accept new graduates.",
          "4. **\"In the US\" is read from the location text** (country, state, or one of a few large cities) and can miss a posting that gives only a small city.",
          "5. **Proposed, not confirmed.** Which track a title belongs to is an AI-made proposal.", ""]

    write(os.path.join(ddir, "counts.json"), json.dumps(counts, ensure_ascii=False, indent=1))
    write(os.path.join(ddir, "matches.jsonl"), "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in sorted(matches.values(), key=lambda m: (m["company"].lower(), m["title"].lower()))))
    write(os.path.join(ddir, "report.md"), "\n".join(o))
    write(os.path.join(cdir, "latest.md"), "\n".join(o))
    write(os.path.join(cdir, "latest-counts.json"), json.dumps(counts, ensure_ascii=False, indent=1))
    if not (state and state.get("last_snapshot") == date):
        write(seen_path, json.dumps(dict(last_snapshot=date, previous_snapshot=prev, seen=sorted(seen | set(matches)),
                                         seen_before_last=sorted(seen), open_last=sorted(matches)), ensure_ascii=False))
    print(f"{slug}: snapshot {date}, open {len(postings)}, matched {len(matches)}, new {'(first run)' if first_run else len(new)}, "
          f"tracks {dict(sorted(counts['track_totals'].items()))}, early {dict(sorted(counts['track_early'].items()))}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--configs", required=True); ap.add_argument("--out", required=True); ap.add_argument("--date")
    a = ap.parse_args()
    cfgs = sorted(glob.glob(os.path.join(a.configs, "*.json")))
    if not cfgs: sys.exit(f"no config files in {a.configs}")
    date = newest_snapshot(a.data, a.date)
    postings = []; n = 0
    keep = ("id", "title", "company", "locations", "country_codes", "url", "apply_url", "first_seen", "posted_at")
    with open(os.path.join(a.data, date, "jobs.jsonl"), encoding="utf-8") as f:
        for line in f:
            n += 1
            if '"status": "open"' not in line and '"status":"open"' not in line: continue
            r = json.loads(line)
            if r.get("status") == "open": postings.append({k: r.get(k) for k in keep})
    for p in cfgs:
        run(json.load(open(p, encoding="utf-8")), os.path.splitext(os.path.basename(p))[0], postings, date, n, a.out)
    old = sorted(glob.glob(os.path.join(a.out, "*", "20*", "matches.jsonl")), key=lambda q: os.path.basename(os.path.dirname(q)))
    days = sorted({os.path.basename(os.path.dirname(q)) for q in old})[:-KEEP_MATCH_DAYS]
    for q in old:                      # this script's own day files only
        if os.path.basename(os.path.dirname(q)) in days: os.remove(q)


if __name__ == "__main__":
    main()
