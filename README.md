# Zero to AI Systems

A first-principles path, in nine courses, from school mathematics to building, evaluating and improving AI systems. It's written for someone with no prior knowledge of the subject: every term is defined when it first appears, and every course uses analogies, hand-drawn-style diagrams, step-through animations, small interactive simulators, equations broken down symbol by symbol, and quizzes. Each course also has hands-on Python labs that run in the page, case studies of real systems with primary sources, design studios, and 20 workbench pages that measure the ideas with the real tools (PyTorch, Hugging Face, TRL, vLLM, local models) on a laptop or a rented GPU.

## The courses

It assumes you can program in Python and know the software engineering around a model (processes, HTTP, databases, reliability, security); chapters recall those ideas in a sentence where they need them.

| # | Course | Folder | Size |
|---|---|---|---|
| A0 | **Math & Code for Machine Learning**: arrays, linear algebra, SVD, derivatives and autodiff, optimisers, floating point, probability, likelihood, information theory, statistics of experiments | `ml-foundations/` | 23 chapters · 6 labs · 5 case studies · 2 studios |
| A1 | **Machine Learning & Data Science**: framing and metrics, linear models, trees and boosting, unsupervised learning, cross-validation, leakage, calibration, features, time series, competitions, proving value | `ml/` | 22 chapters · 6 labs · 7 case studies · 3 studios · 1 workbench |
| A2 | **Deep Learning & Transformers**: backpropagation, training dynamics, embeddings, attention, a GPT by hand, tokenisation, decoding, FLOPs and memory, scaling laws, modern architectures | `deep-learning/` | 23 chapters · 6 labs · 7 case studies · 2 studios · 5 workbenches |
| A3 | **Training, Post-training & Serving LLMs**: pretraining data and parallelism, RL foundations, SFT, LoRA, RLHF, DPO, GRPO, distillation, merging, quantisation, KV cache, serving engines | `llm-training/` | 24 chapters · 7 labs · 7 case studies · 3 studios · 8 workbenches |
| A4 | **Agents, Tools & Protocols**: the tool loop, tool design, function calling, MCP and A2A, context engineering, workflows, multi-agent systems, durable execution, deep research, computer use, agent security | `agents/` | 23 chapters · 7 labs · 7 case studies · 3 studios · 1 workbench |
| A5 | **Retrieval, Search & Document AI**: BM25, relevance metrics, dense and hybrid retrieval, vector indexes, RAG with verified citations, PDFs, OCR, tables and visual retrieval | `retrieval/` | 23 chapters · 6 labs · 7 case studies · 3 studios · 1 workbench |
| A6 | **Evals, Guardrails & Safe Operation**: error analysis, LLM judges, eval statistics, domain benchmarks, agent evals, hallucination, prompt injection, guardrails, red teaming, observability, governance | `evals/` | 23 chapters · 7 labs · 7 case studies · 3 studios · 1 workbench |
| A7 | **Search, Evolution & Self-Improving Agents**: MCTS, evolution, novelty and quality-diversity, open-ended algorithms, FunSearch and AlphaEvolve, meta agents, evaluator hacking | `open-ended/` | 22 chapters · 7 labs · 7 case studies · 3 studios · 2 workbenches |
| A8 | **Applied AI Delivery Studio** (capstone): discovery, requirements under ambiguity, prototypes, evaluation plans, domains, production delivery, security reviews, writing for customers, getting hired | `ai-delivery/` | 20 chapters · 4 labs · 6 case studies · 8 take-home studios · 1 workbench |

Chapters are tagged **Deep dive**, **Core** or **Quick intro** so you know where to spend your effort. Chapters that change fast (model rankings, prices, library and protocol versions) keep those facts in dated **State of play** boxes, so the main text stays about durable mechanisms.

### The builder spine

The path has a **builder spine**: about 90 chapters on the way to course A7, for learners who want to build evolutionary and self-improving systems rather than deliver AI to customers. Each AI course lists its spine chapters in `assets/js/catalog.js` (`spine: [...]`), and every other chapter shows as *elective*. The **Builder spine only** button at the foot of the sidebar hides the electives, and its prev/next links then walk the spine across courses. A8 is wholly elective. One problem, online bin packing, runs through the spine as its worked example. `curriculum.html` has the full plan.

### Labs and stand-in models

Labs use the standard library only and are deterministic. Labs that talk to a model use **scripted stand-in models** from `lab-support/llm.py` (copied into each lab folder as `llm.py`), so `python3 check.py` is free, offline and repeatable. To try a lab's ideas against a real model, set `LAB_MODEL`:

```sh
LAB_MODEL=anthropic:<model-id> python3 your_script.py   # needs ANTHROPIC_API_KEY
LAB_MODEL=openai:<model-id>    python3 your_script.py   # needs OPENAI_API_KEY; OPENAI_BASE_URL for compatible servers
LAB_MODEL=ollama:<model-name>  python3 your_script.py   # a local Ollama server
```

