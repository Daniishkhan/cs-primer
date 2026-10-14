# Unit: dl-studio1

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: design studios

- `deep-learning/studios/studio-01-debug-training.html` (data-studio `S1`, after Part 5) · **Debug a Training Run That Will Not Learn**: Flat loss, then a spike, then NaNs: find the causes in order, with the evidence for each. Related chapters: 03, 17.
- `deep-learning/studios/studio-02-small-model-plan.html` (data-studio `S2`, after Part 6) · **Plan a Small Model on a Budget**: Pick size, tokens, context length and architecture for a domain model with a fixed GPU budget. Related chapters: 16, 18, 19.
- The course toolbox `deep-learning/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `pytorch` (PyTorch), `nanogpt` (nanoGPT, nanochat & minGPT), `tokenisers` (Tokeniser playgrounds), `tensorboard` (TensorBoard & W&B), `profiler` (PyTorch profiler), `colab` (Free GPU notebooks). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).