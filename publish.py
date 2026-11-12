#!/usr/bin/env python3
"""publish.py: turn the search results in out/ into the files this repo publishes.

    python3 -I publish.py --out /home/jobs/course-tracks/out --repo .

For every configs/<course>.json that has results in OUT/<course>/ it writes, under courses/<course>/:

    jobs.csv            every open posting that matched, one row each (facts only: company, title, location, link)
    new-today.md        postings new since the last run that are in a core track or have an early-career title
    report.md           the full report for the newest day
    reports/DATE.md     the same report, kept per day
    counts.json         the counts behind the report
    summary/DATE.json   the day's totals per track and per job title (small; kept per day)

and rewrites the lines between the headline markers in README.md. It reads no network and changes nothing in OUT.
Stdlib only."""
import argparse, csv, glob, io, json, os, re, sys

COLUMNS = ["id", "tracks", "title_groups", "company", "title", "locations", "in_us", "early_career_title",
           "new_today", "first_seen", "posted_at", "url"]
START, END = "<!-- headline:start -->", "<!-- headline:end -->"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    os.replace(tmp, path)


def cell(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def table(ms, names, with_track):
    ms = sorted(ms, key=lambda m: (m["company"].lower(), m["title"].lower()))
    head = ["Company", "Job title", "Location"] + (["Track"] if with_track else []) + ["In the US", "Link"]
    L = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for m in ms:
        c = [cell(m["company"]), cell(m["title"]), cell("; ".join(m["locations"])[:70])]
        if with_track: c.append("; ".join(names[t] for t in m["tracks"]))
        L.append("| " + " | ".join(c + ["yes" if m["us"] else "", f"[posting]({m['url']})"]) + " |")
    return L


def new_today(cfg, counts, matches):
    tracks = cfg["tracks"]; names = {t: v["name"] for t, v in tracks.items()}
    core = [t for t in tracks if t in (cfg.get("core_track") or [])]
    date, prev = counts["snapshot"], counts.get("previous_snapshot")
    core_names = " and ".join(names[t] for t in core) or "no track"
    o = [f"# {cfg['course']}: new postings, {date}", "", "## Executive summary", "",
         f"**What this is.** The short daily list: postings that appeared since the last run and are either a {core_names} title "
         "or have an early-career word in the title (any track).", "",
         "**Why read it.** These are the two groups worth checking every day. The full list of every open posting is in "
         "[jobs.csv](jobs.csv) and the full report is in [report.md](report.md).", ""]
    if counts.get("first_run"):
        return "\n".join(o + ["**What it found.** This is the first day of the search for this course, so there is nothing to compare with. "
                              "The first list of new postings appears after the next run.", ""])
    new = [m for m in matches if m.get("new")]
    in_core = {t: [m for m in new if t in m["tracks"]] for t in core}
    early = [m for m in new if m["early_career_title"]]
    if not early and not any(in_core.values()):
        o += [f"**What it found.** Nothing new today in these two groups. {counts['new']:,} postings are new since {prev} across all tracks, "
              "none of them in a core track or with an early-career title.", ""]
    else:
        bits = [f"{len(in_core[t])} new in {names[t]}" for t in core]
        bits.append(f"{len(early)} new with an early-career title ({sum(1 for m in early if m['us'])} in the US)")
        o += [f"**What it found.** Since {prev}: " + "; ".join(bits) + f". Across all tracks {counts['new']:,} postings are new.", ""]
    o += ["The track of each job title is a proposal made by an AI. The course designers have not confirmed it.", ""]
    for t in core:
        o += [f"## New in {names[t]} ({len(in_core[t])})", ""] + (table(in_core[t], names, False) if in_core[t] else ["None today."]) + [""]
    o += [f"## New early-career postings, all tracks ({len(early)})", ""] + (table(early, names, True) if early else ["None today."]) + [""]
    return "\n".join(o)


def jobs_csv(matches):
    buf = io.StringIO(); w = csv.writer(buf, lineterminator="\n"); w.writerow(COLUMNS)
    for m in sorted(matches, key=lambda m: (m["company"].lower(), m["title"].lower(), m["id"])):
        w.writerow([m["id"], ";".join(m["tracks"]), "; ".join(m["rows"]), m["company"], m["title"], "; ".join(m["locations"]),
                    "yes" if m["us"] else "", "yes" if m["early_career_title"] else "", "yes" if m.get("new") else "",
                    m.get("first_seen") or "", m.get("posted_at") or "", m.get("url") or ""])
    return buf.getvalue()


def summary(cfg, counts):
    tracks = cfg["tracks"]; tn = counts.get("track_new") or {}
    return dict(course=cfg["course"], snapshot=counts["snapshot"], previous_snapshot=counts.get("previous_snapshot"),
                open_postings_searched=counts["open_postings"], matched=counts.get("matched"), new=counts.get("new"), closed=counts.get("closed"),
                tracks={t: dict(name=v["name"], open=counts["track_totals"].get(t, 0), early_career=counts["track_early"].get(t, 0), new=tn.get(t))
                        for t, v in tracks.items()},
                titles=[dict(title=r["title"], track=r["track"], open=r["postings"], companies=r["companies"], early_career=r["early"]) for r in counts["rows"]])


def headline(slug, cfg, counts):
    tracks = cfg["tracks"]; tn = counts.get("track_new") or {}
    L = [f"### {cfg['course']}", "",
         f"Snapshot **{counts['snapshot']}**: {counts.get('matched', 0):,} open postings matched, out of {counts['open_postings']:,} searched. "
         f"Files: [new today](courses/{slug}/new-today.md), [full report](courses/{slug}/report.md), [every posting](courses/{slug}/jobs.csv).", "",
         "| Track | Open postings | With an early-career title | New since the last run |", "|---|---:|---:|---:|"]
    for t, v in tracks.items():
        n = tn.get(t)
        L.append(f"| {v['name']} | {counts['track_totals'].get(t, 0):,} | {counts['track_early'].get(t, 0)} | {'first day' if n is None else n} |")
    return L + [""]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--repo", required=True)
    a = ap.parse_args()
    heads = []
    for p in sorted(glob.glob(os.path.join(a.repo, "configs", "*.json"))):
        slug = os.path.splitext(os.path.basename(p))[0]; cfg = json.load(open(p, encoding="utf-8"))
        cpath = os.path.join(a.out, slug, "latest-counts.json")
        if not os.path.exists(cpath):
            print(f"{slug}: no results yet, skipped"); continue
        counts = json.load(open(cpath, encoding="utf-8")); date = counts["snapshot"]
        if not re.fullmatch(r"20\d\d-\d\d-\d\d", date): sys.exit(f"{slug}: bad snapshot date {date!r}")
        mpath = os.path.join(a.out, slug, date, "matches.jsonl")
        if "matched" not in counts or not os.path.exists(mpath):
            print(f"{slug}: results for {date} are from an older version of the search or incomplete, skipped"); continue
        matches = [json.loads(l) for l in open(mpath, encoding="utf-8")]
        report = open(os.path.join(a.out, slug, date, "report.md"), encoding="utf-8").read()
        d = os.path.join(a.repo, "courses", slug)
        write(os.path.join(d, "jobs.csv"), jobs_csv(matches))
        write(os.path.join(d, "new-today.md"), new_today(cfg, counts, matches))
        write(os.path.join(d, "report.md"), report)
        write(os.path.join(d, "reports", f"{date}.md"), report)
        write(os.path.join(d, "counts.json"), json.dumps(counts, ensure_ascii=False, indent=1) + "\n")
        write(os.path.join(d, "summary", f"{date}.json"), json.dumps(summary(cfg, counts), ensure_ascii=False, indent=1) + "\n")
        heads += headline(slug, cfg, counts)
        print(f"{slug}: published {date}, {len(matches)} postings, {sum(1 for m in matches if m.get('new'))} new")
    readme = os.path.join(a.repo, "README.md")
    if heads and os.path.exists(readme):
        s = open(readme, encoding="utf-8").read()
        if START in s and END in s:
            s = s[:s.index(START) + len(START)] + "\n" + "\n".join(heads) + s[s.index(END):]
            write(readme, s)


if __name__ == "__main__":
    main()
