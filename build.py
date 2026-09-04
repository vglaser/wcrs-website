#!/usr/bin/env python3
"""
WCRS website builder.  Python 3.9 or newer; no third-party packages.

  python3 build.py                 → writes the site into this folder: index.html, about.html, conferences.html,
                                      people.html, conferences/<year>.html, three alias pages, assets/site.css
  python3 build.py --single OUT    → one self-contained HTML file (all pages, images inlined) for sharing
  python3 build.py --artifact OUT  → the same without <html>/<head>/<body> wrappers, for hosted artifacts

Data:
  data/site.json                 organization-level facts, plus the people and organization registries
  data/conferences/<year>.json   everything about one conference year, including its papers

The one rule: edit the JSON, run this script, commit. Never hand-edit the generated HTML.
No sentence about a specific conference or year may live in this file; it belongs in that year's JSON.
Status (past / upcoming / to be announced / not held) is derived from the dates at build time.
Set WCRS_TODAY=YYYY-MM-DD in the environment to build as if on another day (used to test the rollover).
"""
import json, os, sys, base64, glob, datetime, html as H
from functools import lru_cache

SITE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(SITE, "data")
site = json.load(open(os.path.join(DATA, "site.json"), encoding="utf-8"))
confs = sorted((json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(DATA, "conferences", "*.json"))),
               key=lambda c: -c['year'])
TODAY = datetime.date.fromisoformat(os.environ['WCRS_TODAY']) if os.environ.get("WCRS_TODAY") else datetime.date.today()
BUILD_DATE = TODAY.strftime("%Y.%m.%d")
ORGS, PEOPLE = site['organizations'], site['people']

def e(s):
    return H.escape(str(s), quote=True) if s is not None else ""

# ----------------------------------------------------------------------------- derived facts
def d(s):
    return datetime.date.fromisoformat(s)

def status(c):
    """none | past | upcoming | tba — never stored, always derived."""
    if not c.get("held", True): return "none"
    if c.get("start_date"):
        return "past" if d(c['end_date']) < TODAY else "upcoming"
    return "past" if c['year'] < TODAY.year else "tba"

def held_years():
    return sorted(c['year'] for c in confs if status(c) in ("past", "upcoming"))

def ordinal(c):
    """Count from the founding symposium; years not held do not count. Only for dated or past years."""
    if status(c) not in ("past", "upcoming"): return None
    n = held_years().index(c['year']) + 1
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"

def featured():
    if site.get("feature_year"):
        return conf(site['feature_year'])
    up = [c for c in confs if status(c) == "upcoming"]
    if up: return min(up, key=lambda c: c['year'])
    tba = [c for c in confs if status(c) == "tba"]
    return min(tba, key=lambda c: c['year']) if tba else None

def conf(year):
    for c in confs:
        if c['year'] == year: return c
    sys.exit(f"build.py: no data/conferences/{year}.json")

def org(i): return ORGS[i]
def person(i): return PEOPLE[i]
def concluded(): return [c for c in confs if status(c) == "past"]
def paper_count(c): return len(c.get("papers", []))

NUM = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
def num_word(n, cap=False):
    w = NUM[n] if n < len(NUM) else str(n)
    return w.capitalize() if cap else w

def schools_of(ids):
    return list(dict.fromkeys(org(i)['school'] for i in ids))

def sponsor_ids_current():
    f = featured()
    if f and f.get("sponsor_ids"): return f['sponsor_ids']
    for c in confs:                                   # else the most recent year that lists sponsors
        if c.get("sponsor_ids"): return c['sponsor_ids']
    return list(ORGS)

def committee_ids_current():
    f = featured()
    if f and f.get("committee_ids"): return f['committee_ids']
    for c in confs:
        if c.get("committee_ids"): return c['committee_ids']
    return []

def weekday(s): return d(s).strftime("%A")
def long_date(s): return d(s).strftime("%B %-d, %Y") if os.name != "nt" else d(s).strftime("%B %d, %Y")

def validate():
    problems = []
    years = [c['year'] for c in confs]
    if len(years) != len(set(years)): problems.append("duplicate conference years")
    for c in confs:
        y = c['year']
        if c.get("start_date") and not c.get("end_date"): problems.append(f"{y}: start_date without end_date")
        if c.get("host") and c['host'].get("org_id") not in ORGS: problems.append(f"{y}: unknown host org_id")
        for i in c.get("sponsor_ids", []):
            if i not in ORGS: problems.append(f"{y}: unknown sponsor id {i}")
        for i in c.get("committee_ids", []):
            if i not in PEOPLE: problems.append(f"{y}: unknown person id {i}")
        for key in ("program_pdf",):
            if c.get(key) and not os.path.exists(os.path.join(SITE, "assets", "programs", c[key]['file'])):
                problems.append(f"{y}: missing assets/programs/{c[key]['file']}")
        dc = c.get("doctoral_consortium", {})
        if dc.get("program_pdf") and not os.path.exists(os.path.join(SITE, "assets", "programs", dc['program_pdf']['file'])):
            problems.append(f"{y}: missing assets/programs/{dc['program_pdf']['file']}")
        if c.get("photo") and not os.path.exists(os.path.join(SITE, "assets", "img", c['photo']['file'])):
            problems.append(f"{y}: missing assets/img/{c['photo']['file']}")
        kd = [k['date'] for k in c.get("key_dates", [])]
        if kd != sorted(kd): problems.append(f"{y}: key_dates out of order")
    for i, o in ORGS.items():
        if not os.path.exists(os.path.join(SITE, "assets", "img", o['logo'])): problems.append(f"org {i}: missing logo {o['logo']}")
    if len([c for c in confs if status(c) == "upcoming"]) > 1:
        problems.append("more than one upcoming conference; check the dates")
    if problems:
        sys.exit("build.py stopped. Fix these and run again:\n  - " + "\n  - ".join(problems))
    f = featured()
    if f is None:
        print("note: no upcoming or to-be-announced conference; Home shows the most recent one as past.")
    else:
        print(f"featured: WCRS {f['year']} ({status(f)}" + (f", ends {f['end_date']}" if f.get("end_date") else "") + f") · today {TODAY}")

# ----------------------------------------------------------------------------- context (multi-page vs single-file)
class Ctx:
    def __init__(self, mode, depth=0):
        self.mode, self.depth, self.rel = mode, depth, "../" * depth
    def href(self, slug, anchor=None):
        if self.mode != "multi":
            return "#" + slug + (f"--{anchor}" if anchor else "")
        if slug == "home": path = self.rel + "index.html"
        elif slug.startswith("conference-"): path = self.rel + "conferences/" + slug.split("-")[1] + ".html"
        else: path = self.rel + slug + ".html"
        return path + (f"#{anchor}" if anchor else "")
    def img(self, name):
        return self.rel + "assets/img/" + name if self.mode == "multi" else data_uri(os.path.join(SITE, "assets", "img", name))
    def pdf(self, info):
        if not info: return None, None
        if self.mode == "multi": return self.rel + "assets/programs/" + info['file'], None
        if info.get("legacy_url"): return info['legacy_url'], "opens the copy on the current WCRS site"
        return None, "published with the site"

@lru_cache(maxsize=None)
def data_uri(path):
    mime = "image/jpeg" if path.lower().endswith((".jpg", ".jpeg")) else "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()

# ----------------------------------------------------------------------------- small markup helpers (keep f-strings simple; Python 3.9)
def cref(ctx, c, anchor=None):
    """Link to a conference-year page (kept out of f-strings for Python 3.9)."""
    return ctx.href("conference-%d" % c["year"], anchor)

def link(url, text, cls=None):
    c = f' class="{cls}"' if cls else ""
    return f'<a href="{e(url)}"{c}>{text}</a>'

def person_card(pid, role=None):
    p = person(pid)
    name = link(p['url'], e(p['name'])) if p.get("url") else e(p['name'])
    sub = e(p['school']) + (" · " + e(role or p.get("role")) if (role or p.get("role")) else "")
    return f'<div class="person"><b>{name}</b><span>{sub}</span></div>'

