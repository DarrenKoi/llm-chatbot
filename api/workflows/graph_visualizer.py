"""워크플로 LangGraph 그래프를 Mermaid 소스로 렌더링하는 HTML을 생성한다."""

from html import escape

from api.workflows.registry import get_workflow
from api.workflows.registry import list_workflow_ids as list_registered_workflow_ids

_MERMAID_FRONTMATTER = {
    "config": {
        "theme": "neutral",
        "look": "classic",
        "themeVariables": {
            "primaryColor": "#f4f1e8",
            "primaryTextColor": "#17271f",
            "primaryBorderColor": "#5f7a70",
            "lineColor": "#5f7a70",
            "secondaryColor": "#e8f1ef",
            "tertiaryColor": "#fffdf7",
        },
    }
}

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Workflow: {workflow_id}</title>
    <style>
      :root {{
        color-scheme: light;
        --bg: linear-gradient(180deg, #f7f5ef 0%, #eef4f6 100%);
        --surface: rgba(255, 255, 255, 0.94);
        --surface-strong: #fffdf7;
        --border: rgba(23, 39, 31, 0.14);
        --text: #17271f;
        --muted: #506067;
        --accent: #295f5a;
        --accent-soft: #e6f0ee;
        --shadow: 0 20px 48px rgba(23, 39, 31, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        padding: 0;
        background: var(--bg);
        color: var(--text);
        font-family: "Segoe UI", sans-serif;
      }}

      .workflow-shell {{
        width: min(88vw, 1480px);
        margin: 28px auto 40px;
      }}

      .workflow-header {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 16px;
      }}

      .workflow-header h1 {{
        margin: 0;
        font-size: 28px;
        font-weight: 700;
      }}

      .workflow-header p {{
        margin: 6px 0 0;
        color: var(--muted);
        font-size: 14px;
      }}

      .copy-button {{
        border: 1px solid var(--border);
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font: inherit;
        font-size: 13px;
        font-weight: 600;
        padding: 10px 16px;
        cursor: pointer;
      }}

      .copy-button:hover {{
        background: #d8e8e4;
      }}

      .workflow-card {{
        padding: 18px;
        border-radius: 22px;
        background: var(--surface);
        box-shadow: var(--shadow);
      }}

      .workflow-card h2 {{
        margin: 0 0 10px;
        font-size: 16px;
      }}

      .workflow-card p {{
        margin: 0 0 14px;
        color: var(--muted);
        font-size: 14px;
      }}

      .workflow-source {{
        margin: 0;
        padding: 18px;
        overflow-x: auto;
        border: 1px solid var(--border);
        border-radius: 18px;
        background: var(--surface-strong);
        font-family: "SFMono-Regular", "SF Mono", Consolas, "Liberation Mono", Menlo, monospace;
        font-size: 13px;
        line-height: 1.6;
        white-space: pre;
      }}

      @media (max-width: 960px) {{
        .workflow-shell {{
          width: calc(100vw - 24px);
          margin: 12px auto 24px;
        }}

        .workflow-header {{
          flex-direction: column;
          align-items: stretch;
        }}

        .workflow-card {{
          padding: 12px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="workflow-shell">
      <section class="workflow-header">
        <div>
          <h1>Workflow: {workflow_id}</h1>
          <p>
            LangGraph built-in Mermaid export입니다. 필요하면 그대로 복사해서 Mermaid 호환 도구에
            붙여 넣을 수 있습니다.
          </p>
        </div>
        <button class="copy-button" type="button" data-copy-target="workflow-mermaid">Copy Mermaid</button>
      </section>
      <section class="workflow-card">
        <h2>Mermaid Source</h2>
        <p>Python 시각화 라이브러리 없이 LangGraph 그래프 정의를 직접 확인하는 용도입니다.</p>
        <pre id="workflow-mermaid" class="workflow-source"><code>{mermaid_source}</code></pre>
      </section>
    </main>
    <script>
      const copyButton = document.querySelector("[data-copy-target]");
      if (copyButton && navigator.clipboard) {{
        copyButton.addEventListener("click", async () => {{
          const target = document.getElementById(copyButton.dataset.copyTarget);
          if (!target) return;
          await navigator.clipboard.writeText(target.textContent || "");
          copyButton.textContent = "Copied";
          window.setTimeout(() => {{
            copyButton.textContent = "Copy Mermaid";
          }}, 1200);
        }});
      }}
    </script>
  </body>
</html>
"""


def build_workflow_html(workflow_id: str) -> str:
    """주어진 workflow_id의 LangGraph Mermaid HTML 문자열을 반환한다."""

    workflow_def = get_workflow(workflow_id)
    builder = workflow_def["build_lg_graph"]
    lg_graph = builder().compile().get_graph()
    mermaid_source = lg_graph.draw_mermaid(frontmatter_config=_MERMAID_FRONTMATTER)
    return _PAGE_TEMPLATE.format(
        workflow_id=escape(workflow_id),
        mermaid_source=escape(mermaid_source),
    )


def list_workflow_ids() -> list[str]:
    """등록된 모든 workflow_id 목록을 반환한다."""

    return list_registered_workflow_ids()
