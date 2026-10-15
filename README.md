# Zero to AI Systems

A first-principles path, in eleven courses, built towards four public research artifacts, from school mathematics to building, evaluating and improving AI systems. It's written for someone with no prior knowledge of the subject: every term is defined when it first appears, and every course uses analogies, hand-drawn-style diagrams, step-through animations, small interactive simulators, equations broken down symbol by symbol, and quizzes. Each course also has hands-on Python labs that run in the page, case studies of real systems with primary sources, design studios, and 18 workbench pages that measure the ideas with the real tools (PyTorch, Hugging Face, TRL, local models, real agents) on a rented lab VM or, later, a rented GPU.

## The courses

It assumes you can program in Python and know the software engineering around a model (processes, HTTP, databases, reliability, security); chapters recall those ideas in a sentence where they need them.

| # | Course | Folder | Size |
|---|---|---|---|
| A0 | **Math & Code for Machine Learning**: arrays, linear algebra, SVD, derivatives and autodiff, optimisers, floating point, probability, likelihood, information theory, statistics of experiments, compute costs, programs as data | `ml-foundations/` | 23 chapters · 6 labs · 5 case studies · 2 studios |
| A1 | **Machine Learning & Data Science**: generalisation, framing and metrics, cross-validation, leakage | `ml/` | 5 chapters · 1 lab · 2 case studies |
| A2 | **Deep Learning & Transformers**: backpropagation, training dynamics, embeddings, attention, a GPT by hand ending at nanochat, tokenisation, decoding, FLOPs and memory, scaling laws, modern architectures, interpretability and learned optimisers as reading | `deep-learning/` | 25 chapters · 6 labs · 7 case studies · 2 studios · 5 workbenches |
| A3 | **Training, Post-training & Serving LLMs**: pretraining data, GPU memory, parallelism, kernels, long runs, RL foundations, SFT, LoRA, RLHF, DPO, reward hacking, GRPO, distillation, merging, the cost of a token | `llm-training/` | 20 chapters · 5 labs · 6 case studies · 2 studios · 4 workbenches |
| A4 | **Agents, Tools & Protocols**: the tool loop, tool design, function calling, MCP and A2A, context engineering, workflows, multi-agent systems, durable execution, deep research, coding agents, sandboxes, agent security, dense retrieval | `agents/` | 24 chapters · 7 labs · 7 case studies · 3 studios · 2 workbenches |
| A6 | **Evals, Guardrails & Safe Operation**: error analysis, LLM judges, eval statistics, domain benchmarks, contamination, agent evals, hallucination, prompt injection, guardrails, red teaming, observability, governance | `evals/` | 23 chapters · 7 labs · 7 case studies · 3 studios · 1 workbench |
| A7 | **Search, Evolution & Self-Improving Agents**: MCTS, evolution, novelty and quality-diversity, open-ended algorithms, co-evolution, program evolution, evolution frameworks, meta agents, self-referential improvers, automated science, evaluator hacking | `open-ended/` | 22 chapters · 7 labs · 7 case studies · 3 studios · 2 workbenches |
| A9 | **Research Engineering on Small Proxies**: the research loop as a program, proxies, noise floors and seeds, scaling laws and μP for proxies, ablations and run tracking, a Rust runner, the write-up | `research-eng/` | 7 chapters · 1 lab · 1 case study · 1 workbench |
| A10 | **Harness & Evaluator Engineering**: harness engineering as research, AIDE's tree search over experiments, public and private splits, attested results and hacking rate, kernels for agents, research-agent benchmarks | `harness-eng/` | 6 chapters · 1 lab · 1 case study · 1 workbench |
| A11 | **AI Control & Sandbox Security**: the threat model of a research loop, deny-by-default egress, attested tool results, transcript monitoring, incident playbooks | `control/` | 6 chapters · 1 lab · 1 case study · 1 workbench |
| A12 | **Measuring Recursive Self-Improvement**: the Level-1 conditions, automation levels for AI research, the economics of a loop, reading self-improvement claims | `rsi-measurement/` | 6 chapters · 1 lab · 1 case study · 1 workbench |

