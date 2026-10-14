# Unit: llm-lab3

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: labs

- Page `llm-training/labs/lab-05-evolutionary-merge.html` (data-lab `L5`, after Part 4) with code in `llm-training/labs/code/lab05/` · **Lab 5: Evolutionary Model Merging**: Merge task-specialised small models and evolve merge coefficients against a held-out task. Related chapters: 16.
  - Design notes: Use small pure-Python models (e.g. tiny MLPs or linear models) fine-tuned from a shared base on different tasks; implement weight averaging, task arithmetic, TIES-style trimming/sign election, and a simple evolutionary search (e.g. (1+λ) or CMA-lite) over per-layer merge coefficients scored on a search split, reporting a held-out split.
- Page `llm-training/labs/lab-06-serving-sim.html` (data-lab `L6`, after Part 5) with code in `llm-training/labs/code/lab06/` · **Lab 6: A Serving Simulator**: Simulate static and continuous batching with a paged KV cache, and measure throughput and latency. Related chapters: 18, 20, 22.
  - Design notes: Discrete-event simulation: requests with prompt/output lengths from a seeded distribution; a GPU with a KV-cache budget in tokens split into fixed-size pages; static batching versus continuous batching with paged allocation; report throughput, time-to-first-token and per-token latency percentiles; preemption when the cache is full.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `llm-training/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-lab3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).