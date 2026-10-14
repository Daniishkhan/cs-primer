# Unit: dl-ch6

Course: **A2 Deep Learning & Transformers** (id `dl`, folder `deep-learning/`).

## Course brief
A2 builds deep learning from a neuron to a GPT and modern architectures. Notation: B batch, T sequence length, C or d_model model width, h heads, d_k = d_model/h, V vocabulary; attention softmax(QK^T/sqrt(d_k))V; shapes always written in parentheses (B, T, C). Run NumPy implementations for every mechanism; PyTorch listings may appear labelled 'PyTorch, not run here'. Follow Karpathy's Zero to Hero / nanoGPT spirit (cite them) but write original explanations. Link A0 (autodiff ch 09, optimisers ch 10, numerics ch 11, information theory ch 14) and track-1 systems ch 21 (GPUs).

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `deep-learning/chapters/19-efficient-attention.html` · chapter 19 · **core** · Part 6 (Modern Architectures) · **Efficient Attention**: Multi-query and grouped-query attention, sliding windows and FlashAttention's memory trick.  → glossary `glossary-src/dl-19.json`
- `deep-learning/chapters/20-mixture-of-experts.html` · chapter 20 · **intro** · Part 6 (Modern Architectures) · **Mixture of Experts**: Routing tokens to a few of many experts: more parameters for the same compute, and the catches.  → glossary `glossary-src/dl-20.json`
- `deep-learning/chapters/21-vision-language.html` · chapter 21 · **core** · Part 6 (Modern Architectures) · **Vision-Language Models**: Patches, image encoders, projectors and how a language model learns to read a picture.  → glossary `glossary-src/dl-21.json`
- `deep-learning/chapters/22-beyond-attention.html` · chapter 22 · **intro** · Part 6 (Modern Architectures) · **Beyond Attention**: State-space models, linear attention and hybrids, and what they trade away.  → glossary `glossary-src/dl-22.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/dl-ch6/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).