def author_line(p):
    return f'<span class="pa">{e(p["authors"])}</span>' if p.get("authors") else ""

def pdf_button(ctx, info, label):
    if not info: return ""
    href, note = ctx.pdf(info)
    if href:
        t = f' title="{e(note)}"' if note else ""
        return f'<a class="pdf" href="{e(href)}"{t}><span class="ic">PDF</span>{label}</a>'
    return f'<span class="pdf off" title="{e(note)}"><span class="ic">PDF</span>{label} · {e(note)}</span>'

def place_line(c):
    """'The Banff Centre, Banff, Alberta' / 'University of Washington, Seattle, WA' / 'University of Washington · Held online'."""
    pl, v = c.get("place", {}), c.get("venue")
    school = org(c['host']['org_id'])['school'] if c.get("host") else ""
    if pl.get("mode") == "virtual": return f"{school} · {pl.get('city_display', 'Held online')}"
    head = v['short'] if v and c is featured() else school
    return f"{head}, {pl.get('city_display', '')}".strip(", ")

def row_title(c):
    """Index rows name the business school and the city, not the building (Emily, 2026.09.03)."""
    host = c.get("host", {}); pl = c.get("place", {})
    name = host.get("school_display") or org(host["org_id"]).get("row_name") or org(host["org_id"])["school"]
    if pl.get("mode") == "virtual": return f"{name} · {pl.get('city_display', 'Held online')}"
    return f"{name}, {pl.get('city_display', '')}".strip(", ")

def one_liner(c):
    bits = []
    if c.get("dates_display"): bits.append(c["dates_display"])
    if c.get("theme"): bits.append(c["theme"])
    return " · ".join(bits)

