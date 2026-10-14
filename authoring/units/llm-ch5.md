# Unit: llm-ch5

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `llm-training/chapters/15-distillation.html` · chapter 15 · **core** · Part 3 (Post-training) · **Distillation & Synthetic Data**: Teaching small models with big ones, logit distillation, synthetic data and model collapse.  → glossary `glossary-src/llm-15.json`
- `llm-training/chapters/16-model-merging.html` · chapter 16 · **core** · Part 4 (Cheap Adaptation) · **Model Merging & Evolutionary Merging**: Averaging weights, task vectors, TIES and DARE, and searching for merge recipes by evolution.  → glossary `glossary-src/llm-16.json`
- `llm-training/chapters/17-adapters-on-demand.html` · chapter 17 · **intro** · Part 4 (Cheap Adaptation) · **Adapters on Demand**: Self-adaptive models and hypernetworks that generate adapters from a task description.  → glossary `glossary-src/llm-17.json`
- `llm-training/chapters/18-kv-cache.html` · chapter 18 · **deep** · Part 5 (Inference) · **The KV Cache & the Cost of Decoding**: Prefill versus decode, why generation is memory-bound, and what the cache costs.  → glossary `glossary-src/llm-18.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-ch5/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).