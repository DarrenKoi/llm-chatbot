# HARNESS

This file is a pre-code harness for any coworker LLM working in this repository.

## Mission

Work on Control MCP and workflow logic only.

- Primary scope: `api/mcp/`
- Primary scope: `api/workflows/`
- Reference authoring scope: `devtools/workflows/`
- Start from workflow entry: `start_chat`

If a task does not clearly belong to Control MCP or workflows, do not change code until the task is reframed.

## First Principle

This repository starts workflow execution from `start_chat`.

- Default workflow entry is `start_chat`
- New routing, handoff, and workflow control should be designed from `api/workflows/start_chat/`
- Assume user requests first enter `start_chat`, then move to another workflow only through explicit workflow control

Do not bypass this entry path with ad hoc shortcuts.

## Folder Control

You are expected to control and edit only the workflow and MCP control surface.

### Allowed Focus Areas

- `api/workflows/`
- `api/workflows/start_chat/`
- `api/workflows/*/graph.py`
- `api/workflows/*/nodes.py`
- `api/workflows/*/state.py`
- `api/workflows/*/routing.py`
- `api/workflows/registry.py`
- `api/workflows/orchestrator.py`
- `api/mcp/`
- `devtools/workflows/`
- `devtools/DEVGUIDE.md`

### Default No-Touch Areas

Do not modify these unless the human explicitly asks for it.

- `api/config.py`
- `api/__init__.py`
- `index.py`
- `wsgi.ini`
- `requirements.txt`
- `.env`
- `.env.example`
- general app bootstrap or deployment setup
- unrelated service packages outside MCP and workflows

## Working Rules

1. Begin by tracing how the request flows through `api/workflows/start_chat/`.
2. Prefer routing, handoff, node, graph, and state changes over global setup changes.
3. Keep edits local to workflow packages, devtools workflow examples, and MCP control modules.
4. When adding a new workflow, register it through the existing workflow discovery contract, not by inventing a parallel system.
5. When handing off from `start_chat`, use the established workflow registry and orchestrator behavior.
6. Preserve existing basic setup unless a human gives explicit approval to change it.

## Match Devtools To API

The workflow authoring experience in `devtools/` should resemble the real runtime in `api/`.

- Use `devtools/workflows/travel_planner_example/` as the reference for a rule-based workflow
- Use `devtools/workflows/translator_example/` as the reference for a workflow that also uses MCP tools
- Keep file splits familiar across both folders: `__init__.py`, `graph.py`, `nodes.py`, `state.py`, with optional helper files such as `tools.py`, `routing.py`, and `prompts.py`
- In `devtools/workflows/`, prefer relative imports inside the workflow package so the code is easy to promote later
- In `api/workflows/`, keep the production entry and handoff path centered on `start_chat`

These example folders exist so coworkers can copy structure and coding style without touching base app setup.

## Devtools Response Rule

When the task is being handled in `devtools/`, say so explicitly in the answer.

- Use clear wording such as `This is done via devtools.`
- Mention the relevant `devtools/...` path when describing the change
- Do not describe devtools work as if it were already wired into production runtime
- If the code is only a devtools prototype or example, label it as devtools work first

## How To Write A Workflow

When creating a new workflow, follow this order.

1. Start from `devtools/workflows/travel_planner_example/` or `devtools/workflows/translator_example/`.
2. Keep the implementation inside the workflow folder first.
3. Define state in `state.py`.
4. Put node behavior in `nodes.py`.
5. Wire the graph in `graph.py`.
6. Add optional helpers only when the workflow actually needs them.
7. After the workflow shape is stable, connect or hand off from `api/workflows/start_chat/`.

If an example workflow uses a helper module such as `tools.py`, keep that pattern instead of flattening everything into one file.

## Decision Boundary

Choose the smallest valid change inside the control folders first.

- Fix in `api/workflows/start_chat/` before touching app-wide code
- Fix in `api/mcp/` before touching unrelated integrations
- Extend workflow nodes and routing before changing bootstrap

## Architecture Reminder

Current expected flow:

`Cube -> queue -> worker -> orchestrator -> start_chat -> handoff/next workflow`

Respect that control chain.

## Output Bias

Prefer code that improves:

- workflow entry handling
- workflow routing
- workflow handoff
- MCP tool control
- state transitions
- control-layer safety and clarity

Avoid work that mainly changes:

- environment setup
- deployment setup
- base application wiring
- unrelated API domains

## If Unsure

Stop and ask whether the task should be handled inside:

- `api/workflows/`
- `api/mcp/`

If not, do not expand scope on your own.