`check.py` never uses a real model. Chapter examples use the standard library and NumPy; where a chapter imports a small shared helper, the chapter links it from `<course>/chapters/code/`.

### Authoring

`authoring/guide.md` is the page contract (voice, skeletons, diagrams, labs, cases, studios). `authoring/check_page.py` lints pages against it, `authoring/render_check.sh` loads pages in headless Chrome and reports JavaScript errors, and `authoring/build_glossary.py` rebuilds `glossary.html` from `glossary-src/*.json`.

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
- Scripts that need a real operating system (processes, threads, sockets, `fsync`, `mmap`) are marked **run locally**: copy them and run them with `python3`. That is most of How Programs Run, by design.
- Every lab page has **Or work in the page**: `starter.py` as an editable cell whose **▶ Check** runs the lab's `check.py` against it (args: `solution`, or a milestone number). All 56 labs have one; the two that start processes or threads (agents labs 3 and 6) say "run locally" instead.

### Equations

Formulas are typeset with the vendored [KaTeX](https://katex.org). The equations a chapter is built around are **anatomy blocks**: the equation in plain words, a colour-coded legend that says what *kind* of thing each symbol is, a step-by-step build-up, and a runnable script that computes it on a few numbers.

### Workbench: the real tools

**Workbench** pages repeat a chapter's idea with PyTorch, Hugging Face, TRL or vLLM on a real machine: predict a number from the chapter, measure it, compare (measurement tables keep what you type). Each page is badged *Your laptop* or *A GPU box*. `workbench/requirements.txt` sets up the laptop; `workbench/wb` rents an RTX 4090 on RunPod with your models on a network volume, and stops a forgotten pod by itself. See `lab-machine.html#gpu`.

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
- the Ask panel: your provider, model and key, and the thread for each page.

## Labs

Every lab has `<course>/labs/code/labNN/` with three files:

- `starter.py`: yours to fill in;
- `check.py`: run `python3 check.py` to see which milestones pass;
- `solution.py`.

Labs use Python 3.9+ and the standard library only, and are deterministic (see above for the stand-in models). A few agent labs start subprocesses or threads, so they say "run locally" instead of running in the page.

## Project layout

```
index.html                  hub: all courses and progress
glossary.html               searchable glossary, with a course filter
curriculum.html             curriculum map: how the courses fit together, university comparison, study plans
lab-machine.html            the laptop environment and a rented GPU for workbenches
<course>/index.html         course roadmap
<course>/chapters/          one file per chapter
<course>/labs/              labs; code in <course>/labs/code/labNN/
<course>/cases/             case studies
<course>/studios/           design studios
<course>/workbench/         workbench pages; code in <course>/workbench/code/wNN/ (.py + .ipynb)
workbench/                  laptop and GPU requirements, wb (RunPod helper), pod setup and idle stop
review.html                 spaced review of quiz questions, progress backup
assets/css/theme.css        colour tokens for the three themes
assets/css/main.css         layout and shared components
assets/css/widgets/         styles for individual interactive widgets
assets/js/catalog.js        every course, part, chapter, lab, case and studio (single source of truth)
assets/js/main.js           hub, sidebar, pager, table of contents, theme, progress
assets/js/quiz.js           declarative quizzes
assets/js/stepper.js        generic step-through diagrams
assets/js/studio.js         design studios: autosaved notes, rubric
assets/js/sketch.js         hand-drawn rendering of diagrams (Rough.js)
assets/js/runner.js         code cells: copy, edit (CodeMirror), run (Pyodide in a worker); lab workspaces
assets/js/equations.js      typeset maths (KaTeX) and equation anatomy blocks
assets/js/review.js         spaced review of every quiz; progress export/import
assets/js/ask.js            ask about this page: selection chip, tutor panel, streaming from OpenAI, Anthropic or Ollama
assets/js/*-data.js         generated: review-data, search-data (authoring/build_study.py), glossary-data
assets/js/widgets/          one script per interactive widget
assets/vendor/              Rough.js (MIT), CodeMirror 5.65.18 (MIT), KaTeX 0.16.11 (MIT)
lab-support/llm.py          scripted stand-in models + optional real-model adapter, copied into labs
<course>/chapters/code/     small helper modules some chapters import
glossary-src/               per-chapter glossary terms (JSON), merged by authoring/build_glossary.py
authoring/                  guide, link index, page linter, render check, glossary builder, unit briefs
```

## Adding a page

1. Add an entry to the right course in `assets/js/catalog.js`: a chapter (id, part, depth, file, title, blurb), a lab, a case or a studio.
2. Copy a page of the same kind from that course and change its `data-*` attribute and content. Every page's `<body>` carries `data-root="../.."` and `data-course="<id>"`.

The sidebar, table of contents, page header, "mark complete" box, cross-links and previous/next links are generated automatically.

3. Re-run `python3 authoring/build_study.py` so the page's quiz joins the Review page and its sections join search, and `python3 authoring/check_page.py PAGE` to lint it (it also checks every formula).