# ----------------------------------------------------------------------------- CSS
@lru_cache(maxsize=None)
def css(mode, depth):
    ctx = Ctx(mode, depth)
    photos = sorted({c['photo']['file'] for c in confs if c.get("photo")})
    photo_rules = "".join(f'.ph-{os.path.splitext(n)[0]}{{background-image:url("{ctx.img(n)}")}}\n' for n in photos)
    draft = "" if mode == "multi" else """
body{padding-top:34px}
.draft-bar{position:fixed;top:0;left:0;right:0;z-index:100;background:#22292f;color:#d9dde2;font:500 12px/1 var(--sans);letter-spacing:.04em;display:flex;gap:16px;align-items:center;padding:0 16px;height:34px}
.draft-bar b{color:#fff}.draft-bar span{color:#9aa4ad}
@media (max-width:640px){.draft-bar span{display:none}}
header.site{top:34px}
"""
    return "/* WCRS — generated by build.py; edit build.py, not this file */\n" + r"""
:root{
  --paper:#f7f3ec; --paper-2:#efe9de; --paper-3:#e6dfd1;
  --ink:#12263a; --ink-2:#0b1a29; --slate:#3b5266; --slate-2:#5d7386;
  --text:#1c2730; --muted:#5e6b76;
  --amber:#c47a2c; --amber-2:#e0995a; --amber-soft:#f4e2cc;
  --hair:#d8cfc0; --hair-2:#e4dccf;
  --serif:"Newsreader","Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Inter","Helvetica Neue",Helvetica,Arial,system-ui,sans-serif;
  color-scheme:light;
}
*,*::before,*::after{box-sizing:border-box}
html{background:var(--paper);scroll-behavior:smooth}
body{margin:0;background:var(--paper);color:var(--text);font-family:var(--serif);font-size:18px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:var(--slate);text-decoration-thickness:1px;text-underline-offset:3px}
a:hover{color:var(--ink)}
a:focus-visible{outline:2px solid var(--amber);outline-offset:3px}
img{max-width:100%;display:block}
.wrap{max-width:1120px;margin:0 auto;padding:0 28px}
.skip{position:absolute;left:-9999px;top:0;background:var(--ink);color:#fff;padding:10px 16px;font:600 .8rem var(--sans);z-index:200}
.skip:focus{left:0}
""" + draft + r"""
header.site{background:var(--paper);border-bottom:1px solid var(--hair);position:sticky;top:0;z-index:50}
.bar{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:14px 0}
.brand{display:flex;align-items:center;gap:14px;text-decoration:none;color:var(--ink)}
.mono{width:46px;height:46px;border-radius:6px;background:var(--ink);color:#fff;display:grid;place-items:center;font:700 13px/1 var(--sans);letter-spacing:.06em;flex:none;position:relative;overflow:hidden}
.mono::after{content:"";position:absolute;left:0;right:0;bottom:0;height:5px;background:linear-gradient(90deg,var(--amber),var(--amber-2))}
.brand .t1{display:block;font:600 1.05rem/1.1 var(--serif);color:var(--ink)}
.brand .t2{display:block;font:500 .66rem/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-top:5px}
nav.top{display:flex;gap:22px;flex-wrap:wrap;font:600 .74rem/1 var(--sans);letter-spacing:.1em;text-transform:uppercase}
nav.top a{color:var(--slate);text-decoration:none;padding:6px 0;border-bottom:2px solid transparent;white-space:nowrap}
nav.top a:hover{color:var(--ink);border-bottom-color:var(--amber)}
nav.top a[aria-current="page"]{color:var(--ink);border-bottom-color:var(--ink)}
nav.top a.feat{color:var(--amber)}
@media (max-width:900px){nav.top{gap:14px;font-size:.68rem}}
@media (max-width:720px){.bar{flex-direction:column;align-items:flex-start;gap:12px}}
.view{display:none}.view.on{display:block}
main.page{display:block}
section[id]{scroll-margin-top:90px}

/* hero (home) */
.hero{position:relative;background:var(--ink-2);color:#fff;overflow:hidden;min-height:560px;display:flex}
.hero.plain,.cover.plain{background:linear-gradient(120deg,var(--ink-2),var(--ink) 60%,#1d3a55)}
.hero .photo,.cover .photo{position:absolute;inset:0;background-position:center 45%;background-size:cover;background-repeat:no-repeat}
.hero .scrim{position:absolute;inset:0;background:linear-gradient(100deg,rgba(11,26,41,.92) 0%,rgba(11,26,41,.82) 38%,rgba(11,26,41,.35) 68%,rgba(11,26,41,.15) 100%)}
.hero .wrap{position:relative;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(300px,.85fr);gap:48px;align-items:end;padding-top:64px;padding-bottom:56px;width:100%}
.kicker{font:600 .7rem/1.4 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--amber-2);margin:0 0 18px}
.hero h1{font:400 clamp(2rem,4.6vw,3.4rem)/1.08 var(--serif);letter-spacing:-.01em;margin:0 0 22px;max-width:16ch;text-wrap:balance}
.hero h1 em{font-style:italic;color:#f1d7b7}
.hero .lede,.cover .lede{font-size:1.1rem;line-height:1.6;color:#dbe3ea;max-width:52ch;margin:0}
.credit{position:absolute;right:16px;bottom:10px;font:400 .62rem/1 var(--sans);letter-spacing:.06em;color:rgba(255,255,255,.7)}
.next{background:rgba(247,243,236,.97);color:var(--text);border-radius:8px;padding:26px 26px 24px;box-shadow:0 18px 50px rgba(0,0,0,.35);border-top:5px solid var(--amber)}
.next .lbl{font:700 .66rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--amber);margin:0 0 12px}
.next h2{font:500 1.55rem/1.15 var(--serif);margin:0 0 6px;color:var(--ink)}
.next .when{font:600 1.05rem/1.3 var(--sans);color:var(--ink);margin:0 0 4px}
.next .where{margin:0 0 12px;color:var(--muted);font-size:1rem}
.next .theme{font-size:.98rem;line-height:1.5;margin:0 0 18px;padding-top:12px;border-top:1px solid var(--hair)}
.btns{display:flex;gap:10px;flex-wrap:wrap}
.btn{display:inline-block;font:600 .74rem/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;text-decoration:none;padding:12px 16px;border-radius:4px;border:1.5px solid var(--ink);color:var(--ink)}
.btn.solid{background:var(--ink);color:#fff}
.btn.solid:hover{background:var(--slate)}
.btn:hover{border-color:var(--amber);color:var(--ink)}
@media (max-width:860px){.hero .wrap{grid-template-columns:1fr;gap:28px;padding-top:48px}.hero{min-height:0}.hero h1{max-width:none}}

/* key dates */
.dates{background:var(--ink);color:#fff}
.dates .wrap{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}
.date{padding:22px 20px 20px;border-left:1px solid rgba(255,255,255,.12)}
.date:first-child{border-left:0}
.date .d{font:500 1.3rem/1 var(--serif);color:#fff}
.date .w{font:500 .82rem/1.4 var(--sans);color:#c9d3dc;margin-top:8px}
.date.past .d,.date.past .w{color:#8797a5}
.date .tag{display:inline-block;font:700 .58rem/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;padding:4px 6px;border-radius:3px;margin-top:10px;background:rgba(255,255,255,.1);color:#aab7c2}
.date.upcoming .tag{background:var(--amber);color:#fff}
@media (max-width:900px){.dates .wrap{padding:0}.date{border-left:0;border-top:1px solid rgba(255,255,255,.12);padding:18px 24px}}

/* sections */
section.block{padding-top:60px;padding-bottom:12px}
.label{font:700 .68rem/1.4 var(--sans);letter-spacing:.22em;text-transform:uppercase;color:var(--amber);margin:0 0 16px}
.label.gap{margin-top:48px}
h2.head{font:400 clamp(1.5rem,2.6vw,2.05rem)/1.2 var(--serif);color:var(--ink);margin:0 0 18px;letter-spacing:-.01em;text-wrap:balance}
h3.sub{font:500 1.2rem/1.3 var(--serif);color:var(--ink);margin:30px 0 10px}
.prose{max-width:68ch}.prose p{margin:0 0 16px}
.lead{font-size:1.16rem;line-height:1.55}
.band{background:var(--paper-2);border-top:1px solid var(--hair-2);border-bottom:1px solid var(--hair-2);margin-top:48px}
.band section.block{padding-top:52px;padding-bottom:44px}
.small{font:400 .82rem/1.5 var(--sans);color:var(--muted)}

/* sponsors */
.sponsors{padding-top:34px;padding-bottom:30px;border-bottom:1px solid var(--hair-2)}
.sponsors .label{text-align:center;margin-bottom:22px;color:var(--muted)}
.logos{display:flex;flex-wrap:wrap;justify-content:center;align-items:center;gap:18px 34px}
.logos a{background:#fff;border:1px solid var(--hair-2);border-radius:4px;padding:10px 16px;height:64px;display:flex;align-items:center}
.logos img{height:34px;width:auto;max-width:210px;object-fit:contain}
.logos a:hover{border-color:var(--amber)}
@media (max-width:720px){.logos{gap:12px}.logos a{height:56px;padding:8px 12px}.logos img{height:28px;max-width:160px}}

/* cards */
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;margin-top:10px}
.card{background:#fff;border:1px solid var(--hair-2);border-top:3px solid var(--slate);padding:22px 22px 24px;border-radius:0 0 4px 4px}
.card h3{font:500 1.12rem/1.25 var(--serif);color:var(--ink);margin:0 0 8px}
.card p{margin:0;font-size:.97rem;color:var(--muted);line-height:1.5}

/* call */
.call{display:grid;grid-template-columns:1.4fr 1fr;gap:40px;align-items:start}
.side{background:#fff;border:1px solid var(--hair-2);padding:24px;border-radius:4px}
.side dl{margin:0;display:grid;grid-template-columns:auto 1fr;gap:8px 18px;font-size:.98rem}
.side dt{font:600 .68rem/1.6 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted)}
.side dd{margin:0}
.chip{display:inline-block;font:700 .58rem/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;padding:4px 6px;border-radius:3px;background:var(--paper-3);color:var(--muted);margin-left:8px;vertical-align:middle}
.chip.open{background:var(--amber);color:#fff}
@media (max-width:860px){.call{grid-template-columns:1fr}}

/* stats */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;background:var(--hair);border:1px solid var(--hair);margin:12px 0 34px}
.stat{background:var(--paper);padding:22px 20px}
.stat .n{font:400 2.2rem/1 var(--serif);color:var(--ink);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.stat .t{font:600 .66rem/1.4 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-top:10px}

/* conference rows */
.rows{margin-top:6px}
.row{display:grid;grid-template-columns:110px 1fr auto;gap:24px;align-items:baseline;padding:22px 0;border-top:1px solid var(--hair);text-decoration:none;color:inherit}
.row:last-child{border-bottom:1px solid var(--hair)}
.row .yr{font:400 1.9rem/1 var(--serif);color:var(--ink);letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.row .yr small{display:block;font:600 .62rem/1.4 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--amber);margin-top:8px}
.row h3{font:500 1.15rem/1.3 var(--serif);margin:0 0 4px;color:var(--ink)}
.row p{margin:0;color:var(--muted);font-size:.98rem}
.row .go{font:600 .68rem/1 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--slate);white-space:nowrap}
a.row:hover h3{color:var(--amber)}
.row.quiet .yr,.row.quiet h3{color:var(--muted)}
.row.quiet .yr small{color:var(--slate-2)}
@media (max-width:640px){.row{grid-template-columns:1fr;gap:6px}.row .go{display:none}}
table.hosts{border-collapse:collapse;width:100%;max-width:640px;font-size:.98rem;margin-top:8px}
table.hosts th,table.hosts td{text-align:left;padding:10px 12px 10px 0;border-top:1px solid var(--hair-2)}
table.hosts th{font:600 .68rem/1.6 var(--sans);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);border-top:0}
table.hosts td.n{font-variant-numeric:tabular-nums;color:var(--ink)}
table.hosts td.y{font:400 .85rem/1.5 var(--sans);color:var(--muted)}

/* interior covers */
.cover{position:relative;background:var(--ink-2);color:#fff;overflow:hidden}
.cover .scrim{position:absolute;inset:0;background:linear-gradient(90deg,rgba(11,26,41,.94) 0%,rgba(11,26,41,.8) 50%,rgba(11,26,41,.4) 100%)}
.cover .wrap{position:relative;padding-top:44px;padding-bottom:52px}
.backlink{font:600 .68rem/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:#aab7c2;text-decoration:none;display:inline-block;margin-bottom:26px}
.backlink:hover{color:#fff}
.cover h1{font:400 clamp(1.8rem,3.6vw,2.7rem)/1.12 var(--serif);margin:0 0 14px;max-width:26ch;letter-spacing:-.01em;text-wrap:balance}
.cover .lede{max-width:60ch}
.subnav{display:flex;gap:18px;flex-wrap:wrap;margin-top:26px;font:600 .68rem/1 var(--sans);letter-spacing:.14em;text-transform:uppercase}
.subnav a{color:#dbe3ea;text-decoration:none;border-bottom:1px solid rgba(255,255,255,.25);padding-bottom:4px}
.subnav a:hover{color:#fff;border-color:var(--amber-2)}

/* facts */
.facts{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1px;background:var(--hair);border:1px solid var(--hair);margin:0 0 8px}
.facts > div{background:#fff;padding:18px 20px}
.facts dt{font:600 .64rem/1.4 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--muted);margin-bottom:6px}
.facts dd{margin:0;font-size:1rem;line-height:1.45}
.facts dd small{display:block;color:var(--muted);font-size:.9rem;margin-top:2px}
.pdfs{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 0;align-items:center}
.pdf{display:inline-flex;align-items:center;gap:10px;text-decoration:none;font:600 .8rem/1 var(--sans);color:var(--ink);background:#fff;border:1.5px solid var(--ink);padding:12px 16px;border-radius:4px}
.pdf:hover{border-color:var(--amber)}
.pdf .ic{display:inline-grid;place-items:center;width:24px;height:28px;background:var(--amber);color:#fff;border-radius:2px;font:700 .5rem/1 var(--sans);letter-spacing:.05em}
.pdf.off{border-style:dashed;color:var(--muted);border-color:var(--hair)}
.pdf.off .ic{background:var(--paper-3);color:var(--muted)}

/* paper list */
.plist{list-style:none;margin:8px 0 0;padding:0;counter-reset:p}
.plist li{display:grid;grid-template-columns:44px 1fr;gap:14px;padding:12px 0;border-top:1px solid var(--hair-2)}
.plist li::before{counter-increment:p;content:counter(p);font:500 1rem/1.4 var(--serif);color:var(--amber);font-variant-numeric:tabular-nums}
.plist .pt{display:block;font-size:1.02rem;line-height:1.4;color:var(--text)}
.plist .pa{display:block;font:400 .84rem/1.5 var(--sans);color:var(--muted);margin-top:2px}
.hl{margin:0;padding-left:20px}.hl li{margin-bottom:8px}

.callout{background:var(--amber-soft);border-left:4px solid var(--amber);padding:18px 22px;margin:34px 0 0;border-radius:0 4px 4px 0}
.callout p{margin:0;font-size:1rem}
.callout .ct{font:700 .66rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--amber);margin:0 0 8px}
.two{display:grid;grid-template-columns:1fr 1fr;gap:40px}
@media (max-width:760px){.two{grid-template-columns:1fr}}
.plain{list-style:none;margin:0;padding:0}
.plain li{padding:9px 0;border-top:1px solid var(--hair-2);font-size:1rem}
.plain li:last-child{border-bottom:1px solid var(--hair-2)}
.plain li span{color:var(--muted);font:400 .85rem/1.4 var(--sans);display:block}
.plain li a{text-decoration:none;color:var(--ink);border-bottom:1px solid var(--hair)}
.plain li a:hover{color:var(--amber);border-color:var(--amber)}
.pager{display:flex;justify-content:space-between;gap:20px;margin:48px 0 0;padding-top:20px;border-top:1px solid var(--hair);font:600 .74rem/1.4 var(--sans);letter-spacing:.12em;text-transform:uppercase}
.pager a{text-decoration:none;color:var(--slate)}.pager a:hover{color:var(--amber)}

/* timeline (about) */
.tl{list-style:none;margin:10px 0 0;padding:0;border-left:2px solid var(--hair)}
.tl li{position:relative;padding:0 0 22px 26px}
.tl li::before{content:"";position:absolute;left:-7px;top:9px;width:12px;height:12px;border-radius:50%;background:var(--amber);border:2px solid var(--paper)}
.tl .y{font:600 .7rem/1.4 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--amber)}
.tl .w{font-size:1.02rem;color:var(--ink)}
.tl .s{font:400 .85rem/1.5 var(--sans);color:var(--muted)}

/* people */
.people{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px;margin-top:8px}
.person{background:#fff;border:1px solid var(--hair-2);padding:18px 20px;border-radius:4px}
.person b{display:block;font:500 1.08rem/1.3 var(--serif);color:var(--ink)}
.person b a{text-decoration:none;color:var(--ink);border-bottom:1px solid var(--hair)}
.person b a:hover{color:var(--amber);border-color:var(--amber)}
.person span{display:block;font:400 .84rem/1.5 var(--sans);color:var(--muted);margin-top:4px}
.sponsor-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin-top:8px}
.sponsor{display:grid;grid-template-columns:150px 1fr;gap:18px;align-items:center;background:#fff;border:1px solid var(--hair-2);padding:16px 18px;border-radius:4px;text-decoration:none;color:inherit}
.sponsor img{height:34px;width:auto;max-width:150px;object-fit:contain}
.sponsor b{display:block;font:500 1.02rem/1.3 var(--serif);color:var(--ink)}
.sponsor span{display:block;font:400 .82rem/1.5 var(--sans);color:var(--muted)}
.sponsor:hover{border-color:var(--amber)}
.links{list-style:none;margin:10px 0 0;padding:0;font:500 .9rem/1.6 var(--sans)}
.links li{margin:0 0 6px}

/* footer */
footer.site{background:var(--ink-2);color:#c9d3dc;margin-top:64px;padding:48px 0 30px;font-size:.95rem}
.fgrid{display:grid;grid-template-columns:1.4fr 1fr 1fr;gap:40px}
footer h4{font:600 .68rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;color:var(--amber-2);margin:0 0 14px}
footer p{margin:0 0 12px;line-height:1.55}
footer ul{list-style:none;margin:0;padding:0}footer li{margin:0 0 8px}
footer a{color:#fff;text-decoration:none}footer a:hover{color:var(--amber-2)}
.fine{margin-top:36px;padding-top:18px;border-top:1px solid rgba(255,255,255,.12);font:400 .72rem/1.6 var(--sans);letter-spacing:.05em;color:#8797a5}
@media (max-width:760px){.fgrid{grid-template-columns:1fr;gap:28px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
""" + photo_rules

