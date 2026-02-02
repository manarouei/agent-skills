from typing import Dict, Any, List, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import logging

logger = logging.getLogger(__name__)


class StickyNoteNode(BaseNode):
    """
    Sticky Note node for adding comments and notes to workflows.
    This node doesn't process data but serves as a visual comment/documentation element.
    It passes through input data unchanged, similar to the n8n StickyNote node.
    """

    type = "stickyNote"
    version = 1

    description = {
        "displayName": "Sticky Note",
        "name": "stickyNote",
        "icon": "fa:sticky-note",
        "group": ["input"],
        "version": 1,
        "description": "Make your workflow easier to understand",
        "defaults": {
            "name": "Sticky Note",
            "color": "#FFD233"
        },
        "inputs": [],  # No inputs as this is primarily a visual/documentation node
        "outputs": [],  # No outputs as this is primarily a visual/documentation node
        "usableAsTool": False,
    }

    properties = {
        "parameters": [
            {
                "name": "content",
                "type": NodeParameterType.STRING,
                "display_name": "Content",
                "default": "## I'm a note \n**Double click** to edit me. [Guide](https://docs.n8n.io/workflows/sticky-notes/)",
                "description": "The content of the sticky note",
            },
            {
                "name": "height",
                "type": NodeParameterType.NUMBER,
                "display_name": "Height",
                "default": 160,
                "required": True,
                "description": "Height of the sticky note in pixels",
            },
            {
                "name": "width",
                "type": NodeParameterType.NUMBER,
                "display_name": "Width",
                "default": 240,
                "required": True,
                "description": "Width of the sticky note in pixels",
            },
            {
                "name": "color",
                "type": NodeParameterType.NUMBER,
                "display_name": "Color",
                "default": 1,
                "required": True,
                "description": "Color theme for the sticky note (1-6 representing different color schemes)",
            },
        ],
        "credentials": [],  # No credentials required for sticky notes
    }

    icon = "fa:sticky-note"
    color = "#FFD233"  # Yellow color to match n8n default
    subtitle = "Add notes to your workflow"

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the sticky note node.
        Since sticky notes are primarily visual/documentation elements,
        they pass through input data unchanged or return empty data if no input.
        """
        # try:
        # Get input data if available
        input_data = self.get_input_data()
        
        if input_data:
            # If there's input data, pass it through unchanged
            # This maintains the data flow while allowing the node to serve as documentation
            logger.debug(f"StickyNote '{self.node_data.name}' passing through {len(input_data)} items")
            return [[]]
        else:
            # If no input data, return empty list (sticky notes can exist without data flow)
            logger.debug(f"StickyNote '{self.node_data.name}' has no input data")
            return [[]]

        # except Exception as e:
        #     logger.error(f"Error in StickyNote node '{self.node_data.name}': {str(e)}")
            
        #     # Return empty data on error to avoid breaking the workflow
        #     # Sticky notes shouldn't cause workflow failures
        #     error_data = NodeExecutionData(
        #         json_data={
        #             "error": f"StickyNote error: {str(e)}",
        #             "node_type": "stickyNote",
        #             "node_name": getattr(self.node_data, 'name', 'Unknown')
        #         },
        #         binary_data=None
        #     )
        #     return [[error_data]]

    def get_content(self, item_index: int = 0) -> str:
        """Get the content of the sticky note"""
        return self.get_node_parameter("content", item_index, 
                                     "## I'm a note \n**Double click** to edit me.")

    def get_height(self, item_index: int = 0) -> int:
        """Get the height of the sticky note"""
        return int(self.get_node_parameter("height", item_index, 160))

    def get_width(self, item_index: int = 0) -> int:
        """Get the width of the sticky note"""
        return int(self.get_node_parameter("width", item_index, 240))

    def get_color(self, item_index: int = 0) -> int:
        """Get the color theme of the sticky note"""
        return int(self.get_node_parameter("color", item_index, 1))

    def get_sticky_note_config(self, item_index: int = 0) -> Dict[str, Any]:
        """
        Get the complete configuration for the sticky note as a dictionary.
        This can be used by UI components to render the sticky note.
        """
        return {
            "content": self.get_content(item_index),
            "height": self.get_height(item_index),
            "width": self.get_width(item_index),
            "color": self.get_color(item_index),
            "node_name": getattr(self.node_data, 'name', 'Sticky Note'),
            "node_id": getattr(self.node_data, 'id', None),
        }