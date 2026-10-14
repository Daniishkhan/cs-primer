# Unit: dl-case1

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: case studies

- `deep-learning/cases/case-01-alexnet.html` (data-case `C1`) · **AlexNet and ImageNet, 2012** · pattern: Data + compute + method · Two GPUs, a big labelled dataset and ReLUs: the result that restarted neural networks. Related: 07, 04.
- `deep-learning/cases/case-02-transformer.html` (data-case `C2`) · **Attention Is All You Need** · pattern: Parallel sequence models · The 2017 translation paper whose architecture now runs nearly every frontier model. Related: 09, 10.
- `deep-learning/cases/case-03-gpt-scaling.html` (data-case `C3`) · **From GPT-2 to GPT-3** · pattern: Scale changes behaviour · A language model that learned tasks nobody trained it for, and the in-context learning surprise. Related: 14, 18.
- `deep-learning/cases/case-04-chinchilla.html` (data-case `C4`) · **Chinchilla: Compute-Optimal Training** · pattern: Balance data and size · Why a smaller model trained on more tokens beat a model four times its size. Related: 16, 18.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).