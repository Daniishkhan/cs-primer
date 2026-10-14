# Unit: llm-lab1

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: labs

- Page `llm-training/labs/lab-01-data-pipeline.html` (data-lab `L1`, after Part 1) with code in `llm-training/labs/code/lab01/` · **Lab 1: A Pretraining Data Pipeline**: Extract, filter by quality heuristics and deduplicate with MinHash and locality-sensitive hashing. Related chapters: 01.
  - Design notes: Corpus: a small built-in set of synthetic 'web pages' (with boilerplate, near-duplicates, spam, short pages, non-English) as Python strings or a JSON fixture. Implement text extraction from simple HTML, Gopher/C4-style quality heuristics, exact-hash dedupe, MinHash signatures and LSH banding, and report the precision/recall of near-duplicate detection against labelled pairs.
- Page `llm-training/labs/lab-02-policy-gradient.html` (data-lab `L2`, after Part 2) with code in `llm-training/labs/code/lab02/` · **Lab 2: Policy Gradients & PPO**: REINFORCE with a baseline, then PPO's clipped objective with a KL penalty, on bandits and a gridworld. Related chapters: 06, 07, 08.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `llm-training/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-lab1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).