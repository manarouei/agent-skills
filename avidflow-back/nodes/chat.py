from nodes.base import BaseNode
from models import NodeExecutionData
from uuid import uuid4

class ChatNode(BaseNode):
    """
    A node that represents a chat interaction.
    """

    type = "chat"
    version = "1.0"

    description = {
        "displayName": "Chat",
        "name": "chat",
        "description": "Represents a chat interaction",
        "inputs": [],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }

    properties = {
        "parameters": [
            {
                "name": "Chat url",
                "type": "string",
                "required": True,
                "default": "{chat_url_in_frontend}",
                "readonly": True,
                "description": "The URL of the chat endpoint"
            },
            {
                "name": "initial message",
                "type": "string",
                "required": True,
                "default": "Welcome to Avid assistant. How can I help you today?",
                "description": "The initial message to send in the chat"
            }
        ]
    }

    def trigger(self):
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