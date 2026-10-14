# Unit: oe-lab3

Course: **A7 Search, Evolution & Self-Improving Agents** (id `oe`, folder `open-ended/`).

## Course brief
A7 covers search and open-endedness: bandits/MCTS, evolutionary algorithms, novelty search, quality-diversity/MAP-Elites, POET, OMNI/OMNI-EPIC, Voyager, inference-time search (best-of-n, self-consistency, AB-MCTS), FunSearch, AlphaEvolve, OpenEvolve and ShinkaEvolve, prompt/pipeline evolution (EvoPrompt, PromptBreeder, DSPy optimisers), ADAS/Meta Agent Search, the Darwin Gödel Machine, The AI Scientist, evaluator and reward hacking (including the AI CUDA Engineer episode), held-out evaluation, safety of self-modifying systems, and search in real products. Verified arXiv ids from planning: MAP-Elites 1504.04909, POET 1901.01753, AI-GAs 1905.10985, Voyager 2305.16291, Eureka 2310.12931, OMNI-EPIC 2405.15568, ADAS 2408.08435, AB-MCTS 2503.04412, DGM 2505.22954, AlphaEvolve 2506.13131, ALE-Bench 2506.09050, ShinkaEvolve 2509.19349 (check others). Sakana AI's work is prominent here; present it on its merits alongside DeepMind, Uber AI, Jeff Clune's and Kenneth Stanley's lines. Runnable examples in pure Python with seeded randomness; anywhere an LLM is the mutation operator, use a deterministic stand-in mutation function and say so.

## Your assignment: labs

- Page `open-ended/labs/lab-05-meta-agent.html` (data-lab `L5`, after Part 4) with code in `open-ended/labs/code/lab05/` · **Lab 5: A Mini Meta-Agent Search**: Search over agent designs on a small benchmark, with separate search and held-out splits. Related chapters: 12, 16.
  - Design notes: Agent designs are small Python configurations or composed functions (e.g. choose among prompt strategies, self-consistency n, verification step) evaluated on a stand-in benchmark where a seeded simulated model answers questions with accuracy depending on the design; meta agent proposes new designs from the archive; strict search/validation/test splits; show selection bias when reporting the best-of-many on the search split.
- Page `open-ended/labs/lab-06-gameable-evaluator.html` (data-lab `L6`, after Part 5) with code in `open-ended/labs/code/lab06/` · **Lab 6: The Gameable Evaluator**: Watch a search loop exploit a leaky scorer, then harden the harness until the exploits stop. Related chapters: 15, 16.
  - Design notes: A search loop optimising code or parameters against a leaky evaluator (e.g. timing measured wrongly, a test that can be satisfied by special-casing inputs, a reward that reads its own output file). The learner first watches the loop exploit it, then hardens the harness (randomised hidden tests, held-out inputs, sandboxed I/O, output validation) until exploits stop; the check verifies each hardening blocks its exploit and keeps honest solutions passing.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `open-ended/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/oe-lab3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).