Chapters are tagged **Deep dive**, **Core** or **Quick intro** so you know where to spend your effort. Chapters that change fast (model rankings, prices, library and protocol versions) keep those facts in dated **State of play** boxes, so the main text stays about durable mechanisms.

### The artifact track

The path is built towards **four public artifacts**, each a small replication of a published result about automating AI research plus one honest extension: autoresearch-rs (a research loop with a Rust runner), a mini FML-Bench search study (tree search against greedy), an evaluator-hardening kit (break a kernel grader, harden it, measure hacking), and AIDE²-in-miniature (an outer agent that improves the Artifact 2 agent). `CS_ARTIFACTS` in `assets/js/catalog.js` lists, for each, the chapters to read before starting, the chapters to open while building, and the labs, workbenches and cases that build it. Every chapter is shown as *read first*, *while building* or *reading*. The **Artifact track** control in the settings panel shows only one artifact's chapters, and prev/next then walk its reading list across courses. `curriculum.html` has the four artifacts, their gates, an 18-month roadmap and the standards every artifact must meet; `contributing.html` and `evidence.html` cover upstream pull requests and the evidence log. The plan behind it is `RSI Artifact-First Roadmap.md`.

A5 (Retrieval) and A8 (Applied AI Delivery) were removed in October 2026, and A1 and A3 were cut to what the artifacts use; their numbers are not reused.

### Labs and stand-in models

Labs use the standard library only and are deterministic. Labs that talk to a model use **scripted stand-in models** from `lab-support/llm.py` (copied into each lab folder as `llm.py`), so `python3 check.py` is free, offline and repeatable. To try a lab's ideas against a real model, set `LAB_MODEL`:

```sh
LAB_MODEL=anthropic:<model-id> python3 your_script.py   # needs ANTHROPIC_API_KEY
LAB_MODEL=openai:<model-id>    python3 your_script.py   # needs OPENAI_API_KEY; OPENAI_BASE_URL for compatible servers
LAB_MODEL=ollama:<model-name>  python3 your_script.py   # a local Ollama server
```

`check.py` never uses a real model. Chapter examples use the standard library and NumPy; where a chapter imports a small shared helper, the chapter links it from `<course>/chapters/code/`.

### Authoring

`authoring/guide.md` is the page contract (voice, skeletons, diagrams, labs, cases, studios). `authoring/check_page.py` lints pages against it, `authoring/render_check.sh` loads pages in headless Chrome and reports JavaScript errors, and `authoring/build_glossary.py` rebuilds `glossary.html` from `glossary-src/*.json`, `authoring/build_link_index.py` regenerates the link index authors take cross-links from, `authoring/remove_pages.py` removes pages and repairs every link to them, and `authoring/maintenance.md` lists the dated claims to refresh each quarter.

## Opening it

**Live site: https://daniishkhan.github.io/cs-primer/** (GitHub Pages, served from `main`; every push republishes it).

To run it locally instead (there is no build step and there are no dependencies), serve the folder over http and open the hub:

```sh
python3 -m http.server 8000      # in the site folder, then open http://localhost:8000
```

Opening `index.html` straight from disk (`open index.html`) also works for reading, but browsers restrict pages loaded from `file://`: code cells then run without a Stop button, and lab workspaces cannot load their files. Any static host (GitHub Pages, Cloudflare Pages) serves the site as it is.

Reading needs no network beyond Google Fonts. If you're offline, the pages fall back to system fonts.

### Running the examples in the page

