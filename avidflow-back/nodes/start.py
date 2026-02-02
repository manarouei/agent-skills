from typing import Dict, Any, List
from models import NodeExecutionData
from .base import BaseNode


class StartNode(BaseNode):
    """
    Start Node - Simple passthrough node that marks the beginning of a workflow.
    It outputs whatever input it receives with no modifications and no configuration options.
    """
    
    type = "n8n-nodes-base.start"
    version = 1
    
    description = {
        "displayName": "Start",
        "name": "start",
        "group": ["trigger"],
        "version": 1,
        "description": "Marks the beginning of a workflow",
        "defaults": {
            "name": "Start",
            "color": "#00FF00"
        },
        "inputs": [],  # No inputs as this is a starting point
        "outputs": [
            {
                "name": "main",
                "type": "main",
                "required": True
            }
        ]
    }
    
    # No parameters - completely simplified
    properties = {
        "parameters": []  # Empty parameters list
    }
    
    icon = "fa:play-circle"
    color = "#00FF00"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Simply pass through the input data or provide empty data if this is the workflow start
        """
        try:
            # Check if we have input data from workflow execution
            input_data = None
            
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