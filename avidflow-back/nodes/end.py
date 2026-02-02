from typing import Dict, Any, List
from models import NodeExecutionData
from .base import BaseNode


class EndNode(BaseNode):
    """
    End Node - Simple passthrough node that marks the end of a workflow.
    It outputs whatever input it receives with no modifications and no configuration options.
    """
    
    type = "n8n-nodes-base.end"
    version = 1
    
    description = {
        "displayName": "End",
        "name": "end",
        "group": ["output"],
        "version": 1,
        "description": "Marks the end of a workflow execution path",
        "defaults": {
            "name": "End",
            "color": "#FF3300"  # Red color to visually distinguish from start node
        },
        "inputs": [
            {
                "name": "main",
                "type": "main",
                "required": True,
                "maxConnections": 2
            }
        ],
        "outputs": []  # No outputs as this is an end point
    }
    
    # No parameters - completely simplified
    properties = {
        "parameters": []  # Empty parameters list
    }
    
    icon = "fa:stop-circle"
    color = "#FF3300"  # Red color
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Simply pass through the input data as the final result of the workflow
        """
        try:
            # Get input data from connected nodes
            input_items = self.get_input_data()
            
            if not input_items:
                return [[]]
                
            # Return the input data as the final workflow result
            return [input_items]
            
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