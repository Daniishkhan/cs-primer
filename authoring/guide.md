# Authoring guide: Zero to AI Systems

This guide is the contract for every page of Zero to AI Systems (courses A0 to A8). New pages must be indistinguishable from the existing ones in format, voice and quality. Read this whole file before writing anything, then read the sample pages it names.

Site root: `/Users/danish/Desktop/projects/cs-refresh/networking/` (all paths below are relative to it).

## 1. What already exists and what you must not touch

- `assets/js/catalog.js` is the single source of truth: every course, part, chapter, lab, case, studio and tool, with ids, file names, titles, blurbs, depth and `related` links. **Do not edit it.** If you believe a title or blurb is wrong, say so in your final report; the coordinator changes it.
- `assets/js/main.js`, `quiz.js`, `stepper.js`, `studio.js`, `sketch.js`, `assets/css/main.css`, `assets/css/theme.css`: shared. **Do not edit.**
- `authoring/link-index.md`: every page on the site with its exact path, title and blurb. Use it for every cross-link. Never invent a file name.
- `lab-support/llm.py`: the shared stand-in model module for labs (section 8).
- The engineering underneath (processes, networks, storage, reliability, security) is assumed, not taught. Remind the reader of such an idea in one sentence; there are no other courses to link to.

The courses (id, folder):

| Course | id | folder |
|---|---|---|
| A0 Math & Code for Machine Learning | mlf | ml-foundations/ |
| A1 Machine Learning & Data Science | ml | ml/ |
| A2 Deep Learning & Transformers | dl | deep-learning/ |
| A3 Training, Post-training & Serving LLMs | llm | llm-training/ |
| A4 Agents, Tools & Protocols | agt | agents/ |
| A5 Retrieval, Search & Document AI | ret | retrieval/ |
| A6 Evals, Guardrails & Safe Operation | evl | evals/ |
| A7 Search, Evolution & Self-Improving Agents | oe | open-ended/ |
| A8 Applied AI Delivery Studio | aid | ai-delivery/ |

The path is **broad**: it trains a general AI systems / applied AI engineer, not a candidate for one company. Use examples from many domains (finance, health, law, government, retail, software). Mention specific companies only as sources or case material. Write in English; do not build Japanese-specific content.

## 2. Read these sample pages first

Open and read at least the ones for the kind of page you are writing. They are the quality bar.

- Chapter: `deep-learning/chapters/09-attention.html` (structure, callouts, code with real output, diagrams, an equation anatomy block, quiz). For a stepper, search any chapter for `widget stepper`.
- Lab page: `ml/labs/lab-01-linear-models.html`; lab code: `ml/labs/code/lab01/check.py`, `starter.py`, `solution.py`.
- Case study: `llm-training/cases/case-01-instructgpt.html`.
- Design studio: `llm-training/studios/studio-01-domain-adaptation.html`.
- Course roadmap: `llm-training/index.html`. Toolbox: `llm-training/toolbox.html`.

## 3. Voice and style (strict)

- **British English** spelling: behaviour, optimise, colour, modelling, labelled, analyse, centre, licence (noun). Keep proper names and code identifiers as they are (`optimizer.step()`, "Optimizer" in a library name).
- **No em-dashes (—) anywhere.** Use a colon, a comma, parentheses sparingly, or a new sentence. En-dashes only inside numeric ranges, and prefer "to" ("5 to 10").
- Written for someone with **no prior knowledge of the topic** but who has done the earlier courses. **Define every term the first time it appears**, wrapped in `<span class="term">…</span>` at the defining mention. Remind briefly of terms from earlier courses with a link.
- First principles before patterns. Explain *why* a mechanism works, then *how*, then *what goes wrong*. Every abstraction gets a concrete example with numbers.
- Plain, direct sentences. Short paragraphs. Bold sparingly for the key phrase of a paragraph.
- Honest uncertainty. Do not invent numbers, quotes, dates, benchmark scores, paper results or URLs. If you state a figure, it comes from a source you checked (fetch it if you can) or it is clearly labelled as an illustrative assumption ("assume 2,000 requests a second").
- **Volatile facts get a date.** Model names, leaderboard positions, prices, framework versions, spec versions and "state of the art" claims change monthly. Keep them out of the core explanation. Put them in a dated box:
  ```html
  <div class="callout note">
    <p class="callout-title">State of play, October 2026</p>
    <p>… what is true now, with sources, and what is likely to change …</p>
  </div>
  ```
  The durable concept (the loop, the trade-off, the maths) is the main text. Today is 14 October 2026.