# ----------------------------------------------------------------------------- chrome
def nav_items():
    """Home · WCRS <featured year> · Conferences · People · About. The featured item is generated, never typed."""
    items = [("home", "Home")]
    f = featured()
    if f: items.append((f"conference-{f['year']}", f"WCRS {f['year']}"))
    items += [("conferences", "Conferences"), ("people", "People"), ("about", "About")]
    return items

def header(ctx, current):
    links = ""
    for slug, label in nav_items():
        is_feat = slug.startswith("conference-")
        cur = current == slug or (slug == "conferences" and current.startswith("conference-") and not is_feat and current != (f"conference-{featured()['year']}" if featured() else ""))
        attrs = ' aria-current="page"' if cur else ""
        cls = ' class="feat"' if is_feat else ""
        links += f'<a href="{ctx.href(slug)}" data-slug="{slug}"{cls}{attrs}>{e(label)}</a>'
    return (f'<a class="skip" href="#main">Skip to content</a>\n<header class="site"><div class="wrap bar">'
            f'<a class="brand" href="{ctx.href("home")}"><span class="mono" aria-hidden="true">WCRS</span>'
            f'<span><span class="t1">{e(site["short_name"])}</span><span class="t2">on Technology Entrepreneurship</span></span></a>'
            f'<nav class="top" aria-label="Main">{links}</nav></div></header>')

def footer(ctx):
    schools = schools_of(sponsor_ids_current())
    blurb = (f"{site['tagline']}, initiated in {site['founded_city']} in {site['founded']} and sponsored by "
             f"{num_word(len(schools))} schools: {', '.join(schools[:-1])}, and {schools[-1]}. Registration runs through the host school each year.")
    pages = "".join(f'<li><a href="{ctx.href(s)}">{e(l)}</a></li>' for s, l in nav_items())
    pages += f'<li><a href="{ctx.href("about", "papers")}">Papers</a></li><li><a href="{ctx.href("people", "contact")}">Contact</a></li>'
    roles = f'<p><a href="mailto:{e(site["contact"]["email"])}">{e(site["contact"]["email_label"])}</a><br>{e(site["contact"]["email"])}</p>'
    f = featured()
    if f and f.get("host", {}).get("contact_person_id"):
        p = person(f["host"]["contact_person_id"])
        roles += f"<p>{e(f['host'].get('contact_role', 'Conference'))}, {f['year']}: {e(p['name'])}, {e(p['school'])}.</p>"
    return (f'<footer class="site"><div class="wrap"><div class="fgrid">'
            f'<div><h4>{e(site["short_name"])}</h4><p>{e(blurb)}</p><p>{e(site["papers_policy"]["paragraphs"][0].split(". For that reason")[0])}. Papers are shared with participants directly and are not hosted on this site.</p></div>'
            f'<div><h4>Pages</h4><ul>{pages}</ul></div><div><h4>Contact</h4>{roles}</div></div>'
            f'<p class="fine">{e(site["full_name"])} · Since {site["founded"]} · Generated {BUILD_DATE}</p></div></footer>')

