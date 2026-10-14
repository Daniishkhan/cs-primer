# Unit: mlf-case1

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: case studies

- `ml-foundations/cases/case-01-reinhart-rogoff.html` (data-case `C1`) · **A Spreadsheet Error That Shaped Policy** · pattern: Reproducible analysis · An influential economics result that a student could not reproduce, and what the spreadsheet hid. Related: 03, 04.
- `ml-foundations/cases/case-02-patriot-missile.html` (data-case `C2`) · **The Patriot Missile Clock** · pattern: Floating-point drift · A tiny rounding error, accumulated over 100 hours of uptime, and a missed interception. Related: 11.
- `ml-foundations/cases/case-03-adamw.html` (data-case `C3`) · **AdamW: Weight Decay Done Right** · pattern: Optimiser details matter · Why L2 regularisation and weight decay stop being the same thing inside Adam. Related: 10.
- `ml-foundations/cases/case-04-mixed-precision.html` (data-case `C4`) · **Mixed-Precision Training** · pattern: Fewer bits, same model · Half-precision arithmetic, loss scaling and master weights: how training got twice as cheap. Related: 11, 17.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).