- Analogies: one good analogy per chapter at most two, in `callout analogy`, always ending with `<p><em>Where it breaks down:</em> …</p>`.
- Avoid hype words: "revolutionary", "game-changing", "magic", "simply", "just" (as in "just do X").
- Cite people and papers by name and year in prose ("Vaswani et al., 2017"), with the paper title on first mention. Put links in the chapter's Further reading list.

## 4. Page skeletons (copy exactly)

Every page is a static HTML file. Head and tail are fixed; only the `<title>`, `data-*` attributes, widget CSS/JS and content change. `main.js` builds the sidebar, eyebrow (part, chapter number, depth badge, reading time), table of contents (from `h2`s), "builds on" line, "mark complete" box, labs/studios/case cross-links, "Tools to try" box and prev/next pager. **Do not write any of those yourself.**

### Chapter (`<dir>/chapters/<file>`)

```html
<!doctype html>
<html lang="en" data-theme="tokyo">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CHAPTER TITLE · COURSE TITLE</title>
<script>try{var t=localStorage.getItem("nz-theme");if(t)document.documentElement.dataset.theme=t}catch(e){}</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../../assets/css/theme.css">
<link rel="stylesheet" href="../../assets/css/main.css">
<!-- optional: <link rel="stylesheet" href="../../assets/css/widgets/COURSEIDCHAPTERID-NAME.css"> -->
</head>
<body data-root="../.." data-course="COURSEID" data-chapter="NN">
<div class="app">
<aside id="sidebar" class="sidebar"></aside>
<div class="main-col">
<main class="content">
<article class="prose">

<header class="chapter-head">
  <h1>CHAPTER TITLE</h1>
  <p class="lede">Two or three sentences: what this chapter explains and the question it answers.</p>
</header>

<div class="callout why">
  <p class="callout-title">Why this matters</p>
  <p>Where this sits in the path, what breaks if you do not understand it, and what you will be able to do after.</p>
</div>

… body: h2 sections, h3 subsections …

<div class="callout key">
  <p class="callout-title">Key takeaways</p>
  <ul><li>…</li></ul>
</div>

<h2>Further reading</h2>
<ul class="sources">
  <li><a href="https://…" target="_blank" rel="noopener">Author, "Title" (year)</a>. One sentence on what it is and why to read it.</li>
</ul>

<section class="quiz">
  <h2>Check your understanding</h2>
  <div class="q" data-answer="2">
    <p class="q-text">Question?</p>
    <ol class="q-options"><li>…</li><li>…</li><li>…</li><li>…</li></ol>
    <div class="q-explain">Why the right answer is right and the tempting wrong ones are wrong.</div>
  </div>
</section>

</article>
</main>
</div>
</div>
<script src="../../assets/js/catalog.js"></script>
<script src="../../assets/js/main.js"></script>
<script src="../../assets/js/quiz.js"></script>
<!-- if the page has a stepper: <script src="../../assets/js/stepper.js"></script> -->
<!-- optional widget: <script src="../../assets/js/widgets/COURSEIDCHAPTERID-NAME.js"></script> -->
</body>
</html>
```

- `data-chapter` is the two-digit chapter id from the catalog. Title text must match the catalog title (escape `&` as `&amp;`).
- `data-answer` is the **0-based** index of the correct option. Spread correct answers across positions 0 to 3. Four options each.
- Lab pages: `data-lab="L1"`, title "Lab 1: TITLE", folder `<dir>/labs/`. Case pages: `data-case="C1"`, folder `<dir>/cases/`. Studios: `data-studio="S1"`, folder `<dir>/studios/`, and add `<script src="../../assets/js/studio.js"></script>`. Course roadmap: `data-root=".." data-page="course"`. Toolbox: `data-root=".." data-page="toolbox"`. Paths to assets from `<dir>/index.html` are `../assets/…`.

### Size and shape by depth

| Depth | Words of prose (excluding code/SVG) | Diagrams | Code with real output | Quiz |
|---|---|---|---|---|
| deep | 4,000 to 6,500 | 3 to 5 SVG, at least one stepper or interactive widget | 3 or more | 6 |
| core | 2,500 to 4,000 | 2 to 3 | 2 or more | 6 |
| intro | 1,200 to 2,200 | 1 to 2 | optional | 4 |

These are targets, not quotas: depth comes from mechanism, worked examples and failure modes, never from padding.

### Chapter body: required ingredients