# ----------------------------------------------------------------------------- shared blocks
def sponsor_strip(ctx, ids=None):
    ids = ids or sponsor_ids_current()
    logos = "".join(f'<a href="{e(org(i)["url"])}" title="{e(org(i)["unit"])}, {e(org(i)["school"])}"><img src="{ctx.img(org(i)["logo"])}" alt="{e(org(i)["unit"])}, {e(org(i)["school"])}"></a>' for i in ids)
    return f'<section class="sponsors"><div class="wrap"><p class="label">Sponsored by {num_word(len(schools_of(ids)))} schools</p><div class="logos">{logos}</div></div></section>'

def row(ctx, c):
    y, st = c['year'], status(c)
    href = ctx.href(f"conference-{y}")
    if st == "none":
        return f'<a class="row quiet" href="{href}"><span class="yr">{y}<small>Not held</small></span><span><h3>No symposium</h3><p>{e(c.get("note"))}</p></span><span class="go">Note →</span></a>'
    if st == "tba":
        return f'<a class="row quiet" href="{href}"><span class="yr">{y}<small>Next</small></span><span><h3>To be announced</h3><p>{e(c.get("note"))}</p></span><span class="go">Details →</span></a>'
    tag = ("Next · " if st == "upcoming" else "") + ordinal(c)
    go = "Conference page →" if st == "upcoming" else ("Program →" if c.get("program_pdf") else "Details →")
    return f'<a class="row" href="{href}"><span class="yr">{y}<small>{e(tag)}</small></span><span><h3>{e(row_title(c))}</h3><p>{e(one_liner(c))}</p></span><span class="go">{go}</span></a>'

def next_card(ctx, f):
    """The featured-conference card on Home. Every field optional; a TBA year renders honestly."""
    if f is None:
        last = concluded()[0]
        return (f'<aside class="next" aria-label="Most recent conference"><p class="lbl">Most recent</p><h2>WCRS {last["year"]} · {e(ordinal(last))} symposium</h2>'
                f'<p class="where">{e(place_line(last))}</p><div class="btns"><a class="btn solid" href="{cref(ctx, last)}">Conference page</a></div></aside>')
    st = status(f)
    head = f"WCRS {f['year']}" + (f" · {ordinal(f)} symposium" if ordinal(f) else "")
    if st == "tba":
        return (f'<aside class="next" aria-label="Next conference"><p class="lbl">Next conference</p><h2>{e(head)}</h2>'
                f'<p class="where">{e(f.get("note", "To be announced."))}</p><div class="btns"><a class="btn" href="{ctx.href("conferences")}">All conferences</a></div></aside>')
    host = f.get("host", {})
    hosted = f"Hosted by the {host['unit']}, {org(host['org_id'])['school']}" if host.get("unit") else f"Hosted by {org(host['org_id'])['school']}"
    theme = ""
    if f.get("theme"):
        kn = f.get("keynote")
        theme = f'<p class="theme"><b>Theme:</b> {e(f["theme"])}.' + (f' Keynote by {e(kn["speaker"])}, {e(kn["affiliation"])}.' if kn else "") + "</p>"
    btns = f'<a class="btn solid" href="{cref(ctx, f)}">Conference page</a>'
    if f.get("call_for_papers"): btns += f'<a class="btn" href="{cref(ctx, f, "call-for-papers")}">Call for papers</a>'
    if f.get("travel"): btns += f'<a class="btn" href="{cref(ctx, f, "travel")}">Travel</a>'
    return (f'<aside class="next" aria-label="Next conference"><p class="lbl">Next conference</p><h2>{e(head)}</h2>'
            f'<p class="when">{e(f.get("dates_display", ""))}</p><p class="where">{e(place_line(f))}<br>{e(hosted)}</p>{theme}<div class="btns">{btns}</div></aside>')

def key_dates_band(f):
    if not f or not f.get("key_dates"): return ""
    cells = ""
    for k in f['key_dates']:
        past = d(k.get("end_date", k['date'])) < TODAY
        disp = d(k['date']).strftime("%b %-d") if os.name != "nt" else d(k['date']).strftime("%b %d")
        if k.get("end_date"): disp += "–" + str(d(k['end_date']).day)
        if k.get("kind") == "deadline": tag = "Closed" if past else "Deadline"
        else: tag = weekday(k['date'])[:3] + ("–" + weekday(k['end_date'])[:3] if k.get("end_date") else "")
        cells += f'<div class="date {"past" if past else "upcoming"}"><div class="d">{e(disp)}</div><div class="w">{e(k["what"])}</div><span class="tag">{e(tag)}</span></div>'
    return f'<section class="dates" aria-label="Key dates for WCRS {f["year"]}"><div class="wrap">{cells}</div></section>'

# ----------------------------------------------------------------------------- pages
def page_home(ctx):
    f = featured()
    photo = f.get("photo") if f else None
    if not photo:
        for c in confs:
            if c.get("photo"): photo = c['photo']; break
    hero_bg = f'<div class="photo ph-{os.path.splitext(photo["file"])[0]}" role="img" aria-label="{e(photo["alt"])}"></div><div class="scrim"></div>' if photo else ""
    credit = f'<span class="credit">{e(photo["credit"])}</span>' if photo else ""
    cards = "".join(f'<div class="card"><h3>{e(c["title"])}</h3><p>{e(c["text"])}</p></div>' for c in site['what_wcrs_is']['cards'])
    recent = [c for c in confs if status(c) in ("upcoming", "past")][:4]
    rows = "".join(row(ctx, c) for c in sorted(recent + [c for c in confs if status(c) == "tba"], key=lambda c: -c['year']))
    n_held = len(concluded()); n_all = len(held_years())
    cities = list(dict.fromkeys(c['place']['city'] for c in sorted(confs, key=lambda c: c['year']) if status(c) in ("past", "upcoming") and c.get("place", {}).get("city")))
    schools = schools_of(sponsor_ids_current())
    call = ""
    if f and f.get("call_for_papers"):
        cf = f['call_for_papers']; open_ = d(cf['deadline']) >= TODAY
        chip = f'<span class="chip {"open" if open_ else ""}">{"Deadline " if open_ else "Submissions closed "}{e(cf["deadline_display"])}</span>'
        verb = "especially encourages" if open_ else "especially encouraged"
        call = (f'<div class="band"><section class="block wrap"><div class="call"><div><p class="label">Call for papers</p><h2 class="head">WCRS {f["year"]} {chip}</h2>'
                f'<div class="prose"><p>In addition to its broad focus on technology entrepreneurship, for {f["year"]} the symposium {verb} submissions on <b>{e(cf["emphasis_short"])}</b>: {e(cf["emphasis"])}.</p>'
                f'<a class="btn" href="{cref(ctx, f, "call-for-papers")}">Read the full call</a></div></div>'
                f'<div class="side"><dl><dt>Where</dt><dd>{e(place_line(f))}</dd><dt>When</dt><dd>{e(f.get("dates_display", ""))}</dd><dt>Host</dt><dd>{e(f["host"]["unit"])}, {e(org(f["host"]["org_id"])["school"])}</dd>'
                f'<dt>Deadline</dt><dd>{e(cf["deadline_display"])}{"" if open_ else " (closed)"}</dd><dt>Format</dt><dd>{e(site["format_note"])}</dd><dt>Submissions</dt><dd>{e(cf.get("submissions_note", ""))}</dd></dl></div></div></section></div>')
    first_city, last_city = (cities[0], cities[-1]) if cities else (site['founded_city'], site['founded_city'])
    return f"""
<section class="hero{'' if photo else ' plain'}">{hero_bg}<div class="wrap">
  <div><p class="kicker">Annual since {site['founded']} · {num_word(len(schools), True)} sponsoring schools</p>
    <h1>{e(site['short_name'])} on <em>Technology Entrepreneurship</em></h1>
    <p class="lede">{e(site['home_lede'])}</p></div>
  {next_card(ctx, f)}
</div>{credit}</section>
{key_dates_band(f)}
{sponsor_strip(ctx)}
<section class="block wrap"><p class="label">What WCRS is</p><h2 class="head">{e(site['what_wcrs_is']['heading'])}</h2>
  <div class="prose"><p class="lead">{e(site['what_wcrs_is']['lead'])}</p></div><div class="cards">{cards}</div></section>
{call}
<section class="block wrap"><p class="label">Since {site['founded']}</p><h2 class="head">{num_word(n_all, True)} symposia, {num_word(len(cities))} host cities, one idea</h2>
  <div class="stats"><div class="stat"><div class="n">{site['founded']}</div><div class="t">First symposium, {e(site['founded_city'])}</div></div>
  <div class="stat"><div class="n">{n_held}</div><div class="t">Symposia held to date</div></div>
  <div class="stat"><div class="n">{len(schools)}</div><div class="t">Sponsoring schools</div></div>
  <div class="stat"><div class="n">{len(cities)}</div><div class="t">Host cities, {e(first_city)} to {e(last_city)}</div></div></div>
  <div class="prose"><p>{e(site['about']['genesis'][1])}</p><p><a href="{ctx.href('about')}">About WCRS →</a></p></div></section>
<div class="band"><section class="block wrap"><p class="label">Conferences</p><h2 class="head">Recent symposia</h2><div class="rows">{rows}</div>
<p style="margin-top:22px"><a href="{ctx.href('conferences')}">All conferences, {site['founded']} to today →</a></p></section></div>"""

