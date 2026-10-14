# Unit: llm-lab2

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: labs

- Page `llm-training/labs/lab-03-lora.html` (data-lab `L3`, after Part 3) with code in `llm-training/labs/code/lab03/` · **Lab 3: LoRA from Scratch**: Freeze a small model, train low-rank adapters, merge them back and compare parameter counts. Related chapters: 11.
  - Design notes: No real LLM: freeze a small 'pretrained' pure-Python linear or two-layer model provided in starter (weights generated with a seed and pre-fit on task A), then fine-tune on task B with rank-r adapters A,B (B initialised to zero), alpha/r scaling, merge, and compare trainable parameter counts and task A forgetting versus full fine-tuning.
- Page `llm-training/labs/lab-04-dpo-grpo.html` (data-lab `L4`, after Part 3) with code in `llm-training/labs/code/lab04/` · **Lab 4: DPO & GRPO on a Toy Policy**: Implement both losses on a policy over answers to arithmetic questions with a verifiable reward. Related chapters: 12, 14.
  - Design notes: The policy is a softmax over a fixed set of candidate answers per arithmetic question (logits are the parameters), with a reference policy for the KL term. DPO uses preference pairs; GRPO samples groups of answers, scores with a verifiable reward (exact numeric match), normalises advantages within each group, and applies a clipped objective with a KL penalty. Deterministic with seeds.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `llm-training/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).