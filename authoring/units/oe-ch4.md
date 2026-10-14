# Unit: oe-ch4

Course: **A7 Search, Evolution & Self-Improving Agents** (id `oe`, folder `open-ended/`).

## Course brief
A7 covers search and open-endedness: bandits/MCTS, evolutionary algorithms, novelty search, quality-diversity/MAP-Elites, POET, OMNI/OMNI-EPIC, Voyager, inference-time search (best-of-n, self-consistency, AB-MCTS), FunSearch, AlphaEvolve, OpenEvolve and ShinkaEvolve, prompt/pipeline evolution (EvoPrompt, PromptBreeder, DSPy optimisers), ADAS/Meta Agent Search, the Darwin Gödel Machine, The AI Scientist, evaluator and reward hacking (including the AI CUDA Engineer episode), held-out evaluation, safety of self-modifying systems, and search in real products. Verified arXiv ids from planning: MAP-Elites 1504.04909, POET 1901.01753, AI-GAs 1905.10985, Voyager 2305.16291, Eureka 2310.12931, OMNI-EPIC 2405.15568, ADAS 2408.08435, AB-MCTS 2503.04412, DGM 2505.22954, AlphaEvolve 2506.13131, ALE-Bench 2506.09050, ShinkaEvolve 2509.19349 (check others). Sakana AI's work is prominent here; present it on its merits alongside DeepMind, Uber AI, Jeff Clune's and Kenneth Stanley's lines. Runnable examples in pure Python with seeded randomness; anywhere an LLM is the mutation operator, use a deterministic stand-in mutation function and say so.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `open-ended/chapters/12-meta-agent-search.html` · chapter 12 · **deep** · Part 4 (Meta Agents) · **Automated Design of Agentic Systems**: A meta agent that writes agents as code, keeps an archive and searches for better designs.  → glossary `glossary-src/oe-12.json`
- `open-ended/chapters/13-self-improving-agents.html` · chapter 13 · **deep** · Part 4 (Meta Agents) · **Self-Improving Coding Agents**: The Darwin Gödel Machine: an agent that edits its own scaffold, validated empirically.  → glossary `glossary-src/oe-13.json`
- `open-ended/chapters/14-automated-science.html` · chapter 14 · **core** · Part 4 (Meta Agents) · **Automated Science**: The AI Scientist: ideas, experiments, papers and automated review, and their limits.  → glossary `glossary-src/oe-14.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/oe-ch4/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).