def page_about(ctx):
    a = site['about']
    what = "".join(f"<p>{e(p)}</p>" for p in a['what_we_do']); gen = "".join(f"<p>{e(p)}</p>" for p in a['genesis'])
    how = "".join(f'<div class="card"><h3>{e(c["title"])}</h3><p>{e(c["text"])}</p></div>' for c in a['how_it_works'])
    tl = ""
    for j in a['joiners']:
        names = ", ".join(person(i)['name'] for i in j['people_ids'])
        note = f' · {e(j["note"])}' if j.get("note") else ""
        tl += f'<li><div class="y">{j["year"]}</div><div class="w">{e(names)}</div><div class="s">{e(j["schools"])}{note}</div></li>'
    ids = sponsor_ids_current(); schools = schools_of(ids)
    sp = "".join(f'<li>{link(org(i)["url"], e(org(i)["unit"]))}<span>{e(org(i)["school"])}</span></li>' for i in ids)
    pp = "".join(f'<p class="lead">{e(x)}</p>' for x in site['papers_policy']['paragraphs'])
    return f"""
<section class="cover plain"><div class="wrap"><p class="kicker">About</p><h1>{e(site['full_name'])}</h1>
<p class="lede">{e(site['tagline'])}, initiated in {e(site['founded_city'])} in {site['founded']} and sponsored by {num_word(len(schools))} schools.</p>
<nav class="subnav" aria-label="On this page"><a href="{ctx.href('about', 'how')}">How WCRS works</a><a href="{ctx.href('about', 'schools')}">Schools</a><a href="{ctx.href('about', 'papers')}">Papers</a></nav></div></section>
<section class="block wrap" id="story"><div class="two"><div><p class="label">What we do</p><div class="prose">{what}</div></div><div><p class="label">Our genesis</p><div class="prose">{gen}</div></div></div></section>
<div class="band"><section class="block wrap" id="how"><p class="label">How WCRS works</p><h2 class="head">A small conference run by its sponsoring schools</h2><div class="cards">{how}</div>
<h3 class="sub">Hosting a symposium</h3><div class="prose"><p>{e(a['hosting'])}</p></div></section></div>
<section class="block wrap" id="schools"><div class="two"><div><p class="label">Schools joining the consortium</p><ul class="tl">{tl}</ul></div>
<div><p class="label">Current sponsoring schools</p><ul class="plain">{sp}</ul></div></div></section>
<div class="band"><section class="block wrap" id="papers"><p class="label">Papers</p><h2 class="head">{e(site['papers_policy']['heading'])}</h2><div class="prose">{pp}<p><a class="btn" href="{ctx.href('conferences')}">Conference programs, {site['founded']} to today</a></p></div></section></div>
{sponsor_strip(ctx)}"""

def page_conferences(ctx):
    rows = "".join(row(ctx, c) for c in confs)
    counts = {}
    for c in confs:
        if status(c) in ("past", "upcoming") and c.get("host"):
            k = org(c['host']['org_id'])['school'] + (" (online)" if c.get("place", {}).get("mode") == "virtual" else "")
            counts.setdefault(k, []).append(str(c['year']))
    tr = "".join(f'<tr><td>{e(k)}</td><td class="n">{len(v)}</td><td class="y">{", ".join(sorted(v))}</td></tr>' for k, v in sorted(counts.items(), key=lambda kv: -len(kv[1])))
    return f"""
<section class="cover plain"><div class="wrap"><p class="kicker">Conferences</p><h1>Every symposium since {site['founded']}</h1>
</div></section>
<section class="block wrap"><div class="rows">{rows}</div></section>
<div class="band"><section class="block wrap"><p class="label">Hosts</p><h2 class="head">Who has hosted</h2><table class="hosts"><thead><tr><th>School</th><th>Times</th><th>Years</th></tr></thead><tbody>{tr}</tbody></table></section></div>"""

def page_people(ctx):
    committee = "".join(person_card(i) for i in committee_ids_current())
    founders = "".join(person_card(i) for i in site['founder_ids'])
    ids = sponsor_ids_current(); schools = schools_of(ids)
    spons = "".join(f'<a class="sponsor" href="{e(org(i)["url"])}"><img src="{ctx.img(org(i)["logo"])}" alt=""><span><b>{e(org(i)["unit"])}</b><span>{e(org(i)["school"])}</span></span></a>' for i in ids)
    f = featured(); yr = f['year'] if f and f.get("committee_ids") else None
    roles = f'<div class="person"><b><a href="mailto:{e(site["contact"]["email"])}">{e(site["contact"]["email_label"])}</a></b><span>{e(site["contact"]["email"])} · general enquiries, submissions, and this website</span></div>'
    if f and f.get("host", {}).get("contact_person_id"):
        roles += person_card(f["host"]["contact_person_id"], f"{f['host'].get('contact_role', 'Conference')}, {f['year']}")
    return f"""
<section class="cover plain"><div class="wrap"><p class="kicker">People</p><h1>The steering committee and the sponsoring schools</h1>
<p class="lede">WCRS is run by faculty from its {num_word(len(schools))} sponsoring schools. Names link to school directory pages.</p>
<nav class="subnav" aria-label="On this page"><a href="{ctx.href('people', 'committee')}">Steering committee</a><a href="{ctx.href('people', 'sponsors')}">Sponsors</a><a href="{ctx.href('people', 'contact')}">Contact</a></nav></div></section>
<section class="block wrap" id="committee"><p class="label">Steering committee{(", %s" % yr) if yr else ""}</p><div class="people">{committee}</div>
<p class="label gap">Founders and early conveners</p><div class="people">{founders}</div></section>
<div class="band"><section class="block wrap" id="sponsors"><p class="label">Sponsors</p><h2 class="head">{num_word(len(schools), True)} schools, {num_word(len(ids))} sponsoring units</h2><div class="sponsor-list">{spons}</div></section></div>
<section class="block wrap" id="contact"><p class="label">Contact</p><h2 class="head">Who to ask</h2><div class="people">{roles}</div><p class="small" style="margin-top:14px">{e(site['contact']['note'])}</p></section>"""

