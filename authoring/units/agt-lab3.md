# Unit: agt-lab3

Course: **A4 Agents, Tools & Protocols** (id `agt`, folder `agents/`).

## Course brief
A4 teaches agents as engineering: the tool loop, tool design, function calling, MCP and A2A protocols, context engineering and memory, workflow patterns, multi-agent systems, durable execution, deep-research, computer-use and coding agents, agent security, sandboxes, frameworks and AI coding tools. Spine sources: Anthropic engineering posts ('Building effective agents' Dec 2024, 'Effective context engineering for AI agents', 'Writing effective tools for agents', 'How we built our multi-agent research system', 'Claude Code best practices'), OpenAI's 'A practical guide to building agents', the MCP specification (versions 2025-06-18, 2025-11-25; a 2026-07-28 revision removes the initialize handshake/sessions per its release-candidate post: VERIFY the final text at modelcontextprotocol.io before stating details), the A2A project (a2a-protocol.org, Linux Foundation), Simon Willison on the lethal trifecta (June 2025), METR's July 2025 RCT. Message format in examples: the content-block shape used by lab-support/llm.py (text, tool_use, tool_result blocks). Use the ScriptedModel/RuleModel stand-ins for runnable examples. Link track-1: networking ch 10 (HTTP), 12 (APIs), 16 (failure, retries); distributed ch 17 (exactly-once); architecture ch 15 (sagas); security ch 1, 7, 8, 9, 11.

## Your assignment: labs

- Page `agents/labs/lab-05-durable-agent.html` (data-lab `L5`, after Part 4) with code in `agents/labs/code/lab05/` · **Lab 5: A Durable Agent**: An event-sourced agent that survives being killed mid-task without repeating side effects. Related chapters: 15, dist:17.
  - Design notes: Event-sourced agent: an append-only JSONL event log; the check kills the agent (raises an exception or stops at a random step via a seeded crash injector) and restarts it, verifying that external side effects (a fake payments/email API recording calls) happen exactly once thanks to idempotency keys, that completed tool results are replayed from the log not re-executed, and that a human-approval gate pauses and resumes.
- Page `agents/labs/lab-06-deep-research.html` (data-lab `L6`, after Part 5) with code in `agents/labs/code/lab06/` · **Lab 6: A Mini Deep-Research Agent**: Plan, search a local corpus, read, cite and verify every claim against its source. Related chapters: 16, 10.
  - Design notes: Local corpus fixture of ~30 short documents with some contradictions and one outdated source; the stand-in model is a RuleModel/ScriptedModel that plans sub-questions and 'writes' claims with citations; the learner implements planning, parallel search (BM25-lite provided or simple), reading, a claim-to-source citation checker (quoted span must appear in the cited document), and a report assembler that drops unsupported claims.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `agents/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/agt-lab3/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).