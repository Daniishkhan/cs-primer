# Zero to Systems

A first-principles path from how computers talk to senior-level system design. It's written for someone with no prior knowledge: every term is defined when it first appears, and every course uses analogies, hand-drawn-style diagrams, step-through animations, small interactive simulators, terminal experiments and quizzes. Each course also has hands-on Python labs, case studies of real systems with primary sources, and (from course 1 onward) interview-style **design studios**.

## The path

| # | Course | Folder | Status |
|---|---|---|---|
| 0 | **Networking from Zero**: bits to replication and consensus | `networking/` | 23 chapters · 6 labs · 10 case studies |
| 1 | **How Programs Run**: CPU, memory, kernel, processes, durability, threads, locks, queues, event loops | `systems/` | 23 chapters · 5 labs · 8 case studies · 2 studios |
| 2 | **Data Systems**: storage engines, indexes, transactions & isolation, caching, replication, sharding, streams | `data/` | 22 chapters · 6 labs · 8 case studies · 2 studios |
| 3 | **Software Architecture & Design**: complexity, coupling, hexagonal design, APIs, microservices, events, sagas, resilience | `architecture/` | 22 chapters · 6 labs · 8 case studies · 2 studios |
| 4 | **Distributed Systems, Deep**: system models, impossibility, failure detection, leases & fencing, consistency models, Paxos & Raft, atomic commit, distributed transactions, CRDTs, exactly-once, multi-region, Jepsen/simulation/TLA+ | `distributed/` | 22 chapters · 7 labs · 10 case studies · 3 studios |
| 5 | **Reliability & Operations**: availability maths, SLOs & error budgets, metrics/logs/tracing, alerting, queueing theory, tail latency, load testing, overload, deploys, config, Kubernetes, blast radius, incidents, postmortems, DR, chaos, cost | `reliability/` | 22 chapters · 6 labs · 8 case studies · 3 studios |
| 6 | **Security Engineering** (added after a curriculum gap analysis): threat modeling, applied crypto, keys & PKI, authentication, sessions & JWTs, OAuth/OIDC, authorization, injection, web security, SSRF, supply chain, zero trust, cloud, multi-tenancy, abuse, privacy, detection | `security/` | 21 chapters · 6 labs · 8 case studies · 3 studios |
| 7 | **System Design Studio** (capstone): a design framework, estimation, building blocks, communication, 15 worked designs, ML/LLM systems, 8 mock design studios | `design/` | 22 chapters · 6 labs · 8 case studies · 8 studios |

Chapters are tagged **Deep dive**, **Core** or **Quick intro** so you know where to spend your effort.

## Opening it

There is no build step, no server and there are no dependencies. Open `index.html` (the hub) in a browser:

```sh
open index.html          # macOS
xdg-open index.html      # Linux
start index.html         # Windows
```

Reading needs no network beyond Google Fonts. If you're offline, the pages fall back to system fonts.

### Running the examples in the page

Every chapter script is a code cell with **Copy**, **✎ Edit** and **▶ Run**. Run executes it in the browser with [Pyodide](https://pyodide.org) (CPython compiled to WebAssembly), and the output appears under the printed output, with a note on whether the two match. Edit opens the script in an editor (the vendored [CodeMirror 5](https://codemirror.net/5/)), so you can change an assumption and run it again; ⌘/Ctrl + Enter runs, Esc closes, and **↺ Reset** restores the original.

- Nothing is downloaded until you press Run. The first run fetches Python from jsDelivr (about 10 MB, then cached by the browser), so it needs a connection.
- Python runs in a Web Worker, so the page stays responsive and **■ Stop** ends a long or endless script. Browser Python is two to three times slower than native, so the heaviest simulations take tens of seconds.
- Scripts that need a real operating system (processes, threads, sockets, `fsync`, `mmap`) are marked **run locally**: copy them and run them with `python3`. That is most of How Programs Run, by design. The labs always run locally.


Diagrams are drawn in a hand-drawn (Excalidraw/tldraw-like) style by default, using the vendored [Rough.js](https://github.com/rough-stuff/rough) and the Shantell Sans font. The **✎ Hand-drawn / ▭ Clean** button switches to crisp diagrams, and printing always uses the clean style.

Your browser's localStorage keeps:

- progress per course;
- design-studio notes and rubric ticks;
- the theme choice: Tokyo Night, Catppuccin Mocha or high-contrast Gruvbox Dark;
- your edits to code cells (until you press Reset).

## Labs

Every lab has `<course>/labs/code/labNN/` with three files:

- `starter.py`: yours to fill in;
- `check.py`: run `python3 check.py` to see which milestones pass;
- `solution.py`.

Labs use Python 3.9+ and the standard library only. The How Programs Run labs use POSIX features (fork, signals, fsync), so on Windows run them in WSL. Distributed-systems labs run whole clusters inside one deterministic, seeded simulation, so any failure can be replayed from its seed. Security labs attack only deliberately vulnerable code inside the lab's own process.

## Curriculum review

After the first six courses were drafted, the whole path was reviewed against a university systems sequence (networking, operating systems, databases, software design, distributed systems, security, parallel computing) and against what senior system-design work actually needs. The review found one large gap and several small ones. The large gap, security, became Course 6. The small ones became **Extensions** chapters at the end of finished courses: cloud networking, parallelism and GPUs, performance engineering, data platforms, and engineering practice. Adding them as Extensions means nothing earlier was renumbered. `curriculum.html` documents the analysis and suggests study plans.

## Project layout

```
index.html                  hub: all courses and progress
glossary.html               searchable glossary across courses, with a course filter
curriculum.html             curriculum map: how the path lines up with university courses, the gap analysis, study plans
lab-machine.html            setting up a local or cloud Linux VM for the Linux-only experiments
<course>/index.html         course roadmap
<course>/chapters/          one file per chapter
<course>/labs/              labs; code in <course>/labs/code/labNN/
<course>/cases/             case studies
<course>/studios/           design studios
assets/css/theme.css        colour tokens for the three themes
assets/css/main.css         layout and shared components
assets/css/widgets/         styles for individual interactive widgets
assets/js/catalog.js        every course, part, chapter, lab, case and studio (single source of truth)
assets/js/main.js           hub, sidebar, pager, table of contents, theme, progress
assets/js/quiz.js           declarative quizzes
assets/js/stepper.js        generic step-through diagrams
assets/js/studio.js         design studios: autosaved notes, rubric
assets/js/sketch.js         hand-drawn rendering of diagrams (Rough.js)
assets/js/runner.js         code cells: copy, edit (CodeMirror), run (Pyodide in a worker)
assets/js/widgets/          one script per interactive widget
assets/vendor/              Rough.js (MIT), CodeMirror 5.65.18 (MIT)
```

## Adding a page

1. Add an entry to the right course in `assets/js/catalog.js`: a chapter (id, part, depth, file, title, blurb), a lab, a case or a studio.
2. Copy a page of the same kind from that course and change its `data-*` attribute and content. Every page's `<body>` carries `data-root="../.."` and `data-course="<id>"`.

The sidebar, table of contents, page header, "mark complete" box, cross-links and previous/next links are generated automatically.