# ----- the conference-year page, section by section; every section returns "" when its data is absent
def sec_cover(ctx, c):
    st = status(c); photo = c.get("photo")
    back = f'<a class="backlink" href="{ctx.href("conferences")}">← All conferences</a>'
    kick = f"WCRS {c['year']}" + (f" · {ordinal(c)} symposium" if ordinal(c) else "") + (" · Next conference" if st == "upcoming" else "")
    if st in ("none", "tba"):
        h1 = "No symposium was held" if st == "none" else "To be announced"
        return f'<section class="cover plain"><div class="wrap">{back}<p class="kicker">{e(kick)}</p><h1>{h1}</h1><p class="lede">{e(c.get("note", ""))}</p></div></section>'
    bg = f'<div class="photo ph-{os.path.splitext(photo["file"])[0]}" role="img" aria-label="{e(photo["alt"])}"></div><div class="scrim"></div>' if photo else ""
    credit = f'<span class="credit">{e(photo["credit"])}</span>' if photo else ""
    pl = c.get("place", {}); v = c.get("venue")
    head = (v['short'] if v else org(c['host']['org_id'])['school']) + (f", {pl['city_display']}" if pl.get("city_display") and pl.get("mode") != "virtual" else (" · " + pl.get("city_display", "") if pl.get("mode") == "virtual" else ""))
    if c.get("dates_display"): head += f" · {c['dates_display']}"
    host = c.get("host", {}); school = org(host['org_id'])['school']
    lede = (f"{c['theme']}. " if c.get("theme") else "") + (f"Hosted by the {host['unit']}, {school}." if host.get("unit") else f"Hosted by {school}.")
    sub = ""
    for anchor, label, present in [("key-dates", "Key dates", st == "upcoming" and c.get("key_dates")), ("call-for-papers", "Call for papers", c.get("call_for_papers")),
                                   ("program", "Program", c.get("program_pdf") or c.get("papers")), ("doctoral-consortium", "Doctoral consortium", c.get("doctoral_consortium")), ("travel", "Travel", c.get("travel"))]:
        if present: sub += f'<a href="{cref(ctx, c, anchor)}">{label}</a>'
    subnav = f'<nav class="subnav" aria-label="On this page">{sub}</nav>' if sub else ""
    return f'<section class="cover{"" if photo else " plain"}">{bg}<div class="wrap">{back}<p class="kicker">{e(kick)}</p><h1>{e(head)}</h1><p class="lede">{e(lede)}</p>{subnav}</div>{credit}</section>'

def sec_overview(ctx, c):
    if status(c) in ("none", "tba"): return ""
    facts = []
    def fact(dt, dd, small=None):
        if dd:
            sm = ("<small>%s</small>" % e(small)) if small else ""
            facts.append(f"<div><dt>{dt}</dt><dd>{e(dd)}{sm}</dd></div>")
    fact("Dates", c.get("dates_display"), c.get("dates_note"))
    v = c.get("venue")
    if v: fact("Venue", v['name'], v.get("rooms"))
    elif c.get("place", {}).get("mode") == "virtual": fact("Venue", "Held online")
    host = c.get("host", {})
    fact("Host", host.get("unit") or org(host['org_id'])['school'], host.get("detail") or (org(host['org_id'])['school'] if host.get("unit") else None))
    fact("Theme", c.get("theme"))
    kn = c.get("keynote")
    if kn: fact("Keynote", f"{kn['speaker']}, {kn['affiliation']}", f"“{kn['title']}” · {kn['when']}" if kn.get("title") else kn.get("when"))
    dc = c.get("doctoral_consortium")
    if dc: fact("Doctoral consortium", dc.get("date_display"), (", ".join(f"{o['name']} ({o['school']})" for o in dc['organizers']) if dc.get("organizers") else None))
    if paper_count(c): fact("Papers", f"{paper_count(c)} papers", "Listed below in program order")
    if ordinal(c): fact("Ordinal", f"{ordinal(c)} {site['short_name']}")
    pdfs = pdf_button(ctx, c.get("program_pdf"), "Conference program") + (pdf_button(ctx, dc.get("program_pdf"), "Doctoral consortium program") if dc else "")
    note = f'<p class="small" style="margin-top:18px">Source note: {e(c["source_note"])}</p>' if c.get("source_note") else ""
    hl = "".join(f"<li>{e(x)}</li>" for x in c.get("highlights", []))
    hl = f'<p class="label gap">At a glance</p><ul class="hl">{hl}</ul>' if hl else ""
    return f'<section class="block wrap" id="overview"><dl class="facts">{"".join(facts)}</dl><div class="pdfs">{pdfs}</div>{note}{hl}</section>'

def sec_key_dates(ctx, c):
    if status(c) != "upcoming" or not c.get("key_dates"): return ""
    return key_dates_band(c).replace('<section class="dates"', '<section class="dates" id="key-dates"', 1)

def sec_call(ctx, c):
    cf = c.get("call_for_papers")
    if not cf: return ""
    open_ = d(cf['deadline']) >= TODAY
    chip = f'<span class="chip {"open" if open_ else ""}">{"Deadline " if open_ else "Submissions closed "}{e(cf["deadline_display"])}</span>'
    paras = "".join(f"<p>{e(p)}</p>" for p in cf.get("paragraphs", []))
    closing = f"<p><em>{e(cf['closing_line'])}</em></p>" if cf.get("closing_line") else ""
    comm = "".join(f'<li>{e(person(i)["name"])}<span>{e(person(i)["school"])}</span></li>' for i in c.get("committee_ids", []))
    spon = "".join(f'<li>{e(org(i)["unit"])}<span>{e(org(i)["school"])}</span></li>' for i in c.get("sponsor_ids", []))
    lists = ""
    if comm or spon:
        lists = f'<div class="two" style="margin-top:40px">' + (f'<div><p class="label">Conference steering committee</p><ul class="plain">{comm}</ul></div>' if comm else "") + (f'<div><p class="label">Conference sponsors</p><ul class="plain">{spon}</ul></div>' if spon else "") + "</div>"
    emph = ('<dt>Emphasis</dt><dd>%s</dd>' % e(c["theme"])) if c.get("theme") else ""
    return f"""<div class="band"><section class="block wrap" id="call-for-papers"><div class="call"><div><p class="label">Call for papers</p><h2 class="head">WCRS {c['year']} {chip}</h2><div class="prose">{paras}{closing}
<p class="small">{e(cf.get('submissions_note', ''))}</p></div></div>
<div class="side"><dl><dt>Location</dt><dd>{e(place_line(c))}</dd><dt>Dates</dt><dd>{e(c.get('dates_display', ''))}</dd><dt>Deadline</dt><dd>{e(cf['deadline_display'])}{'' if open_ else ' (closed)'}</dd>{emph}<dt>Format</dt><dd>{e(site['format_note'])}</dd></dl></div></div>{lists}</section></div>"""

def sec_program(ctx, c):
    if status(c) in ("none", "tba"): return ""
    plist = c.get("papers", [])
    if not plist:
        msg = "No program survives for this year, so the papers are not listed." if status(c) == "past" else "The program will be posted here when it is final."
        return f'<section class="block wrap" id="program"><p class="label">Program</p><p class="prose">{msg}</p></section>'
    items = "".join(f'<li><span><span class="pt">{e(p["title"])}</span>{author_line(p)}</span></li>' for p in plist)
    pdfnote = "The program PDF above carries the full schedule with session times." if c.get("program_pdf") else ""
    return f'<section class="block wrap" id="program"><p class="label">Papers presented</p><h2 class="head">{len(plist)} papers, in program order</h2><p class="small">{pdfnote}</p><ol class="plist">{items}</ol></section>'

def sec_doctoral(ctx, c):
    dc = c.get("doctoral_consortium")
    if not dc or not (dc.get("organizers") or dc.get("program_pdf")): return ""
    orgs = "".join(f'<li>{e(o["name"])}<span>{e(o["school"])}</span></li>' for o in dc.get("organizers", []))
    when = e(dc.get("date_display", "")) + (f" · {e(dc['room'])}" if dc.get("room") else "")
    orgs_block = ('<p class="label">Organizers</p><ul class="plain">%s</ul>' % orgs) if orgs else ""
    dc_text = next((k["text"] for k in site["what_wcrs_is"]["cards"] if "consortium" in k["title"].lower()), "")
    return f"""<div class="band"><section class="block wrap" id="doctoral-consortium"><div class="two"><div><p class="label">Doctoral consortium</p><h2 class="head">{when}</h2>
<div class="prose"><p>{e(dc_text)}</p></div><div class="pdfs">{pdf_button(ctx, dc.get('program_pdf'), 'Doctoral consortium program')}</div></div>
<div>{orgs_block}</div></div></section></div>"""

