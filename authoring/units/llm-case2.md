# Unit: llm-case2

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: case studies

- `llm-training/cases/case-05-evolutionary-merge.html` (data-case `C5`) · **Evolving Model Merges** · pattern: Search over recipes · Evolutionary search that combined existing open models into new capabilities without gradient training. Related: 16.
- `llm-training/cases/case-06-sycophancy-rollback.html` (data-case `C6`) · **The Sycophancy Rollback** · pattern: Reward signals with side effects · A model update that became too eager to please, and what its developer said went wrong. Related: 13.
- `llm-training/cases/case-07-alpaca.html` (data-case `C7`) · **Alpaca & Self-Instruct** · pattern: Distillation from a stronger model · Fifty-two thousand generated instructions, a few hundred dollars and a lesson about imitation. Related: 15, 10.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-case2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).