# Unit: dl-ch2

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `deep-learning/chapters/04-deep-regularisation.html` · chapter 04 · **core** · Part 1 (Neural Networks) · **Regularising Deep Networks**: Weight decay, dropout, data augmentation, early stopping and the strange case of double descent.  → glossary `glossary-src/dl-04.json`
- `deep-learning/chapters/05-pytorch.html` · chapter 05 · **core** · Part 1 (Neural Networks) · **PyTorch as an Autodiff Engine**: Tensors, autograd, modules, optimisers and the standard training loop.  → glossary `glossary-src/dl-05.json`
- `deep-learning/chapters/06-embeddings.html` · chapter 06 · **deep** · Part 2 (Representation) · **Embeddings: Words as Vectors**: One-hot to dense vectors, word2vec, and why meaning becomes geometry.  → glossary `glossary-src/dl-06.json`
- `deep-learning/chapters/07-convolutions.html` · chapter 07 · **core** · Part 2 (Representation) · **Convolutions & Images**: Filters, weight sharing, pooling and the ideas from vision that carried over.  → glossary `glossary-src/dl-07.json`
- `deep-learning/chapters/08-sequences-rnns.html` · chapter 08 · **core** · Part 2 (Representation) · **Sequences & Recurrent Networks**: RNNs and LSTMs, the bottleneck of a single hidden state, and why they gave way to attention.  → glossary `glossary-src/dl-08.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-ch2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).