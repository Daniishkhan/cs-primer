# Unit: wb-retarget

Re-target the surviving workbench pages from "your laptop" to **the lab VM**, because the reader no longer runs anything on their own computer.

## Your assignment
The pages whose catalog `machine` is now `vm` (see `authoring/link-index.md`, Workbench lists): `deep-learning/workbench/w01-pytorch.html`, `w02-char-gpt.html`, `w03-tiktoken.html`, `w05-word-vectors.html`; `agents/workbench/w01-local-model-agent.html`, `agents/workbench/w02-real-embedders.html`; `evals/workbench/w01-real-judge.html`; `open-ended/workbench/w01-funsearch-local.html`. Pages whose machine is `gpu` (`deep-learning/workbench/w04-attention-kernels.html`, `llm-training/workbench/w02` to `w05`, `open-ended/workbench/w02-funsearch-gpu.html`) only need their wording checked: no "laptop" or "MPS" sentences, and the GPU marked as rented later.

For each `vm` page:
1. Copy its `code/wNN/` folder to the lab VM and run the script(s) there with the page's documented flags. Ollama-based pages: `ollama pull` the model the page names first.
2. Replace every output block with the VM's real output, titled `output (lab VM, 16 vCPU, …)`. Update every number in the prose that cited the old output ("What you should see", measurement-table predictions only if the prediction itself depended on the machine). Never keep a laptop number next to VM text.
3. Rewrite the "What you need" callout and any sentence about a laptop, Apple MPS or "your machine" for the lab VM (`lab-machine.html` describes it). Scripts: drop the MPS branch in device selection (CUDA, then CPU), keeping behaviour otherwise identical; re-generate the notebook with `python3 authoring/py2ipynb.py`; re-sync any script listing embedded in the page with the edited script.
4. If a run fails on the VM, fix the cause (missing package: install it with `uv pip install --python ~/lab/bin/python …` and add it to `workbench/requirements.txt`), not the output.

## Process
1. Read `authoring/guide.md` in full (section 17, the artifact track, is new), then the sample pages it lists for your page type. Read `RSI Artifact-First Roadmap.md` at the site root: it is the reason these pages exist. Skim `authoring/link-index.md` for this course and the courses it builds on; take every cross-link path from it.
2. Research before writing. Everything dated after mid-2025 must be fetched from the primary source (WebFetch/WebSearch): the arXiv abstract page, the repository README, the official post. Record what you fetched. If a source cannot be fetched, say so in the page (a `callout note` "What I could and could not read" in cases; a sentence in chapters) and keep the claim out of the main text. Never invent numbers, quotes, dates or URLs. Several links in the roadmap may be wrong or point at mirrors: check each one. Use `$TMPDIR/wb-retarget/` for scratch work.
3. Write the pages. Every code example's output is real output from running it (chapter and lab code is standard-library Python, NumPy at most, run locally with `python3`). Workbench scripts run **only on the lab VM** (below), never on this Mac.
4. Run `python3 authoring/check_page.py <your files>` and `node authoring/check_tex.js <pages with maths>`; fix every ERROR and the reasonable WARNs (sentence length, unexpanded acronyms, missing analogy).
5. Do not edit `assets/js/catalog.js`, shared JS/CSS, or files outside your assignment. Do not run git commands that change state. Remove any `__pycache__` you create.
6. Report back in under 200 words: files written, approximate words, what you fetched and what you could not verify, any catalog change you recommend.

## The lab VM (workbench authors only)
SSH: `ssh -i ~/.ssh/zero_to_ai_vm_ed25519 ubuntu@32.199.227.194` (run outside the sandbox). Ubuntu 24.04, 16 vCPU, 64 GB, Python 3.12 venv at `~/lab` (activated by `~/.bashrc`: PyTorch CPU, transformers, datasets, tokenizers, tiktoken, scikit-learn, matplotlib, jupyterlab), Ollama installed, `uv` at `~/.local/bin/uv` for anything else. Work in `~/work/wb-retarget/`. Copy code with `scp`/`rsync`. An OpenAI key for tests is on the VM: `source ~/.config/lab.env` sets `OPENAI_API_KEY`. Never print it, copy it off the VM, or write it into any file in the repo. Prefer `gpt-5.4-mini` or `gpt-5.4-nano` to keep cost down. Label output blocks `output (lab VM, 16 vCPU, …)`. A CloudWatch alarm stops the VM after an hour under 5% CPU; if SSH fails, say so in your report rather than starting it yourself.
