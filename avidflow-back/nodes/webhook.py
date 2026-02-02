from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameter, NodeParameterType
import json

class WebhookNode(BaseNode):
    """
    Webhook node clearly handles HTTP requests explicitly via trigger.
    """

    type = "webhook"
    version = 1
    is_trigger = True

    description = {
        "displayName": "Webhook",
        "name": "webhook",
        "group": ["trigger"],
        "inputs": [],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }

    properties = {
        "parameters": [
            {
              "name": "test_path",
              "type": "string",
              "display_name": "Test Path",
              "default": "{api_base_address}/webhook/test/execute/webhook/${webhook_id}",
              "readonly": True,
              "description": "The test path for call in editor execution"
            },
            {
              "name": "path",
              "type": "string",
              "display_name": "Path",
              "default": "{api_base_address}/webhook/${webhook_id}/webhook",
              "readonly": True,
              "description": "The path to register the webhook under"
            },
            {
                "name": "httpMethod",
                "type": NodeParameterType.OPTIONS,
                "display_name": "HTTP Method",
                "options": [
                    {"name": "GET", "value": "GET"},
                    {"name": "POST", "value": "POST"},
                ],
                "default": "POST",
                "description": "The HTTP method to listen for"
            }
        ]
    }

    icon = "webhook.svg"
    color = "#885577"

    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        Explicitly handle webhook request data and pass to subsequent nodes.
        """
        try:
            # If there's execution_data on the instance, use it
            if hasattr(self, "execution_data") and self.execution_data:
                input_data = NodeExecutionData(**{'json_data': self.execution_data, 'binary_data': None})
                return [[input_data]]
            
            # Try to get input data from connected nodes (though start nodes typically don't have inputs)
            try:
                input_items = self.get_input_data()
                if input_items and len(input_items) > 0:
                    return [input_items]
            except:
                # No connected input, this is fine for start node
                pass
            
            # If nothing else, return empty data
            empty_data = NodeExecutionData(**{'json_data': {}, 'binary_data': None})
            return [[empty_data]]
            
        except Exception as e:
            import traceback
            error_data = NodeExecutionData(**{
                "json_data": {
                    "error": str(e),
                    "details": traceback.format_exc()
                },
                "binary_data": None
            })
            return [[error_data]]
