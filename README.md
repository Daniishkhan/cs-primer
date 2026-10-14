# Zero to Systems

*Two paths: Zero to Systems (courses 0 to 7) and Zero to AI Systems (courses A0 to A8).*

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

## The second path: Zero to AI Systems

A second path, in nine courses, from school mathematics to building, evaluating and delivering AI systems. It trains a broad AI systems / applied AI engineer and links back to the first path for the engineering underneath instead of repeating it.

| # | Course | Folder | Size |
|---|---|---|---|
| A0 | **Math & Code for Machine Learning**: arrays, linear algebra, SVD, derivatives and autodiff, optimisers, floating point, probability, likelihood, information theory, statistics of experiments | `ml-foundations/` | 20 chapters · 5 labs · 5 case studies · 2 studios |
| A1 | **Machine Learning & Data Science**: framing and metrics, linear models, trees and boosting, unsupervised learning, cross-validation, leakage, calibration, features, time series, competitions, proving value | `ml/` | 22 chapters · 6 labs · 7 case studies · 3 studios |
| A2 | **Deep Learning & Transformers**: backpropagation, training dynamics, embeddings, attention, a GPT by hand, tokenisation, decoding, FLOPs and memory, scaling laws, modern architectures | `deep-learning/` | 23 chapters · 6 labs · 7 case studies · 2 studios |
| A3 | **Training, Post-training & Serving LLMs**: pretraining data and parallelism, RL foundations, SFT, LoRA, RLHF, DPO, GRPO, distillation, merging, quantisation, KV cache, serving engines | `llm-training/` | 24 chapters · 7 labs · 7 case studies · 3 studios |
| A4 | **Agents, Tools & Protocols**: the tool loop, tool design, function calling, MCP and A2A, context engineering, workflows, multi-agent systems, durable execution, deep research, computer use, agent security | `agents/` | 23 chapters · 7 labs · 7 case studies · 3 studios |
| A5 | **Retrieval, Search & Document AI**: BM25, relevance metrics, dense and hybrid retrieval, vector indexes, RAG with verified citations, PDFs, OCR, tables and visual retrieval | `retrieval/` | 23 chapters · 6 labs · 7 case studies · 3 studios |
| A6 | **Evals, Guardrails & Safe Operation**: error analysis, LLM judges, eval statistics, domain benchmarks, agent evals, hallucination, prompt injection, guardrails, red teaming, observability, governance | `evals/` | 23 chapters · 7 labs · 7 case studies · 3 studios |
| A7 | **Search, Evolution & Self-Improving Agents**: MCTS, evolution, novelty and quality-diversity, open-ended algorithms, FunSearch and AlphaEvolve, meta agents, evaluator hacking | `open-ended/` | 19 chapters · 6 labs · 7 case studies · 2 studios |
| A8 | **Applied AI Delivery Studio** (capstone): discovery, requirements under ambiguity, prototypes, evaluation plans, domains, production delivery, security reviews, writing for customers, getting hired | `ai-delivery/` | 20 chapters · 4 labs · 6 case studies · 8 take-home studios |

Chapters that change fast (model rankings, prices, library and protocol versions) keep those facts in dated **State of play** boxes, so the main text stays about durable mechanisms.

### The builder spine

The second path has a **builder spine**: about 90 chapters on the way to course A7, for learners who want to build evolutionary and self-improving systems rather than deliver AI to customers. Each AI course lists its spine chapters in `assets/js/catalog.js` (`spine: [...]`), and every other chapter shows as *elective*. The **Builder spine only** button at the foot of the sidebar hides the electives, and its prev/next links then walk the spine across courses. A8 is wholly elective. One problem, online bin packing, runs through the spine as its worked example. `curriculum.html` has the full plan.

### Labs in the second path

AI-path labs follow the same `starter.py` / `check.py` / `solution.py` layout, use the standard library only and are deterministic. Labs that talk to a model use **scripted stand-in models** from `lab-support/llm.py` (copied into each lab folder as `llm.py`), so `python3 check.py` is free, offline and repeatable. To try a lab's ideas against a real model, set `LAB_MODEL`:

```sh
LAB_MODEL=anthropic:<model-id> python3 your_script.py   # needs ANTHROPIC_API_KEY
LAB_MODEL=openai:<model-id>    python3 your_script.py   # needs OPENAI_API_KEY; OPENAI_BASE_URL for compatible servers
LAB_MODEL=ollama:<model-name>  python3 your_script.py   # a local Ollama server
```

`check.py` never uses a real model. Chapter examples use the standard library and NumPy; where a chapter imports a small shared helper, the chapter links it from `<course>/chapters/code/`.

### Authoring

`authoring/guide.md` is the page contract for the second path (voice, skeletons, diagrams, labs, cases, studios). `authoring/check_page.py` lints pages against it, `authoring/render_check.sh` loads pages in headless Chrome and reports JavaScript errors, and `authoring/build_glossary.py` rebuilds `glossary.html` from the frozen track-1 entries plus `glossary-src/*.json`.

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

Labs use Python 3.9+ and the standard library only (the second path's labs too; see above for its stand-in models). The How Programs Run labs use POSIX features (fork, signals, fsync), so on Windows run them in WSL. Distributed-systems labs run whole clusters inside one deterministic, seeded simulation, so any failure can be replayed from its seed. Security labs attack only deliberately vulnerable code inside the lab's own process.

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
lab-support/llm.py          scripted stand-in models + optional real-model adapter, copied into AI-path labs
<course>/chapters/code/     small helper modules some AI-path chapters import
glossary-src/               per-chapter glossary terms for the AI path (JSON), merged by authoring/build_glossary.py
authoring/                  guide, link index, page linter, render check, glossary builder, unit briefs
```

## Adding a page

1. Add an entry to the right course in `assets/js/catalog.js`: a chapter (id, part, depth, file, title, blurb), a lab, a case or a studio.
2. Copy a page of the same kind from that course and change its `data-*` attribute and content. Every page's `<body>` carries `data-root="../.."` and `data-course="<id>"`.

The sidebar, table of contents, page header, "mark complete" box, cross-links and previous/next links are generated automatically.
