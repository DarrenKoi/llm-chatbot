import json

from tools.query_data import execute as query_data_execute
from tools.create_chart import execute as create_chart_execute

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": "Query internal database or Elasticsearch for business data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language or structured query",
                    },
                    "source": {
                        "type": "string",
                        "enum": ["database", "elasticsearch"],
                        "description": "Data source to query",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_chart",
            "description": "Create a chart image from provided data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {
                        "type": "string",
                        "enum": ["bar", "line", "pie"],
                        "description": "Type of chart",
                    },
                    "title": {
                        "type": "string",
                        "description": "Chart title",
                    },
                    "data": {
                        "type": "object",
                        "description": "Chart data with 'labels' and 'values' arrays",
                    },
                },
                "required": ["chart_type", "title", "data"],
            },
        },
    },
]

TOOL_EXECUTORS = {
    "query_data": query_data_execute,
    "create_chart": create_chart_execute,
}


def execute_tool(name: str, arguments: dict) -> str:
    executor = TOOL_EXECUTORS.get(name)
    if not executor:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return executor(**arguments)
