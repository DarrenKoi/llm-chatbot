"""Cube richnotification block composition test workflow.

The package name keeps the requested `richinotification_test` spelling.
It is devtools-only and is meant for previewing/sending text + datatable
blocks before promoting any production workflow behavior.
"""


def build_lg_graph():
    """richinotification_test LangGraph builder."""

    from .lg_graph import build_lg_graph as builder

    return builder()


def get_workflow_definition() -> dict[str, object]:
    """Return the devtools workflow definition."""

    return {
        "workflow_id": "richinotification_test",
        "build_lg_graph": build_lg_graph,
        "handoff_keywords": (),
    }
