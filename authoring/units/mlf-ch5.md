# Unit: mlf-ch5

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml-foundations/chapters/16-reading-papers.html` · chapter 16 · **core** · Part 5 (Working Practice) · **Reading Papers Efficiently**: A three-pass method, what to skip, how to check claims and how to reproduce a result.  → glossary `glossary-src/mlf-16.json`
- `ml-foundations/chapters/17-compute-costs.html` · chapter 17 · **core** · Part 5 (Working Practice) · **GPUs, Clouds & What Compute Costs**: What a GPU is good at, memory versus FLOPs, renting hardware and estimating a bill.  → glossary `glossary-src/mlf-17.json`
- `ml-foundations/chapters/18-technical-writing.html` · chapter 18 · **core** · Part 5 (Working Practice) · **Writing for Engineers**: Design docs, experiment reports and error-analysis memos that people actually read.  → glossary `glossary-src/mlf-18.json`
- `ml-foundations/chapters/19-ai-assistants.html` · chapter 19 · **intro** · Part 5 (Working Practice) · **Learning with AI Assistants**: Using coding assistants to go faster without outsourcing the understanding.  → glossary `glossary-src/mlf-19.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-ch5/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).