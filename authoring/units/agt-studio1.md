# Unit: agt-studio1

Course: **A4 Agents, Tools & Protocols** (id `agt`, folder `agents/`).

## Course brief
A4 teaches agents as engineering: the tool loop, tool design, function calling, MCP and A2A protocols, context engineering and memory, workflow patterns, multi-agent systems, durable execution, deep-research, computer-use and coding agents, agent security, sandboxes, frameworks and AI coding tools. Spine sources: Anthropic engineering posts ('Building effective agents' Dec 2024, 'Effective context engineering for AI agents', 'Writing effective tools for agents', 'How we built our multi-agent research system', 'Claude Code best practices'), OpenAI's 'A practical guide to building agents', the MCP specification (versions 2025-06-18, 2025-11-25; a 2026-07-28 revision removes the initialize handshake/sessions per its release-candidate post: VERIFY the final text at modelcontextprotocol.io before stating details), the A2A project (a2a-protocol.org, Linux Foundation), Simon Willison on the lethal trifecta (June 2025), METR's July 2025 RCT. Message format in examples: the content-block shape used by lab-support/llm.py (text, tool_use, tool_result blocks). Use the ScriptedModel/RuleModel stand-ins for runnable examples. Link track-1: networking ch 10 (HTTP), 12 (APIs), 16 (failure, retries); distributed ch 17 (exactly-once); architecture ch 15 (sagas); security ch 1, 7, 8, 9, 11.

## Your assignment: design studios

- `agents/studios/studio-01-support-agent.html` (data-studio `S1`, after Part 4) · **Design a Customer-Support Agent**: Answers, account lookups and refunds with limits, escalation to humans and an audit trail. Related chapters: 13, 15, 05.
- `agents/studios/studio-02-research-product.html` (data-studio `S2`, after Part 5) · **Design a Deep-Research Product**: Long-running research jobs with citations, cost controls, progress updates and quality checks. Related chapters: 14, 16.
- `agents/studios/studio-03-regulated-agent.html` (data-studio `S3`, after Part 6) · **Design an Agent for a Regulated Back Office**: Documents in, decisions out, with a threat model, approvals and evidence an auditor accepts. Related chapters: 19, 20, 15.
- The course toolbox `agents/toolbox.html` (data-page toolbox) with one tool card per catalog tool, ids: `coding-agents` (Claude Code, Codex CLI & Cursor), `mcp-inspector` (MCP Inspector), `sdks` (Provider SDKs & agent SDKs), `llm-cli` (The llm command-line tool), `playwright` (Playwright), `containers` (Docker sandboxes). See guide section 11.

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/agt-studio1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).