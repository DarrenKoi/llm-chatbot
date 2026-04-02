"""워크플로 그래프를 pyvis 네트워크로 변환하여 HTML을 생성한다."""

from pyvis.network import Network

from api.workflows.registry import get_workflow

_NODE_COLOR = "#4A90D9"
_ENTRY_COLOR = "#2ECC71"
_END_COLOR = "#E74C3C"
_EDGE_COLOR = "#7f8c8d"

_HANDOFF_NODE_ID = "__handoff__"
_HANDOFF_LABEL = "handoff"


def build_workflow_html(workflow_id: str) -> str:
    """주어진 workflow_id의 그래프를 pyvis HTML 문자열로 반환한다."""

    workflow_def = get_workflow(workflow_id)
    graph = workflow_def["build_graph"]()

    net = Network(
        height="600px",
        width="100%",
        directed=True,
        bgcolor="#faf9f6",
        font_color="#17271f",
    )
    net.set_options("""{
        "layout": {
            "hierarchical": {
                "enabled": true,
                "direction": "UD",
                "sortMethod": "directed",
                "nodeSpacing": 180,
                "levelSeparation": 120
            }
        },
        "physics": { "enabled": false },
        "edges": {
            "arrows": { "to": { "enabled": true } },
            "smooth": { "type": "cubicBezier" },
            "font": { "size": 12, "align": "middle" }
        },
        "nodes": {
            "shape": "box",
            "font": { "size": 14 },
            "borderWidth": 2,
            "shadow": true
        }
    }""")

    entry_node_id = graph.get("entry_node_id")
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])

    has_handoff = any(edge[1] is None for edge in edges)

    for node_id in nodes:
        if node_id == entry_node_id:
            color = _ENTRY_COLOR
        else:
            color = _NODE_COLOR
        net.add_node(node_id, label=node_id, color=color)

    if has_handoff:
        net.add_node(_HANDOFF_NODE_ID, label=_HANDOFF_LABEL, color=_END_COLOR)

    for edge in edges:
        source = edge[0]
        target = edge[1] if edge[1] is not None else _HANDOFF_NODE_ID
        label = edge[2] if len(edge) > 2 else ""
        net.add_edge(source, target, label=label, color=_EDGE_COLOR)

    return net.generate_html()


def list_workflow_ids() -> list[str]:
    """등록된 모든 workflow_id 목록을 반환한다."""

    from api.workflows.registry import _WORKFLOWS

    return sorted(_WORKFLOWS.keys())
