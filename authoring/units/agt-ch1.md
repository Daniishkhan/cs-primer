# Unit: agt-ch1

Course: **A4 Agents, Tools & Protocols** (id `agt`, folder `agents/`).

## Course brief
A4 teaches agents as engineering: the tool loop, tool design, function calling, MCP and A2A protocols, context engineering and memory, workflow patterns, multi-agent systems, durable execution, deep-research, computer-use and coding agents, agent security, sandboxes, frameworks and AI coding tools. Spine sources: Anthropic engineering posts ('Building effective agents' Dec 2024, 'Effective context engineering for AI agents', 'Writing effective tools for agents', 'How we built our multi-agent research system', 'Claude Code best practices'), OpenAI's 'A practical guide to building agents', the MCP specification (versions 2025-06-18, 2025-11-25; a 2026-07-28 revision removes the initialize handshake/sessions per its release-candidate post: VERIFY the final text at modelcontextprotocol.io before stating details), the A2A project (a2a-protocol.org, Linux Foundation), Simon Willison on the lethal trifecta (June 2025), METR's July 2025 RCT. Message format in examples: the content-block shape used by lab-support/llm.py (text, tool_use, tool_result blocks). Use the ScriptedModel/RuleModel stand-ins for runnable examples. Link track-1: networking ch 10 (HTTP), 12 (APIs), 16 (failure, retries); distributed ch 17 (exactly-once); architecture ch 15 (sagas); security ch 1, 7, 8, 9, 11.

## Your assignment: chapters
Write these chapter pages, with glossary files:

- `agents/chapters/00-start-here.html` · chapter 00 · **intro** · Part 0 (Orientation) · **Start Here**: Workflows versus agents, why agents fail, and the shape of this course.  → glossary `glossary-src/agt-00.json`
- `agents/chapters/01-model-apis.html` · chapter 01 · **core** · Part 1 (The Loop) · **Talking to a Model**: Messages and roles, system prompts, parameters, streaming and structured output.  → glossary `glossary-src/agt-01.json`
- `agents/chapters/02-tool-loop.html` · chapter 02 · **deep** · Part 1 (The Loop) · **Tool Calling: The Agent Loop**: Tool definitions, tool_use and tool_result turns, stop conditions and iteration budgets.  → glossary `glossary-src/agt-02.json`
- `agents/chapters/03-reasoning-planning.html` · chapter 03 · **core** · Part 1 (The Loop) · **Reasoning, ReAct & Planning**: Thought-action-observation, plan-then-execute, reflection and what reasoning models change.  → glossary `glossary-src/agt-03.json`
- `agents/chapters/04-prompting.html` · chapter 04 · **core** · Part 1 (The Loop) · **Prompting as Programming**: Clear instructions, examples, delimiters and prompts you can test, version and review.  → glossary `glossary-src/agt-04.json`

The full chapter list of this course is in `authoring/link-index.md`; stay within your chapters' scope and link to the neighbours that cover the rest. Chapter 00 (Start Here), when assigned, introduces the course: what it covers and why, the parts, how it connects to the other courses (A0 to A8 and Zero to Systems), how to study it (depth tags, labs, offline checks), and a small taste of the core idea with one diagram; for A0 it also introduces the whole Zero to AI Systems path and the AI systems engineer role broadly (not tied to one employer).

For each deep chapter add at least one stepper or small interactive widget (guide section 6).

## Process
1. Read `authoring/guide.md` in full, then the sample pages it lists for your page type. Skim `authoring/link-index.md` for this course and the courses it builds on, so your links and scope fit the neighbouring pages.
2. Research what you need (WebSearch/WebFetch), especially anything dated, numeric or from 2024 onwards. Use `$TMPDIR/agt-ch1/` for scripts (create it; other authors share `$TMPDIR`).
3. Write the pages. Run every code example and paste real output. Draw diagrams carefully (no overlapping text).
4. Run `python3 authoring/check_page.py <your files>` and fix all ERRORs and reasonable WARNs.
5. Report back in under 200 words (see guide section 14). Work only on the files listed here (plus glossary-src files, widget files named with your course id plus chapter id, and lab code folders you own).