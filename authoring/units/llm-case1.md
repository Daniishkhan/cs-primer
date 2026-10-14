# Unit: llm-case1

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: case studies

- `llm-training/cases/case-01-instructgpt.html` (data-case `C1`) · **InstructGPT: RLHF in Practice** · pattern: Learning from human preferences · A smaller model that labellers preferred to one a hundred times larger. Related: 10, 12.
- `llm-training/cases/case-02-deepseek-r1.html` (data-case `C2`) · **DeepSeek-R1** · pattern: RL with verifiable rewards · Reasoning that emerged from reinforcement learning on checkable problems, then distilled into small models. Related: 14, 15.
- `llm-training/cases/case-03-llama3-training.html` (data-case `C3`) · **Training Llama 3 at Scale** · pattern: Reliability of training clusters · Thousands of GPUs, hundreds of interruptions and the engineering that kept the run on track. Related: 03, 05.
- `llm-training/cases/case-04-vllm.html` (data-case `C4`) · **vLLM and PagedAttention** · pattern: Virtual memory for the KV cache · Borrowing operating-system paging to stop wasting most of a GPU's cache memory. Related: 18, 20, sys:06.

Read the primary sources first (guide section 9). If a case's premise turns out to be wrong or unverifiable after research, write the best accurate version and flag it in your report.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-case1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).