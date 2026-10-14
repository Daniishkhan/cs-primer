# Unit: dl-case2

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: case studies

- `deep-learning/cases/case-05-flashattention.html` (data-case `C5`) · **FlashAttention** · pattern: IO-aware algorithms · Same maths, far less memory traffic: an exact attention kernel that changed context lengths. Related: 19, sys:21.
- `deep-learning/cases/case-06-glitch-tokens.html` (data-case `C6`) · **SolidGoldMagikarp: Glitch Tokens** · pattern: Tokeniser-model mismatch · Tokens that existed in the vocabulary but almost never in training, and the odd behaviour they caused. Related: 13.
- `deep-learning/cases/case-07-opt-logbook.html` (data-case `C7`) · **Training OPT-175B: The Logbook** · pattern: Operating a training run · A public diary of restarts, loss spikes and hardware failures in a large training run. Related: 17.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-case2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).