1. `callout why` at the top (above).
2. Sections that build from first principles to the real thing, each with at least one concrete example.
3. At least one `callout analogy` (with "Where it breaks down") in deep and core chapters.
4. At least one `callout warn` titled "Common misconception".
5. At least one `callout try` titled "Try it yourself" with a small experiment (a script to run, a parameter to change, a question to answer). Use `pre.terminal` with `<span class="prompt">$</span> <span class="cmd">…</span>` for commands.
6. Where relevant, a `callout ds` titled "Systems connection" that names the engineering idea (networks, processes, storage, reliability, security) this idea depends on or mirrors. (The CSS class is `ds` for historical reasons.)
7. Volatile facts in dated `callout note` boxes (section 3).
8. `callout key` takeaways, then Further reading (`ul.sources`, 3 to 8 primary sources: papers, specs, official docs, the original blog posts), then the quiz.
9. In-text links to other chapters in this path, using paths from `authoring/link-index.md`. Link to pages that do not exist yet as well (labs, cases, studios and chapters are being written in parallel): use the exact path from the link index and the linter's broken-link errors for them are expected. Never downgrade such a link to plain text. Labs, cases and studios are linked automatically at the end of a part; you may also mention them in text.

Other components available (see `assets/css/main.css`): `<dl class="terms">` for a term list, `<div class="table-wrap"><table>…</table></div>` for tables, `<ol class="steps">` for numbered procedures, `<div class="cols"><div class="card accent-blue"><h4>…</h4><p>…</p></div>…</div>` for 2 or 3 side-by-side cards (accent-blue/green/purple/orange/red/cyan), `<details class="deeper"><summary>Go deeper <span class="hint">optional</span></summary>…</details>` for optional depth (derivations, proofs, edge cases), `<span class="badge deep|core|intro">`.

## 5. Code examples

- Every `pre.terminal` block that shows output must show output **you actually got by running the code** on this machine. Save the script in your scratch directory, run it with `python3`, paste the real output in a second block:
  ```html
  <pre class="terminal" data-title="attention.py"><code>…code, HTML-escaped (&lt; &gt; &amp;)…</code></pre>
  <pre class="terminal" data-title="output"><code>…real output…</code></pre>
  ```
