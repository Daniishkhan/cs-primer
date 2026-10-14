# Unit: mlf-ch1

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml-foundations/chapters/00-start-here.html` · chapter 00 · **intro** · Part 0 (Orientation) · **Start Here**: What AI systems engineers build, the nine courses, and how to use them without drowning.  → glossary `glossary-src/mlf-00.json`
- `ml-foundations/chapters/01-python-numerics.html` · chapter 01 · **core** · Part 1 (Python for ML Work) · **Python for Numerical Work**: Numbers, lists and loops, why pure Python is slow for maths, and the idea of vectorising.  → glossary `glossary-src/mlf-01.json`
- `ml-foundations/chapters/02-numpy-arrays.html` · chapter 02 · **deep** · Part 1 (Python for ML Work) · **NumPy, Arrays & Broadcasting**: Shapes, strides, axes and broadcasting: the mental model behind every tensor library.  → glossary `glossary-src/mlf-02.json`
- `ml-foundations/chapters/03-data-wrangling.html` · chapter 03 · **core** · Part 1 (Python for ML Work) · **Data Wrangling: pandas, SQL & Tidy Data**: Loading, joining, grouping and cleaning tables, and the questions to ask any dataset.  → glossary `glossary-src/mlf-03.json`
- `ml-foundations/chapters/04-reproducible-experiments.html` · chapter 04 · **core** · Part 1 (Python for ML Work) · **Reproducible Experiments**: Environments, pinned versions, seeds, notebooks versus scripts and experiment logs.  → glossary `glossary-src/mlf-04.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-ch1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).