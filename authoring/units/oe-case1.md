# Unit: oe-case1

Course: **A7 Search, Evolution & Self-Improving Agents** (id `oe`, folder `open-ended/`).

## Course brief
A7 covers search and open-endedness: bandits/MCTS, evolutionary algorithms, novelty search, quality-diversity/MAP-Elites, POET, OMNI/OMNI-EPIC, Voyager, inference-time search (best-of-n, self-consistency, AB-MCTS), FunSearch, AlphaEvolve, OpenEvolve and ShinkaEvolve, prompt/pipeline evolution (EvoPrompt, PromptBreeder, DSPy optimisers), ADAS/Meta Agent Search, the Darwin Gödel Machine, The AI Scientist, evaluator and reward hacking (including the AI CUDA Engineer episode), held-out evaluation, safety of self-modifying systems, and search in real products. Verified arXiv ids from planning: MAP-Elites 1504.04909, POET 1901.01753, AI-GAs 1905.10985, Voyager 2305.16291, Eureka 2310.12931, OMNI-EPIC 2405.15568, ADAS 2408.08435, AB-MCTS 2503.04412, DGM 2505.22954, AlphaEvolve 2506.13131, ALE-Bench 2506.09050, ShinkaEvolve 2509.19349 (check others). Sakana AI's work is prominent here; present it on its merits alongside DeepMind, Uber AI, Jeff Clune's and Kenneth Stanley's lines. Runnable examples in pure Python with seeded randomness; anywhere an LLM is the mutation operator, use a deterministic stand-in mutation function and say so.

## Your assignment: case studies

- `open-ended/cases/case-01-alphazero.html` (data-case `C1`) · **AlphaGo to AlphaZero** · pattern: Search plus learning · Tree search guided by a learned policy and value, and what self-play removed. Related: 01.
- `open-ended/cases/case-02-picbreeder.html` (data-case `C2`) · **Picbreeder & Why Greatness Cannot Be Planned** · pattern: Stepping stones · Images nobody aimed for, found by people following what was interesting. Related: 03, 05.
- `open-ended/cases/case-03-funsearch.html` (data-case `C3`) · **FunSearch and the Cap Set** · pattern: Evolving programs, not answers · A language model in an evolutionary loop that found new constructions in mathematics. Related: 09.
- `open-ended/cases/case-04-alphaevolve.html` (data-case `C4`) · **AlphaEvolve** · pattern: Evolution with evaluators · Evolving whole codebases against automatic evaluators, from matrix multiplication to data-centre scheduling. Related: 09, 10.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/oe-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).