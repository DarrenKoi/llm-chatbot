import json
import os
import uuid

import config


def execute(chart_type: str, title: str, data: dict) -> str:
    """Stub: generates a chart PNG via Matplotlib and returns its URL."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return json.dumps({"error": "matplotlib not installed"})

    os.makedirs(config.CHART_IMAGE_DIR, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.png"
    filepath = os.path.join(config.CHART_IMAGE_DIR, filename)

    labels = data.get("labels", ["A", "B", "C"])
    values = data.get("values", [1, 2, 3])

    fig, ax = plt.subplots()
    if chart_type == "bar":
        ax.bar(labels, values)
    elif chart_type == "line":
        ax.plot(labels, values)
    elif chart_type == "pie":
        ax.pie(values, labels=labels, autopct="%1.1f%%")
    ax.set_title(title)
    fig.savefig(filepath)
    plt.close(fig)

    image_url = f"{config.CHART_IMAGE_BASE_URL}/{filename}"
    return json.dumps({"image_url": image_url, "filepath": filepath})
