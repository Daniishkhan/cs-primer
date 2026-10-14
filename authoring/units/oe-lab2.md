# Unit: oe-lab2

Course: **A7 Search, Evolution & Self-Improving Agents** (id `oe`, folder `open-ended/`).

## Course brief
A7 covers search and open-endedness: bandits/MCTS, evolutionary algorithms, novelty search, quality-diversity/MAP-Elites, POET, OMNI/OMNI-EPIC, Voyager, inference-time search (best-of-n, self-consistency, AB-MCTS), FunSearch, AlphaEvolve, OpenEvolve and ShinkaEvolve, prompt/pipeline evolution (EvoPrompt, PromptBreeder, DSPy optimisers), ADAS/Meta Agent Search, the Darwin Gödel Machine, The AI Scientist, evaluator and reward hacking (including the AI CUDA Engineer episode), held-out evaluation, safety of self-modifying systems, and search in real products. Verified arXiv ids from planning: MAP-Elites 1504.04909, POET 1901.01753, AI-GAs 1905.10985, Voyager 2305.16291, Eureka 2310.12931, OMNI-EPIC 2405.15568, ADAS 2408.08435, AB-MCTS 2503.04412, DGM 2505.22954, AlphaEvolve 2506.13131, ALE-Bench 2506.09050, ShinkaEvolve 2509.19349 (check others). Sakana AI's work is prominent here; present it on its merits alongside DeepMind, Uber AI, Jeff Clune's and Kenneth Stanley's lines. Runnable examples in pure Python with seeded randomness; anywhere an LLM is the mutation operator, use a deterministic stand-in mutation function and say so.

## Your assignment: labs

- Page `open-ended/labs/lab-03-program-evolution.html` (data-lab `L3`, after Part 3) with code in `open-ended/labs/code/lab03/` · **Lab 3: A Mini FunSearch**: Evolve bin-packing heuristics as code with an island archive and a pluggable mutation operator. Related chapters: 09, 10.
  - Design notes: FunSearch-style loop over Python heuristic functions for online bin packing; the 'LLM' is a deterministic mutation operator that edits code (e.g. via a small grammar of expression edits on an AST) with a seed. Islands, an archive, evaluation on a search set of instances and reporting on held-out instances. Make sure evaluated code runs in a restricted way (no imports, time-limited by step count).
- Page `open-ended/labs/lab-04-ab-mcts.html` (data-lab `L4`, after Part 3) with code in `open-ended/labs/code/lab04/` · **Lab 4: Adaptive Branching over Many Models**: Decide when to sample a new answer, refine an old one or switch models, under a call budget. Related chapters: 08.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `open-ended/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/oe-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).