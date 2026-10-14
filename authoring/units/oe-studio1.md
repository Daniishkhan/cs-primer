# Unit: oe-studio1

Course: **A7 Search, Evolution & Self-Improving Agents** (id `oe`, folder `open-ended/`).

## Course brief
A7 covers search and open-endedness: bandits/MCTS, evolutionary algorithms, novelty search, quality-diversity/MAP-Elites, POET, OMNI/OMNI-EPIC, Voyager, inference-time search (best-of-n, self-consistency, AB-MCTS), FunSearch, AlphaEvolve, OpenEvolve and ShinkaEvolve, prompt/pipeline evolution (EvoPrompt, PromptBreeder, DSPy optimisers), ADAS/Meta Agent Search, the Darwin Gödel Machine, The AI Scientist, evaluator and reward hacking (including the AI CUDA Engineer episode), held-out evaluation, safety of self-modifying systems, and search in real products. Verified arXiv ids from planning: MAP-Elites 1504.04909, POET 1901.01753, AI-GAs 1905.10985, Voyager 2305.16291, Eureka 2310.12931, OMNI-EPIC 2405.15568, ADAS 2408.08435, AB-MCTS 2503.04412, DGM 2505.22954, AlphaEvolve 2506.13131, ALE-Bench 2506.09050, ShinkaEvolve 2509.19349 (check others). Sakana AI's work is prominent here; present it on its merits alongside DeepMind, Uber AI, Jeff Clune's and Kenneth Stanley's lines. Runnable examples in pure Python with seeded randomness; anywhere an LLM is the mutation operator, use a deterministic stand-in mutation function and say so.

## Your assignment: design studios

- `open-ended/studios/studio-01-optimisation-loop.html` (data-studio `S1`, after Part 3) · **Design an Automated Optimisation Loop**: Evolve a scheduling heuristic for a business: evaluator, budget, archive, safety and rollout. Related chapters: 09, 10, 16.
- `open-ended/studios/studio-02-review-claim.html` (data-studio `S2`, after Part 5) · **Review a Self-Improvement Claim**: A team says its agent improved itself by 30%. Decide what you need to see before you believe it. Related chapters: 15, 16, 17.
- The course toolbox `open-ended/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `openevolve` (OpenEvolve), `shinka` (ShinkaEvolve), `pyribs` (pyribs), `dspy` (DSPy), `evotorch` (Evolution-strategy libraries). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/oe-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).