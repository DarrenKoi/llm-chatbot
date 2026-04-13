"""워크플로 LangGraph 그래프를 pyvis 네트워크로 변환하여 HTML을 생성한다."""

import re

from pyvis.network import Network

from api.workflows.registry import get_workflow
from api.workflows.registry import list_workflow_ids as list_registered_workflow_ids

_NODE_COLOR = "#4A90D9"
_ENTRY_COLOR = "#2ECC71"
_END_COLOR = "#E74C3C"
_EDGE_COLOR = "#7f8c8d"
_CONDITIONAL_EDGE_COLOR = "#e67e22"

_BODY_GRAPH_PATTERN = re.compile(
    r"<body>\s*<div class=\"card\" style=\"width: 100%\">\s*"
    r"<div id=\"mynetwork\" class=\"card-body\"></div>\s*</div>",
    re.S,
)
_LAYOUT_CSS = """
             body {
                 margin: 0;
                 padding: 0;
                 background: linear-gradient(180deg, #f7f5ef 0%, #eef4f6 100%);
                 color: #17271f;
                 font-family: "Segoe UI", sans-serif;
             }

             .workflow-shell {
                 width: min(80vw, 1500px);
                 margin: 28px auto 40px;
             }

             .workflow-header {
                 margin-bottom: 16px;
             }

             .workflow-header h1 {
                 margin: 0;
                 font-size: 28px;
                 font-weight: 700;
             }

             .workflow-header p {
                 margin: 6px 0 0;
                 color: #506067;
                 font-size: 14px;
             }

             .workflow-card {
                 width: 100% !important;
                 padding: 18px;
                 border: 0;
                 border-radius: 22px;
                 background: rgba(255, 255, 255, 0.92);
                 box-shadow: 0 20px 48px rgba(23, 39, 31, 0.12);
             }

             .workflow-card .card-body {
                 padding: 0;
             }

             #mynetwork {
                 width: 100% !important;
                 height: min(78vh, 920px) !important;
                 min-height: 720px;
                 background-color: #fffdf7 !important;
                 border: 1px solid rgba(23, 39, 31, 0.12) !important;
                 border-radius: 18px;
                 position: relative;
                 float: none !important;
             }

             @media (max-width: 960px) {
                 .workflow-shell {
                     width: calc(100vw - 24px);
                     margin: 12px auto 24px;
                 }

                 .workflow-card {
                     padding: 12px;
                 }

                 #mynetwork {
                     height: 70vh !important;
                     min-height: 520px;
                 }
             }
"""

_LG_START = "__start__"
_LG_END = "__end__"


def build_workflow_html(workflow_id: str) -> str:
    """주어진 workflow_id의 LangGraph 그래프를 pyvis HTML 문자열로 반환한다."""

    workflow_def = get_workflow(workflow_id)
    builder = workflow_def["build_lg_graph"]
    lg_graph = builder().compile().get_graph()

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

    entry_targets: set[str] = set()
    for edge in lg_graph.edges:
        if edge.source == _LG_START:
            entry_targets.add(edge.target)

    for node_id in lg_graph.nodes:
        if node_id in (_LG_START, _LG_END):
            continue
        if node_id in entry_targets:
            color = _ENTRY_COLOR
        else:
            color = _NODE_COLOR
        net.add_node(node_id, label=node_id, color=color)

    net.add_node(_LG_END, label="END", color=_END_COLOR)

    for edge in lg_graph.edges:
        if edge.source == _LG_START:
            continue
        target = _LG_END if edge.target == _LG_END else edge.target
        edge_color = _CONDITIONAL_EDGE_COLOR if edge.conditional else _EDGE_COLOR
        net.add_edge(edge.source, target, color=edge_color)

    return _apply_workflow_layout(html=net.generate_html(), workflow_id=workflow_id)


def list_workflow_ids() -> list[str]:
    """등록된 모든 workflow_id 목록을 반환한다."""

    return list_registered_workflow_ids()


def _apply_workflow_layout(*, html: str, workflow_id: str) -> str:
    html = html.replace("</style>", f"{_LAYOUT_CSS}\n        </style>", 1)
    return _BODY_GRAPH_PATTERN.sub(
        (
            "<body>"
            '<div class="workflow-shell">'
            f'<div class="workflow-header"><h1>Workflow: {workflow_id}</h1>'
            "<p>그래프를 넓혀서 노드와 흐름을 한눈에 볼 수 있도록 조정했습니다.</p></div>"
            '<div class="card workflow-card" style="width: 100%">'
            '<div id="mynetwork" class="card-body"></div>'
            "</div></div>"
        ),
        html,
        count=1,
    )
