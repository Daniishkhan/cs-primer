# Unit: dl-lab1

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: labs

- Page `deep-learning/labs/lab-01-mlp.html` (data-lab `L1`, after Part 1) with code in `deep-learning/labs/code/lab01/` · **Lab 1: A Neural Network from Scratch**: Matrix ops, a two-layer network, backprop by hand and a training loop on a toy dataset. Related chapters: 01, 02, 03.
  - Design notes: Keep sizes tiny (two-moons or XOR-style toy data generated with a seed, hidden width ~8 to 16) so it trains in seconds in pure Python.
- Page `deep-learning/labs/lab-02-embeddings.html` (data-lab `L2`, after Part 2) with code in `deep-learning/labs/code/lab02/` · **Lab 2: Word Embeddings**: Skip-gram with negative sampling on a small corpus, then nearest neighbours and analogies. Related chapters: 06.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `deep-learning/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-lab1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).