Every chapter script is a code cell with **Copy**, **✎ Edit** and **▶ Run**. Run executes it in the browser with [Pyodide](https://pyodide.org) (CPython compiled to WebAssembly), and the output appears under the printed output, with a note on whether the two match. Edit opens the script in an editor (the vendored [CodeMirror 5](https://codemirror.net/5/)), so you can change an assumption and run it again; ⌘/Ctrl + Enter runs, Esc closes, and **↺ Reset** restores the original.

- Nothing is downloaded until you press Run. The first run fetches Python from jsDelivr (about 10 MB, then cached by the browser), so it needs a connection.
- Python runs in a Web Worker, so the page stays responsive and **■ Stop** ends a long or endless script. Browser Python is two to three times slower than native, so the heaviest simulations take tens of seconds.
- Scripts that need a real operating system (processes, threads, sockets, `fsync`, `mmap`) are marked **run locally**: copy them and run them with `python3`. - Every lab page has **Or work in the page**: `starter.py` as an editable cell whose **▶ Check** runs the lab's `check.py` against it (args: `solution`, or a milestone number). All 43 labs have one; labs that start processes or threads say which milestones need to run locally instead.

### Equations

Formulas are typeset with the vendored [KaTeX](https://katex.org). The equations a chapter is built around are **anatomy blocks**: the equation in plain words, a colour-coded legend that says what *kind* of thing each symbol is, a step-by-step build-up, and a runnable script that computes it on a few numbers.

### Workbench: the real tools

**Workbench** pages repeat a chapter's idea with the real tools on a real machine: predict a number from the chapter, measure it, compare (measurement tables keep what you type). Nothing runs on your own computer: each page is badged *The lab VM* (one rented CPU machine on AWS, 16 to 32 cores) or *A GPU box* (a rented 24 GB card, later). `workbench/vm` creates, starts, stops and connects to the VM, with SSH open to your IP address only and an alarm that stops a forgotten VM; `workbench/setup-vm.sh` is its first-boot setup. `workbench/wb` rents a GPU on RunPod for the GPU pages. See `lab-machine.html`.

### Practice: learn by doing

`practice.html` is the front door. It turns every lab milestone into a **drill**: a file with everything written except one function, a checker that says ✔ or ✘ in the browser, the least theory needed to try (a need-to-know card), hints on failure, the solution behind a click, and the lab's explanation and chapter as the "why" afterwards. Drills come in the order the four artifacts need them. Attempts, hints shown and drills passed are saved in the browser; when every drill of a lab passes, the lab counts as complete in its course. `python3 authoring/build_drills.py` generates the drills from the labs (`<course>/labs/code/labNN/drills/`: one `mN.py` per milestone, `lab.json`, and the cards `mN.html` that authors write to `authoring/drill-cards.md`); `--verify` runs every drill's check.

### Review and search

`review.html` asks the quiz questions of the pages you have finished, ten at a time, on a spaced-repetition schedule, and exports or imports all your progress. ⌘/Ctrl + K (or `/`) searches every page and section heading.

### Ask about the page

**Ask** (in the top bar) opens a tutor panel that has the whole page as its context. Select any passage and an **Explain** chip appears next to it: it quotes the passage into the panel with ready-made questions ("Explain this", "Give me an analogy", "Show me with numbers"), and the thread continues from there. Each page keeps its own thread.

The model is called straight from the browser, so you bring the key: open the panel's ⚙ settings and paste one for OpenAI (or any OpenAI-compatible server, through its base URL) or Anthropic, or point it at a local Ollama (start Ollama with `OLLAMA_ORIGINS` set to exactly the site's origin, such as `http://localhost:8000`, so this page may call it; not `*`, which would let every website you visit call it). The key is kept in this browser's localStorage and is sent only to that provider; nothing passes through the site. `node authoring/check_ask.js` checks the stream parser, the request shapes and the Markdown renderer; with `OPENAI_API_KEY` set, `node authoring/check_ask.js --live` also streams one real answer.


Diagrams are drawn in a hand-drawn (Excalidraw/tldraw-like) style by default, using the vendored [Rough.js](https://github.com/rough-stuff/rough) and the Shantell Sans font. The **✎ Hand-drawn / ▭ Clean** button switches to crisp diagrams, and printing always uses the clean style.

Your browser's localStorage keeps:

- progress per course;
- design-studio notes and rubric ticks;
- the theme choice: Tokyo Night, Catppuccin Mocha or high-contrast Gruvbox Dark;
- your edits to code cells (until you press Reset);
- workbench measurements and the review schedule (back them up from the Review page);
- the Ask panel: your provider, model and key, and the thread for each page;
- Practice: drills passed (with dates), attempts, hints shown, and your code in each drill.

## Labs

Every lab has `<course>/labs/code/labNN/` with three files:

- `starter.py`: yours to fill in;
- `check.py`: run `python3 check.py` to see which milestones pass;
- `solution.py`.

Labs use Python 3.9+ and the standard library only, and are deterministic (see above for the stand-in models). A few agent labs start subprocesses or threads, so they say "run locally" instead of running in the page.

## Project layout

```
index.html                  hub: the front door to Practice, all courses and progress
practice.html               Practice: one drill at a time, in artifact order
glossary.html               searchable glossary, with a course filter
curriculum.html             the artifact track: four artifacts, gates, roadmap, standards
contributing.html           upstream repositories and the rules that get pull requests merged
evidence.html               a private evidence log per artifact (autosaved in the browser)
lab-machine.html            the lab VM every workbench runs on, and a rented GPU later
<course>/index.html         course roadmap
<course>/chapters/          one file per chapter
<course>/labs/              labs; code in <course>/labs/code/labNN/
<course>/cases/             case studies
<course>/studios/           design studios
<course>/workbench/         workbench pages; code in <course>/workbench/code/wNN/ (.py + .ipynb)
workbench/                  requirements, vm (the AWS lab VM) and setup-vm.sh, wb (RunPod GPU helper) and pod setup
review.html                 spaced review of quiz questions, progress backup
assets/css/theme.css        colour tokens for the three themes
assets/css/main.css         layout and shared components
assets/css/widgets/         styles for individual interactive widgets
assets/js/catalog.js        every course, part, chapter, lab, case, studio and workbench, and the four artifacts (single source of truth)
assets/js/main.js           hub, sidebar, pager, table of contents, theme, progress
assets/js/quiz.js           declarative quizzes
assets/js/stepper.js        generic step-through diagrams
assets/js/studio.js         design studios: autosaved notes, rubric
assets/js/sketch.js         hand-drawn rendering of diagrams (Rough.js)
assets/js/runner.js         code cells: copy, edit (CodeMirror), run (Pyodide in a worker); lab workspaces
assets/js/equations.js      typeset maths (KaTeX) and equation anatomy blocks
assets/js/review.js         spaced review of every quiz; progress export/import
assets/js/practice.js       Practice: mounts one drill (runner.js workspace), hints, pass detection, the queue
assets/js/drills-data.js    generated: every drill in artifact order (authoring/build_drills.py)
assets/js/ask.js            ask about this page: selection chip, tutor panel, streaming from OpenAI, Anthropic or Ollama
assets/js/*-data.js         generated: review-data, search-data (authoring/build_study.py), glossary-data
assets/js/widgets/          one script per interactive widget
assets/vendor/              Rough.js (MIT), CodeMirror 5.65.18 (MIT), KaTeX 0.16.11 (MIT)
lab-support/llm.py          scripted stand-in models + optional real-model adapter, copied into labs
<course>/chapters/code/     small helper modules some chapters import
glossary-src/               per-chapter glossary terms (JSON), merged by authoring/build_glossary.py
authoring/                  guide, link index and its builder, page linter, render check, glossary builder, page remover, unit briefs, maintenance list
```

## Adding a page

1. Add an entry to the right course in `assets/js/catalog.js`: a chapter (id, part, depth, file, title, blurb), a lab, a case, a studio or a workbench. If an artifact needs it, add its id to that artifact's `before`, `while` or `build` list in `CS_ARTIFACTS`.
2. Copy a page of the same kind from that course and change its `data-*` attribute and content. Every page's `<body>` carries `data-root="../.."` and `data-course="<id>"`.

The sidebar, table of contents, page header, "mark complete" box, cross-links and previous/next links are generated automatically.

3. Re-run `python3 authoring/build_study.py` so the page's quiz joins the Review page and its sections join search, `python3 authoring/build_glossary.py` if you added glossary terms, and `python3 authoring/build_link_index.py`; then `python3 authoring/check_page.py PAGE` to lint it (it also checks every formula). After adding or changing a lab, run `python3 authoring/build_drills.py --verify` so its milestones become drills.

To remove pages, run `python3 authoring/remove_pages.py --page PATH ...` (or `--dir COURSE`): it prints what it would delete and which links it would unwrap, and changes files only with `--apply`.
