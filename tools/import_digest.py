#!/usr/bin/env python3
"""
Import the numbered paper list from a WCRS history digest into that year's conference file.

  python3 tools/import_digest.py --digest /path/to/2027-wcrs-city.md --year 2027

Reads the "## Program" section of the digest, takes every line of the form
  N. Title — Authors
and writes them as "papers": [{"title", "authors"}, ...] into data/conferences/<year>.json,
creating the file with a minimal skeleton if it does not exist yet. Nothing else in the file is touched.
The digest itself is not stored in this repository; keep it wherever the project's history lives.
"""
import re, json, os, sys, argparse

SITE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--digest", required=True); ap.add_argument("--year", required=True, type=int)
a = ap.parse_args()

txt = open(a.digest, encoding="utf-8").read()
if "## Program" not in txt:
    sys.exit("no '## Program' section in the digest")
prog = txt.split("## Program", 1)[1].split("\n## ", 1)[0]
papers = []
for n, line in re.findall(r"^\s*(\d+)\.\s+(.+?)$", prog, flags=re.M):
    line = re.sub(r"\*+", "", line).strip()
    line = re.sub(r"^\[SEJ P\d+\]\s*", "", line)
    parts = re.split(r"\s+[—–]\s+", line, maxsplit=1)
    authors = parts[1].strip() if len(parts) > 1 else ""
    authors = re.sub(r"\s*\[[^\]]*\]", "", authors)
    papers.append({"title": parts[0].strip(), "authors": authors})
if not papers:
    sys.exit("no numbered papers found; nothing written")

path = os.path.join(SITE, "data", "conferences", f"{a.year}.json")
data = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {"year": a.year, "held": True}
data["papers"] = papers
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"wrote {len(papers)} papers into {os.path.relpath(path, SITE)}")
