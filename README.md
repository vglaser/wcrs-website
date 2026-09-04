# WCRS website

The public website of the West Coast Research Symposium on Technology Entrepreneurship. Static HTML, generated from a few JSON files by one Python script, hosted on GitHub Pages. Maintained by Emily Cox Pahnke (University of Washington) from 2026; built by Vern Glaser (University of Alberta) for the 2026 launch.

## The one rule

**Edit the data, run the build, commit and push. Never edit the HTML files by hand.** Every `.html` file in this repository is generated; the next build overwrites it.

## What lives where

| Path | What it is | Edit it? |
|---|---|---|
| `data/site.json` | Facts about the organization: name, what WCRS is, the About text, the registries of people and sponsoring units | Yes, rarely |
| `data/conferences/<year>.json` | **Everything about one conference year**: dates, host, venue, theme, keynote, call for papers, key dates, travel, doctoral consortium, program PDF, the papers presented | Yes: this is the annual update |
| `assets/programs/<year>-wcrs-program.pdf` | The program PDFs, one per year | Add one per year |
| `assets/img/` | Sponsor logos and venue photographs | Add when a logo or venue changes |
| `build.py` | The generator. Holds the templates and the styling; holds no facts about any year | Only to change how the site looks |
| `tools/import_digest.py` | Fills a year's paper list from a history digest | Run, don't edit |
| `index.html`, `about.html`, `conferences.html`, `people.html`, `conferences/*.html`, `assets/site.css` | Generated | **Never** |
| `call-for-papers.html`, `travel.html`, `papers.html`, `contact.html` | Generated forwarding pages so old links keep working | **Never** |

How the site decides what is "next": at build time it compares each year's `end_date` with today. The earliest year whose end date is still ahead is the next conference; it gets the nav item "WCRS <year>", the card on Home, and the key-dates band. If no year is ahead, the earliest year marked to-be-announced (a file with no dates) takes that place. Nothing is flipped by hand. The build prints which year it chose, like this:

```
featured: WCRS 2026 (upcoming, ends 2026-09-10) · today 2026-09-02
```

## The annual update, in one prompt

After the conference, with the final program PDF in hand, open Claude Code in this folder and say:

> Here is the final WCRS 2026 program PDF at <path>. Update the 2026 conference file so it matches what ran, and add a 2027 file marked to be announced. Then build and show me the diff.

When the committee approves the next call:

> Here is the WCRS 2027 call for papers. Fill in the 2027 conference file: dates, host, venue, theme, call text, deadline, key dates, committee and sponsors for the year. Build and show me the Home page.

When the venue and travel details are known:

> Add the travel section and a venue photo to the 2027 file. Build.

Then look at the result locally (below), and push. The push publishes.

## Doing it by hand

1. Copy `data/conferences/2026.json` to `data/conferences/2027.json` and edit every field. Delete fields you don't know yet; the pages simply omit them. A year with only `year`, `held` and `note` renders as "to be announced".
2. Put the program PDF at `assets/programs/2027-wcrs-program.pdf` and reference it in the file's `program_pdf`.
3. Paper lists: `python3 tools/import_digest.py --digest <the year's digest> --year 2027`, or type the `papers` array by hand (title and authors).
4. Build and preview:

```bash
python3 build.py && python3 -m http.server 8000
```

Open <http://localhost:8000>. Python 3.9 or newer; nothing to install.

5. Commit and push to `main`. GitHub Pages rebuilds within a minute or two.

The build refuses to run if a file references a missing PDF, logo, person id or sponsor id, and tells you which.

## Rules the site keeps

- Conference papers are never hosted or linked here. Only programs are public.
- No passwords, credentials, or shared-folder links in any file in this repository.
- The site never states a fact that a program, the event plan, or the previous site does not state. Each year's file has a `source_note` for caveats.

## Who to ask

Emily Cox Pahnke (site and submissions). Vern Glaser built v1 and can help with Claude Code. The history digests the paper lists come from live in Vern's project folder, not in this repository.
