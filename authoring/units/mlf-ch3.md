# Unit: mlf-ch3

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `ml-foundations/chapters/08-derivatives.html` · chapter 08 · **deep** · Part 3 (Calculus & Optimisation) · **Derivatives & the Chain Rule**: Slopes, partial derivatives, gradients and the one rule that makes deep learning possible.  → glossary `glossary-src/mlf-08.json`
- `ml-foundations/chapters/09-autodiff.html` · chapter 09 · **deep** · Part 3 (Calculus & Optimisation) · **Automatic Differentiation**: Computation graphs, forward and reverse mode, and a tiny autograd engine built by hand.  → glossary `glossary-src/mlf-09.json`
- `ml-foundations/chapters/10-optimisers.html` · chapter 10 · **deep** · Part 3 (Calculus & Optimisation) · **Gradient Descent & Optimisers**: Learning rates, SGD, momentum, Adam and AdamW, schedules and what can go wrong.  → glossary `glossary-src/mlf-10.json`
- `ml-foundations/chapters/11-numerics.html` · chapter 11 · **core** · Part 3 (Calculus & Optimisation) · **Floating Point & Numerical Stability**: How floats work, overflow and underflow, stable softmax, and fp16, bf16 and fp8.  → glossary `glossary-src/mlf-11.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-ch3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).