def sec_travel(ctx, c):
    t = c.get("travel")
    if not t: return ""
    v = c.get("venue", {})
    secs = ""
    for s in t.get("sections", []):
        links = "".join(f'<li>{link(l["url"], e(l["label"]))}</li>' for l in s.get("links", []))
        ul = ('<ul class="links">%s</ul>' % links) if links else ""
        secs += f'<div><h3 class="sub">{e(s["title"])}</h3><div class="prose"><p>{e(s["text"])}</p></div>{ul}</div>'
    addr = " · ".join(x for x in [v.get("name"), t.get("address"), f"Tel. {t['phone']}" if t.get("phone") else None] if x)
    return f"""<section class="block wrap" id="travel"><p class="label">Travel and venue</p><h2 class="head">{e(v.get('name', 'Getting there'))}</h2><p class="small">{e(addr)}</p>
<div class="prose"><p class="lead">{e(t.get('intro', ''))}</p></div><div class="two" style="margin-top:20px">{secs}</div></section>"""

def sec_participants(ctx, c):
    if status(c) != "upcoming": return ""
    return f'<section class="wrap"><div class="callout"><p class="ct">For participants</p><p>Full papers are shared with registered participants directly by the organizers; they are not published on this site.</p></div></section>'

def pager(ctx, c):
    i = [x['year'] for x in confs].index(c['year'])
    prev = confs[i + 1] if i + 1 < len(confs) else None; nxt = confs[i - 1] if i > 0 else None
    def lab(x):
        st = status(x)
        tail = " · not held" if st == "none" else (" · to be announced" if st == "tba" else (f" · {x['place'].get('city', x['place'].get('city_display', ''))}" if x.get("place") else ""))
        return f"WCRS {x['year']}{tail}"
    left = f'<a href="{cref(ctx, prev)}">← {e(lab(prev))}</a>' if prev else "<span></span>"
    right = f'<a href="{cref(ctx, nxt)}">{e(lab(nxt))} →</a>' if nxt else f'<a href="{ctx.href("conferences")}">All conferences →</a>'
    return f'<section class="wrap"><nav class="pager" aria-label="Between conferences">{left}{right}</nav></section>'

def page_conference(ctx, c):
    return "".join(fn(ctx, c) for fn in (sec_cover, sec_overview, sec_key_dates, sec_call, sec_program, sec_doctoral, sec_travel, sec_participants, pager))

# ----------------------------------------------------------------------------- assembly
HEAD_LINKS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
              '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..800;1,6..72,300..800&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">')
DESC = f"{site['tagline']}. {site['full_name']}, annual since {site['founded']}."

def head(title, canonical=None):
    canon = f'<link rel="canonical" href="{e(canonical)}">' if canonical else ""
    return (f'<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>'
            f'<meta name="description" content="{e(DESC)}"><meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(DESC)}"><meta property="og:type" content="website">{canon}{HEAD_LINKS}')

PAGES = [("home", "index.html", page_home), ("about", "about.html", page_about), ("conferences", "conferences.html", page_conferences), ("people", "people.html", page_people)]

def aliases():
    """Old URLs and old menu labels keep working: each is a stub that forwards to where the content lives now."""
    f = featured()
    out = {"papers.html": ("about.html", "papers"), "contact.html": ("people.html", "contact")}
    if f:
        out["call-for-papers.html"] = (f"conferences/{f['year']}.html", "call-for-papers" if f.get("call_for_papers") else None)
        out["travel.html"] = (f"conferences/{f['year']}.html", "travel" if f.get("travel") else None)
    return out

def build_multi():
    validate()
    os.makedirs(os.path.join(SITE, "conferences"), exist_ok=True)
    open(os.path.join(SITE, "assets", "site.css"), "w", encoding="utf-8").write(css("multi", 1))  # image URLs resolve relative to assets/site.css, one level down
    n = 0
    def emit(path, slug, body, title):
        nonlocal n
        depth = path.count("/"); ctx = Ctx("multi", depth)
        html = (f'<!doctype html>\n<html lang="en"><head>{head(title, site["base_url"] + path.replace("index.html", ""))}<link rel="stylesheet" href="{ctx.rel}assets/site.css"></head>\n'
                f'<body>{header(ctx, slug)}<main id="main" class="page">{body}</main>{footer(ctx)}</body></html>')
        full = os.path.join(SITE, path); os.makedirs(os.path.dirname(full), exist_ok=True)
        open(full, "w", encoding="utf-8").write(html); n += 1
    for slug, path, fn in PAGES:
        emit(path, slug, fn(Ctx("multi", 0)), site['full_name'] if slug == "home" else f"{dict((s, l) for s, l in nav_items()).get(slug, slug.title())} · {site['name']}")
    for c in confs:
        emit(f"conferences/{c['year']}.html", f"conference-{c['year']}", page_conference(Ctx("multi", 1), c), f"WCRS {c['year']} · {site['full_name']}")
    for path, (target, anchor) in aliases().items():
        url = target + (f"#{anchor}" if anchor else "")
        open(os.path.join(SITE, path), "w", encoding="utf-8").write(
            f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>{e(site["name"])}</title><meta http-equiv="refresh" content="0;url={e(url)}">'
            f'<link rel="canonical" href="{e(site["base_url"] + url)}"></head><body><p>This page has moved to <a href="{e(url)}">{e(url)}</a>.</p></body></html>')
        n += 1
    print(f"multi-page site: {n} files written")

ROUTER = """<script>
(function(){
  var views=document.querySelectorAll('main.view'), nav=document.querySelectorAll('nav.top a');
  function show(){
    var h=(location.hash||'#home').slice(1), parts=h.split('--'), slug=parts[0], anchor=parts[1];
    var el=document.getElementById('p-'+slug); if(!el){slug='home';el=document.getElementById('p-home');anchor=null;}
    views.forEach(function(v){v.classList.toggle('on',v===el);});
    var page=el.getAttribute('data-page');
    nav.forEach(function(a){ if(a.getAttribute('data-slug')===page||a.getAttribute('data-slug')===slug){a.setAttribute('aria-current','page');} else {a.removeAttribute('aria-current');} });
    var h1=el.querySelector('h1'); document.title=(h1?h1.textContent+' · WCRS':'WCRS');
    if(anchor){var t=el.querySelector('#'+anchor); if(t){t.scrollIntoView();return;}}
    window.scrollTo(0,0);
  }
  window.addEventListener('hashchange',show); show();
})();
</script>"""

def build_single(out, artifact=False):
    validate()
    ctx = Ctx("single"); mains = ""
    for slug, _, fn in PAGES:
        mains += f'<main id="p-{slug}" class="view{" on" if slug == "home" else ""}" data-page="{slug}">{fn(ctx)}</main>\n'
    for c in confs:
        mains += f'<main id="p-conference-{c["year"]}" class="view" data-page="conferences">{page_conference(ctx, c)}</main>\n'
    bar = (f'<div class="draft-bar"><b>DRAFT · WCRS website v1 · {BUILD_DATE}</b><span>Complete draft for review before launch. Every fact traces to the conference programs, '
           f'the event plan for the next conference, or the current site. Program PDFs open on the current WCRS site where one is public; the rest ship with the launch.</span></div>')
    body = f"{bar}{header(ctx, 'home')}{mains}{footer(ctx)}{ROUTER}"
    style = f"<style>{css('single', 0)}</style>"
    if artifact:
        html = f"<title>{e(site['full_name'])}</title>\n{HEAD_LINKS}\n{style}\n{body}"
    else:
        html = f'<!doctype html>\n<html lang="en"><head>{head(site["full_name"] + " (draft)")}{style}</head>\n<body>{body}</body></html>'
    open(out, "w", encoding="utf-8").write(html)
    print(f"single file: {out} ({os.path.getsize(out) // 1024} KB)")

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args: build_multi()
    elif args[0] == "--single" and len(args) > 1: build_single(args[1])
    elif args[0] == "--artifact" and len(args) > 1: build_single(args[1], artifact=True)
    else: print(__doc__)
