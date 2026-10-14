# Unit: dl-lab2

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: labs

- Page `deep-learning/labs/lab-03-attention.html` (data-lab `L3`, after Part 3) with code in `deep-learning/labs/code/lab03/` · **Lab 3: Attention & a Transformer Block**: Scaled dot-product attention, causal masks, multi-head attention and a block, checked shape by shape. Related chapters: 09, 10, 11.
- Page `deep-learning/labs/lab-04-tiny-gpt.html` (data-lab `L4`, after Part 3) with code in `deep-learning/labs/code/lab04/` · **Lab 4: Train a Tiny GPT**: A character-level GPT in pure Python, trained until it invents plausible names. Related chapters: 12, 14.
  - Design notes: Must train in pure Python within about 60 seconds on a laptop for the check: use a scalar or tiny list-based autograd, vocabulary of ~27 characters, embedding width 8 to 16, one or two heads, one layer, context 8, a few hundred steps on a small built-in names list. Karpathy's microgpt (a pure-Python GPT, 2026) is prior art: read it if you can find it and credit it, but write your own code. The check verifies shapes, gradient correctness against finite differences on a tiny config, loss decreasing below a threshold with a fixed seed, and sampling determinism.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `deep-learning/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).