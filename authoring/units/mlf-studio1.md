# Unit: mlf-studio1

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: design studios

- `ml-foundations/studios/studio-01-experiment-design.html` (data-studio `S1`, after Part 4) · **Design an Experiment That Can Fail**: Decide whether a change really helped: metric, sample size, stopping rule and what would change your mind. Related chapters: 15, 04.
- `ml-foundations/studios/studio-02-compute-budget.html` (data-studio `S2`, after Part 5) · **Budget the Compute for a Project**: Turn a research plan into GPU-hours, memory, storage and a bill, with the risky assumptions named. Related chapters: 17, 16.
- The course toolbox `ml-foundations/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `jupyter` (Jupyter & notebooks), `numpy` (NumPy), `pandas` (pandas & DuckDB), `uv` (uv & virtual environments), `plotting` (matplotlib), `free-gpus` (Colab & Kaggle notebooks), `papers` (arXiv, Semantic Scholar & Papers with Code). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).