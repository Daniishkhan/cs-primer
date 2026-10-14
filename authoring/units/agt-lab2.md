# Unit: agt-lab2

Course: **A4 Agents, Tools & Protocols** (id `agt`, folder `agents/`).

## Course brief
A4 teaches agents as engineering: the tool loop, tool design, function calling, MCP and A2A protocols, context engineering and memory, workflow patterns, multi-agent systems, durable execution, deep-research, computer-use and coding agents, agent security, sandboxes, frameworks and AI coding tools. Spine sources: Anthropic engineering posts ('Building effective agents' Dec 2024, 'Effective context engineering for AI agents', 'Writing effective tools for agents', 'How we built our multi-agent research system', 'Claude Code best practices'), OpenAI's 'A practical guide to building agents', the MCP specification (versions 2025-06-18, 2025-11-25; a 2026-07-28 revision removes the initialize handshake/sessions per its release-candidate post: VERIFY the final text at modelcontextprotocol.io before stating details), the A2A project (a2a-protocol.org, Linux Foundation), Simon Willison on the lethal trifecta (June 2025), METR's July 2025 RCT. Message format in examples: the content-block shape used by lab-support/llm.py (text, tool_use, tool_result blocks). Use the ScriptedModel/RuleModel stand-ins for runnable examples. Link track-1: networking ch 10 (HTTP), 12 (APIs), 16 (failure, retries); distributed ch 17 (exactly-once); architecture ch 15 (sagas); security ch 1, 7, 8, 9, 11.

## Your assignment: labs

- Page `agents/labs/lab-03-mcp.html` (data-lab `L3`, after Part 2) with code in `agents/labs/code/lab03/` · **Lab 3: An MCP Server & Client**: JSON-RPC over stdio: initialise, list and call tools, resources and errors, both sides by hand. Related chapters: 07, 08.
  - Design notes: MCP over stdio as JSON-RPC 2.0 messages, one JSON object per line. Implement both server and client in-process via a pipe or subprocess (stdlib subprocess is fine). Follow the 2025-11-25 spec for initialize/initialized, tools/list, tools/call, resources/list, resources/read, error codes, and then a milestone that makes the server also accept the stateless 2026-07-28 style (verify the final spec at modelcontextprotocol.io; if unsure, implement the parts you verified and say which on the page). The check drives the server with raw JSON lines and verifies exact responses.
- Page `agents/labs/lab-04-workflows.html` (data-lab `L4`, after Part 4) with code in `agents/labs/code/lab04/` · **Lab 4: Workflow Patterns & Budgets**: Chains, routers, parallel fan-out and orchestrator-workers, with token accounting for each. Related chapters: 13, 14.

The chapters these labs build on may be written in parallel by other authors; read whatever exists in `agents/chapters/` for notation, otherwise follow the course brief. Labs are standard-library Python only, deterministic, and `python3 check.py solution` must pass in under 60 seconds. If a model is involved, copy `lab-support/llm.py` unchanged into the lab folder as `llm.py`.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/agt-lab2/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).