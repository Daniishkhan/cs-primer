# Unit: llm-studio1

Course: **A3 Training, Post-training & Serving LLMs** (id `llm`, folder `llm-training/`).

## Course brief
A3 is the life of a large language model as an engineer meets it: pretraining data and systems, RL foundations, post-training (SFT, LoRA/QLoRA, RLHF, DPO, reward models, RLVR/GRPO, distillation), cheap adaptation (model merging, evolutionary merging, Transformer-squared style self-adaptation, Text-to-LoRA hypernetworks), inference (KV cache, quantisation, serving engines, speculative decoding, token economics) and evaluating trained models. Use A2's notation (B, T, C, V). Derive key objectives fully (REINFORCE, PPO clip, DPO from the KL-regularised reward objective, GRPO's group-relative advantage). Every number about GPUs (HBM, FLOPs) should cite a vendor spec or be labelled an assumption; give 'what fits on one 24 GB GPU' style worked examples. Volatile facts (which models, which library versions) go in dated boxes. TRL v1 (March 2026) and Stanford CS336 are good current references; verify claims you use.

## Your assignment: design studios

- `llm-training/studios/studio-01-domain-adaptation.html` (data-studio `S1`, after Part 3) · **Adapt a Model for a Specialist Domain**: Prompting, retrieval, fine-tuning or all three, under a fixed budget, with the evaluation that decides. Related chapters: 10, 11, 23.
- `llm-training/studios/studio-02-reasoning-model.html` (data-studio `S2`, after Part 3) · **Post-train a Small Reasoning Model**: Pick the base model, reward, data and compute, and plan how you will catch reward hacking. Related chapters: 14, 15.
- `llm-training/studios/studio-03-serving-platform.html` (data-studio `S3`, after Part 5) · **Design an LLM Serving Platform**: Many models, many tenants, latency targets and a GPU bill: batching, routing, caching and autoscaling. Related chapters: 18, 20, 22.
- The course toolbox `llm-training/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `hf` (Hugging Face transformers, TRL & PEFT), `unsloth` (Unsloth), `vllm` (vLLM & SGLang), `llamacpp` (llama.cpp & Ollama), `lm-eval` (lm-evaluation-harness), `nvidia-smi` (nvidia-smi & nvtop). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/llm-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).