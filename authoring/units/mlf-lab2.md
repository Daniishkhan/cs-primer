# Unit: mlf-lab2

Course: **A0 Math & Code for Machine Learning** (id `mlf`, folder `ml-foundations/`).

## Course brief
A0 is the mathematical and practical toolkit for the whole AI path, taught at the point of need. Learners know school maths and Python basics, and have (or are doing) the Zero to Systems engineering courses. Every chapter must say which later course uses the idea (e.g. SVD returns in LoRA, llm-training ch 11; KL returns in PPO/DPO, llm-training ch 8 and 12; the bootstrap returns in eval statistics, evals ch 4). Notation: vectors bold-free lowercase (x, w), matrices uppercase (W, X), shapes written (rows, cols) as in NumPy, gradient as ∇. Examples in pure Python first, then NumPy. Keep it gentle but rigorous: show the derivation, then the code that checks it numerically.

## Your assignment: labs

- Page `ml-foundations/labs/lab-03-optimisers.html` (data-lab `L3`, after Part 3) with code in `ml-foundations/labs/code/lab03/` · **Lab 3: The Optimiser Race**: SGD, momentum, RMSProp, Adam and AdamW on classic test surfaces, with schedules and clipping. Related chapters: 10, 11.
- Page `ml-foundations/labs/lab-04-likelihood.html` (data-lab `L4`, after Part 4) with code in `ml-foundations/labs/code/lab04/` · **Lab 4: Sampling, Likelihood & Entropy**: Samplers, maximum-likelihood fits, stable log-softmax, temperature, entropy and KL. Related chapters: 12, 13, 14.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `ml-foundations/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/mlf-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).