- Python 3 here has the standard library and **NumPy** (2.x). Prefer the standard library; use NumPy where arrays are the point (A0 onwards). PyTorch is **not** installed: if a chapter needs PyTorch-style code (A2, A3), either show an equivalent you ran in NumPy, or show the PyTorch listing with `data-title="train.py (PyTorch, not run here)"` and no output block, and say in the text what it would print in words. Never fabricate output.
- Keep examples short (under about 60 lines), deterministic (seed every random generator), and fast (under a few seconds).
- Example code that calls a model must use the stand-in `ScriptedModel`/`RuleModel` from `lab-support/llm.py` (copy it into your scratch folder to run), so the output is real and reproducible. Show what a real API request looks like as a listing without output if useful.
- HTML-escape code inside `<code>`. Do not add syntax-highlight spans in chapters (labs' solution blocks use them; see section 8).

## 6. Diagrams (inline SVG)

Diagrams are hand-written inline SVG that the site's theme colours and (optionally) redraws in a hand-drawn style. Copy the conventions from the sample chapters:

```html
<figure class="diagram">
  <svg viewBox="0 0 760 240" role="img" aria-label="Full sentence describing what the diagram shows, for screen readers.">
    <defs><marker id="ahAG02a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="arrowhead"/></marker></defs>
    <rect x="20" y="20" width="200" height="56" rx="8" class="box"/>
    <rect x="280" y="20" width="200" height="56" rx="8" class="fs-cyan s-cyan sw-2"/>
    <text x="120" y="53" text-anchor="middle" class="t-sm t-bold">Label</text>
    <text x="120" y="70" text-anchor="middle" class="t-xs t-muted">sub-label</text>
    <line x1="220" y1="48" x2="278" y2="48" class="line" marker-end="url(#ahAG02a)"/>
  </svg>
  <figcaption><strong>Bold first phrase.</strong> One or two sentences saying what to notice.</figcaption>
</figure>
```

- Width 760 (or up to 900 for wide figures). Never hard-code colours: use classes. Fills+strokes: `box` (neutral), `fs-COLOR s-COLOR sw-2` with COLOR in blue, cyan, teal, green, yellow, orange, red, pink, purple. Solid fills (dots, bars): `f-COLOR`. Text: `t-sm`, `t-xs`, `t-bold`, `t-muted`, `t-faint`, `mono`, `t-dark` (on a solid fill), `tc-COLOR` (coloured text). Lines: `line`, `line-thin`, `line-dash`, `line s-COLOR`, `sw-2`. Arrowheads: `class="arrowhead"` (or `arrowhead f-COLOR`).
- **Marker and gradient ids must be unique on the page**: prefix with a course code and chapter/page number plus a letter: `ahMF09a`, `ahAG02b`, `ahRET13c`, `ahEVL-L1a`. (Course codes: MF, ML, DL, LT, AG, RS, EV, OE, AD.)
- Leave room: text must not overflow boxes at `t-sm` (about 7.5 px per character). Keep labels short; put detail in the caption.
- Colour meaning, used consistently across the path: green = inputs/data/clients, blue = computation/services/models, purple = stored state (stores, memory, indexes, weights), orange = queues/streams/flows in motion, cyan = caches/context/retrieved items, red = failures/attacks/errors, yellow = the thing being followed or highlighted.
- Plots: draw axes, ticks and data as SVG paths/rects from numbers you computed (compute them with a script, then write the coordinates). Label axes.

### Step-through diagrams (stepper)

For processes with an order (a training step, an agent loop, a protocol exchange, an algorithm's iterations), use the generic stepper:

```html
<div class="widget stepper" data-autoplay-ms="3500">
  <div class="widget-head"><span class="widget-tag">Step through</span><h4 class="widget-title">Title</h4></div>
  <svg viewBox="0 0 760 300" role="img" aria-label="…">
    <g>always visible</g>
    <g data-steps="2-4">visible on steps 2 to 4</g>
    <g data-steps="3-" data-active="3">visible from step 3, highlighted on step 3</g>
  </svg>
  <ol class="stepper-captions">
    <li><strong>Step one.</strong> Caption.</li>
    <li><strong>Step two.</strong> Caption.</li>
  </ol>
</div>
```
and add `<script src="../../assets/js/stepper.js"></script>` after quiz.js. Steps are 1-based; the number of steps equals the number of captions.

### Interactive widgets (optional, encouraged for a few deep chapters)

A widget is a small self-contained simulator or calculator: attention-weight explorer, temperature/top-p sampler, BM25 scorer, HNSW search visualiser, judge-bias simulator, MAP-Elites grid, KV-cache memory calculator. Rules:
- Files `assets/js/widgets/COURSEIDCHAPTERID-NAME.js` and `assets/css/widgets/COURSEIDCHAPTERID-NAME.css` (e.g. `dl09-attention.js`, root element `id="dl09-attention"`). The course id plus chapter id prefix means parallel authors never collide.
- Plain ES5-style JavaScript in an IIFE, `"use strict"`, no external libraries, no network. Find your root element by a unique id (`document.getElementById("dl-attention")`) and return if absent. Seeded randomness (mulberry32, as in `assets/js/widgets/backoff.js`).
- Markup inside `<div class="widget" id="…"><div class="widget-head"><span class="widget-tag">Try it</span><h4 class="widget-title">…</h4></div> …controls… </div>`. Reuse `widget-row`, `widget-out`, `widget-help`, `.btn`, `<input type="range">`, `<select>`. Colours only through CSS variables (`var(--blue)`, `var(--text)`, `var(--text-muted)`, `var(--bg-alt)`, `var(--border)`); check `assets/css/theme.css` for names. It must work in all three themes and at phone width (no horizontal scroll).
- Read one existing widget fully before writing one (`assets/js/widgets/backoff.js` and its CSS).
- Test it: at minimum run `node --check` on the JS. Keep it under about 400 lines.

## 7. Quizzes

6 questions for deep and core chapters, 4 for intro. Test understanding and application, not recall of trivia: "which change would fix this?", "what happens if…?", "which number is closest?". Every option plausible. The explanation says why the right answer is right *and* why the most tempting wrong answer is wrong. Vary `data-answer` (0 to 3) across questions.

## 8. Labs

A lab is a page (`<dir>/labs/lab-NN-name.html`) plus code in `<dir>/labs/code/labNN/` (two-digit NN = lab number):

- `starter.py`: the learner's file. All scaffolding given (imports, constants, data classes, helper functions not central to the lesson, docstrings with the contract and examples). Every function the learner writes raises `NotImplementedError("TODO milestone N: function_name")`.
- `check.py`: the self-check, modelled exactly on `ml/labs/code/lab01/check.py`: `python3 check.py` checks `starter.py`, `python3 check.py solution` checks `solution.py`, `python3 check.py solution 3` runs only milestone 3. One `check(number, name, fn)` per milestone printing `✔ name`, `✘ name: reason` or `… name: not implemented yet (…)`, then a final line `N/M milestones passing  (T s)`. Failures must explain what was expected, what was got, and a hint at the likely mistake. Seeded randomness; print the seed on failure so it can be replayed.
- `solution.py`: a complete, clean, commented reference answer.
- Optional data/fixtures (`corpus.json`, `traces.jsonl`, …) and, when a model is involved, an **exact copy** of `lab-support/llm.py` named `llm.py`. Do not modify the copy; put lab-specific fake models in the lab's own files (e.g. a `RuleModel` configured in `starter.py` or a `fixtures.py`).
- **Standard library only** (Python 3.9+). No NumPy, no pip installs. Labs about ML implement the maths over lists; keep sizes small enough that `python3 check.py solution` finishes in under 60 seconds (aim for under 15). Deterministic: same output every run.
- 4 to 6 milestones, each building on the previous one, from a warm-up to the real thing. Each milestone tests behaviour through public functions, with hand-checked values first, then seeded property checks, then a scenario.
- An optional final section on the page, "Run it against a real model", may show how to set `LAB_MODEL` and what to look for; check.py never uses a real model.
- **Verify before you finish**: run `python3 check.py` (every milestone must show "not implemented yet", none may crash) and `python3 check.py solution` (all ✔). Paste both real outputs into the lab page (the initial one near the top, the final one at the end). Delete any `__pycache__` you create.

The lab page follows `design/labs/lab-01-estimation.html`: lede, `callout why` ("Why this lab matters"), a `callout note` on determinism and requirements, "What you'll build" (a diagram plus `ol.steps` of the milestones), "Before you start" (file table linking `code/labNN/starter.py`, `check.py`, `solution.py`, and the first check output), then one `h2` per milestone containing explanation, then
```html
<div class="milestone">
  <p class="milestone-title">Your task</p>
  <p>What to write.</p>
  <p class="checkpoint">What check.py verifies for this milestone.</p>
  <details class="deeper"><summary>Hints <span class="hint">try without first</span></summary><ul><li>…</li></ul></details>
  <details class="deeper"><summary>Solution <span class="hint">spoiler</span></summary>
<pre><code>…the solution code for this milestone, with spans: <span class="kw">def</span>, <span class="str">"…"</span>, <span class="num">3</span>, <span class="cmt"># …</span>…</code></pre>
  </details>
</div>
```
then "Going further" ideas, then a quiz of 4 to 6 questions. Lab page length is driven by the milestones: explain each concept enough that someone who skimmed the chapter can succeed.

## 9. Case studies

A case study is a real system, paper, product or incident, built around one pattern (the catalog gives the pattern). Model: `llm-training/cases/case-01-instructgpt.html`.

- **Read the primary sources** with WebFetch/WebSearch before writing: the paper, the engineering post, the court ruling, the official post-mortem, the spec. Prefer the original over news coverage. If a source cannot be fetched, say so.
- Start with `<div class="callout note"><p class="callout-title">What I could and could not read</p>…</div>` listing what was fetched and read, what was only seen through secondary coverage, and anything uncertain.
- Then `<div class="callout why"><p class="callout-title">The pattern in one sentence</p><p><strong>…</strong></p></div>`.
- Sections typically: Context; the mechanism (how it works, with diagrams and numbers from the source); what happened / the results; what the critics or later work said; the lessons, linked to chapters; "Try it yourself" where possible (a small script that reproduces the core idea, run, with real output).
- A `<dl class="terms">` of key terms near the top.
- End with `<h2>Sources</h2><ul class="sources">…</ul>`: each source with link, date, "Fetched and read" or "Not fetched; seen via …", and what it supplied. Then a quiz of 4 questions.
- Every number and quote must come from a source you read. Attribute claims ("the paper reports", "the company said"). Distinguish the source's claims from independent verification. Be fair to the people involved; describe failures without mockery.
- Length: 2,500 to 4,500 words, 2 to 4 diagrams.

## 10. Design studios

Model: `llm-training/studios/studio-01-domain-adaptation.html`. A studio is a 45 to 90 minute mock design session or (in A8) a take-home simulation.

- `callout why` titled "How a design studio works" (adapt the sample's text), then `div.studio-brief` with `p.brief-title` "📐 The brief", the prompt in quotes, constraints as bullets, "Builds on" links and a time box.
- `<h2>Your notes</h2>` + `<textarea class="studio-notes" aria-label="…" placeholder="…"></textarea>`.
- 8 to 12 `<section class="stage">` blocks: `<h2><span class="h-num">1</span>Stage title</h2>`, `<p class="stage-q">Your-turn question</p>`, `<details class="reveal"><summary>Compare with a worked answer</summary> … </details>`. Stages for AI designs: clarify the problem and users, success metrics and evaluation plan, estimate (tokens, cost, latency, volumes), data and context, architecture (diagram), model and prompt/tool strategy, deep dives, failure modes and safety, rollout and monitoring, trade-offs, spoken summary. Worked answers include numbers computed by a script you ran (show code and real output where it helps), diagrams, and tables.
- The last stage includes a `callout mentor` "How a senior engineer would summarise this" (a spoken paragraph) and the shape of the answer in bold.
- Then `<h2>Rubric</h2><ul class="rubric"><li>…</li></ul>` with 10 to 14 concrete signals (bold the key phrase), `<p class="studio-status" id="studio-status"></p>`, and a `callout key`.
- A8 take-home studios add: a time box (4 to 6 hours), the deliverables list (one-page requirements restatement with assumptions and questions, baseline before framework, small gold set with labelling procedure, eval with confidence intervals, quality/cost/latency table, error-analysis memo naming the first failure in sampled traces, limitations section, a three-minute oral defence), sample input data described concretely, and a grading rubric. Worked answers show an excellent submission's key artefacts.
- Length: 4,000 to 7,000 words.

## 11. Course roadmap pages and toolboxes

- `<dir>/index.html` exists already (written by the coordinator); do not edit unless asked.
- `<dir>/toolbox.html` (when assigned): `data-page="toolbox"`, `callout tool` "How to use this page" stating honestly what you ran and what you did not, then one `<section class="tool-card" id="TOOLID">` per tool in the catalog (ids must match), each with `h3`, `p.tool-meta` (install, alternatives, chapters with links), what it is for, and a "10-minute guided exercise" with commands. Mark commands you could not run here (most tools are not installed) as illustrative, and never paste invented output; describe what to look for instead.

## 12. Glossary entries

For every chapter you write, also write `glossary-src/COURSEID-CHAPTERID.json`: a JSON list of 5 to 15 of the chapter's key terms:
```json
[{"term": "KV cache", "def": "Stored keys and values of earlier tokens, so each new token's attention does not recompute them.", "file": "llm-training/chapters/18-kv-cache.html"}]
```
Definitions are one sentence, plain, British English, no em-dashes. Use the exact capitalisation you would want in an index. Labs, cases and studios do not need glossary files.

## 13. Accuracy and research

- You know a lot; still, check what is checkable. Use WebSearch/WebFetch for anything dated after 2023, any number you state, spec details (MCP, A2A, OpenTelemetry), regulatory dates (EU AI Act), benchmark facts and library behaviour. The research notes in `/Users/danish/Desktop/projects/cs-refresh/research_notes/Zero to AI systems engineer curriculum/` and the report in `/Users/danish/Desktop/projects/cs-refresh/reports/Zero to AI systems engineer curriculum.md` summarise what was verified in October 2026 (with caveats); use them as leads and check the original where it matters.
- Model names in some 2026 aggregator sources could not be verified. Avoid naming specific current model versions unless a primary source confirms them; prefer "frontier models" or a dated note.
- Equations: see section 15. Never a centred `<p style="text-align:center">` of HTML maths.
- Derivations go in full when the chapter is deep (for example the DPO loss from the KL-regularised objective, the REINFORCE gradient, BM25's components, attention's scaling factor), with optional detail in `details.deeper`.

## 14. Before you report done

Run this checklist on every file you wrote:

1. `python3 authoring/check_page.py PATH…` (the page linter; it checks skeleton, data attributes against the catalog, unique marker ids, relative links that do not resolve, quiz answers, em-dashes, American spellings and terminal blocks). Fix everything it reports.
2. Every code example's output was produced by running it.
3. Labs: `check.py` on starter (all "not implemented yet") and solution (all ✔) both run clean; outputs pasted into the page.
4. Glossary JSON written for each chapter.
5. No files outside your assignment changed. Do not run git commands that change state (no commit, checkout, reset, stash).
6. Scratch work lives in `$TMPDIR/<your unit id>/` (other authors share `$TMPDIR`). Remove any `__pycache__` folders you created in the site.

Your final report to the coordinator must be short (under 200 words): files written, approximate word counts, anything you could not verify, any catalog change you recommend, and any widget you added. Do not paste page content into the report.

## 15. Equations

Readers come to this path from school mathematics. A display of Greek letters with no help is the single most reliable way to lose them, so every equation is written to be **read**, not decoded. `assets/js/equations.js` typesets maths with KaTeX (vendored, no network) and adds the interactive parts; `node authoring/check_tex.js PAGE` checks every formula (`check_page.py` runs it for you). Reference implementation: both equations in `llm-training/cases/case-01-instructgpt.html` (search for `figure class="eq"`).

### Three kinds of display

1. **Simple formula** (one idea, at most two operators deep, or symbols already explained nearby): typeset it, and keep the old HTML inside as the fallback shown without JavaScript.
   ```html
   <div class="eq-display" data-tex="\sigma(z) = \frac{1}{1 + e^{-z}}">&sigma;(z) = 1 / (1 + e<sup>&minus;z</sup>)</div>
   ```
2. **Worked arithmetic or a formula written in words** (`(784×128 + 128) + … = 101,770 parameters`, `throughput = 1,460 bytes ÷ 0.080 s ≈ 146 kbit/s`, `estimate ± 1.96 × standard error`): TeX adds nothing. Keep it as HTML, centred with the class instead of an inline style: `<p class="eq-plain">…</p>`.
3. **Load-bearing equation** (any of: an expectation or average 𝔼, a sum or product over an index, three or more nested operations, or it is the equation the chapter exists to explain): a full anatomy block, `<figure class="eq">`, followed by a runnable "plug in numbers" script.

Inline maths in prose is optional: `<span class="tex" data-tex="r_\theta(x, y)">r<sub>&theta;</sub>(x, y)</span>`. Use it for symbols the reader must match against a display; leave ordinary prose in HTML.

### The anatomy block

```html
<figure class="eq" id="eq-SHORT-NAME">
  <div class="eq-display" data-tex="… \htmlClass{eq-t1}{TERM} … \htmlClass{eq-t2}{TERM} …">…old HTML as fallback…</div>
  <p class="eq-read">The whole equation in one or two plain sentences, no symbols.</p>
  <dl class="eq-terms">
    <div data-term="t1"><dt data-tex="TERM">fallback</dt>
      <dd><span class="eq-type">scalar</span>What it is, in words, with its range or a typical value.</dd></div>
    <div><dt data-tex="\pi_\phi(y \mid x)">fallback</dt>
      <dd><span class="eq-type">probability</span>A symbol worth defining that is not coloured in the equation.</dd></div>
  </dl>
  <ol class="eq-steps">
    <li data-tex="PARTIAL EXPRESSION" data-terms="t1 t2">Build-up step 1: the innermost idea first.</li>
    <li data-tex="BIGGER EXPRESSION" data-terms="t3">Step 2 adds one operation, and says why it is there.</li>
  </ol>
</figure>
```

- **The reading** (`eq-read`) comes first in importance. If you cannot say the equation in one or two plain sentences, the reader cannot either.
- **The legend** defines every symbol the reader could stumble on, including notation itself (𝔼, ∼, |, ∑, ∇, ‖·‖, log, σ). Each row starts with an `eq-type` pill naming what kind of thing it is: `scalar`, `scalar ≥ 0`, `vector (d,)`, `matrix (n, d)`, `probability`, `distribution`, `function ℝ → (0, 1)`, `index`, `average`, `sign`. Not knowing what *kind* of thing a symbol is causes most of the confusion. Give a typical value or range where you can (σ(0) = 0.5; β is usually 0.01 to 0.5).
- **Colour terms** with `\htmlClass{eq-tN}{…}` in the display, N from 1 to 8, matching `data-term="tN"` in the legend. Colour the 3 to 7 parts the build-up talks about, not every symbol. A legend row without `data-term` is a definition with no colour.
- **The build-up** (`eq-steps`) assembles the equation from the inside out, one operation per step, 3 to 7 steps. Each `li` has a `data-tex` (the partial expression so far; use `\ldots` for parts already shown) and `data-terms` (the colour ids this step introduces; terms not yet reached are dimmed in the display). Each caption says what the step does and **why it is there**, with a number where possible ("a gap of +2 means about 0.88").
- **Long equations**: split over lines with `\begin{aligned} … = {} & … \\ & + … \end{aligned}` so nothing scrolls sideways at desktop width.
- **Plug in numbers**: directly after the figure, a short sentence, a `callout idea` box, then a runnable script (`pre data-title="NAME.py"`, standard library only) that computes the equation on a few hand-picked numbers with one printed line or column per build-up step, and its real output block. Follow the code style in section 5 (≤ 80 columns, docstring, `# ── N. Title ───` banners, named constants with comments).
- Macros available everywhere: `\E` (𝔼), `\R` (ℝ), `\KL`, `\softmax`, `\argmax`, `\argmin`. Use `\mid` for "given", `\text{…}` for words inside maths, `\operatorname{name}` for multi-letter functions.
- Quote the source's equation faithfully (same symbols as the paper or textbook you cite), then explain it. Do not "simplify" a published equation into a different one.

## 16. Workbenches

A **workbench** repeats a chapter's idea with the real tools on a real machine (PyTorch, Hugging Face, TRL, vLLM, Ollama, scikit-learn). Labs stay standard-library-only and toy-sized; workbenches are where the reader meets the tools practitioners use, and **measures** something the chapter predicts. Reference: `llm-training/workbench/w01-kv-cache.html` and `llm-training/workbench/code/w01/kv_cache.py`.

- **Files.** Page `<course>/workbench/wNN-name.html` with `<body … data-workbench="WN">`; code in `<course>/workbench/code/wNN/` (one or two `.py` scripts, plus helper data if any); a paired notebook generated with `python3 authoring/py2ipynb.py SCRIPT.py` (never hand-edit the `.ipynb`). The catalog entry (id, file, title, machine, chapters, time, cost, blurb) is in the `WORKBENCHES` block at the end of `assets/js/catalog.js`; the h1 is "Workbench N: Title".
- **Machine.** `laptop` (Apple MPS or CPU; models up to a few hundred million parameters; Ollama for local language models), `linux`, or `gpu` (one 24 GB NVIDIA card, rented; see `lab-machine.html#gpu` and `workbench/wb`). Requirements are `workbench/requirements.txt` (both) and `workbench/requirements-gpu.txt` (bitsandbytes, TRL, vLLM: Linux + CUDA only).
- **Page skeleton**, in order: `chapter-head` (h1, lede); `callout why` "Why measure it"; `callout note` "What you need" (machine, disk, time; GPU time in hours, no dollar figures outside a dated State of play box); h2 **Predict before you run**: the chapter's formula as an `eq-display` linking the chapter's anatomy block, the inputs from the model's real config, a `callout predict` asking the reader to work it out, and the answer in a `details.deeper`; h2 **Set up** / **Run it**: a `callout idea` box, the script as `<pre class="terminal" data-title="NAME.py" data-run="off">`, links to the `.py` and `.ipynb`; real output in `<pre class="terminal" data-title="output (WHERE IT RAN)">`; h3 **What you should see**: each output line explained; for GPU parts, a `measure-table` (see below); h2 **Break it**: 2 to 4 experiments, each with a prediction first; `callout key`.
- **Honesty rule for output.** Paste only output you produced by running the script. GPU-only parts cannot be run on the authoring machine: say so in a `callout note` titled "Not run here", give **predictions computed from published configs and the chapter's formulas** (show the arithmetic), and give the reader a measurement table. Never invent a measured number, a loss curve or a timing. Qualitative expectations ("the third ratio comes in below 1, because…") must follow from the mechanism or from a cited source.
- **Measurement tables** persist what the reader types and show measured ÷ predicted:
  ```html
  <div class="table-wrap"><table class="measure-table">
    <thead><tr><th>Quantity</th><th>Predicted</th><th>Measured</th><th>Ratio</th></tr></thead>
    <tbody><tr data-predict="224"><td>Cache per 4,096-token sequence, MiB</td><td>224</td><td><input name="seq_mib"></td><td class="ratio"></td></tr></tbody>
  </table></div>
  ```
- **Scripts.** Section 5's style (≤ 80 columns, docstring with usage, `# ── N. Title ───` banners). `args, _ = ap.parse_known_args()` so the notebook runs. Pick the device in order CUDA, MPS, CPU. Laptop defaults must finish in minutes on a laptop; a flag (`--model`, `--sweep`, `--full`) scales up for the GPU. Pin models by Hugging Face id and say how big the download is. Seed everything.
- **Models and datasets.** Prefer small, open, ungated ones (SmolLM2, Qwen2.5 0.5B to 7B, GPT-2, Tiny Shakespeare, text8, GSM8K). Read sizes and architecture numbers from the real `config.json` and `model.safetensors.index.json`, not from memory.

