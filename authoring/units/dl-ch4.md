# Unit: dl-ch4

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `deep-learning/chapters/12-building-gpt.html` · chapter 12 · **deep** · Part 3 (Attention & the Transformer) · **Building a GPT**: A decoder-only Transformer, end to end, trained on characters and read line by line.  → glossary `glossary-src/dl-12.json`
- `deep-learning/chapters/13-tokenisation.html` · chapter 13 · **deep** · Part 4 (Tokens & Language Modelling) · **Tokenisation**: Characters, bytes and byte-pair encoding, vocabulary size, and the bugs tokenisers cause.  → glossary `glossary-src/dl-13.json`
- `deep-learning/chapters/14-language-modelling.html` · chapter 14 · **deep** · Part 4 (Tokens & Language Modelling) · **The Language-Modelling Objective**: Next-token prediction, cross-entropy, perplexity and what a model learns from it.  → glossary `glossary-src/dl-14.json`
- `deep-learning/chapters/15-decoding.html` · chapter 15 · **core** · Part 4 (Tokens & Language Modelling) · **Decoding Strategies**: Greedy, temperature, top-k, top-p, beam search and constrained decoding.  → glossary `glossary-src/dl-15.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-ch4/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).