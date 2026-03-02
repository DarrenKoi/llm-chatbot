import json


def execute(query: str, source: str = "database") -> str:
    """Stub: returns mock query results."""
    mock_result = {
        "source": source,
        "query": query,
        "results": [
            {"name": "Product A", "sales": 1200},
            {"name": "Product B", "sales": 850},
            {"name": "Product C", "sales": 2100},
        ],
        "note": "This is mock data from a stub implementation.",
    }
    return json.dumps(mock_result, ensure_ascii=False)
