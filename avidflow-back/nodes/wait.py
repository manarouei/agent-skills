import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class WaitNode(BaseNode):
    """
    Wait Node that pauses workflow execution for a specified duration or until a specific time.
    Supports different wait modes: fixed time, amount of time, and webhook resumption.
    """

    type = "wait"
    version = 1

    description = {
        "displayName": "Wait",
        "name": "wait",
        "group": ["organization"],
        "version": 1,
        "description": "Waits before continuing with the next node",
        "defaults": {
            "name": "Wait",
            "color": "#804080"
        },
        "inputs": ["main"],
        "outputs": ["main"],
        "icon": "fa:stopwatch"
    }

    properties = {
        "parameters": [
            {
                "name": "amount",
                "type": NodeParameterType.NUMBER,
                "display_name": "Amount",
                "description": "The amount of time to wait in second(s)",
                "default": 1,
                "min": 1,
                "max": 60,
                "required": True
            },
        ]
    }

    icon = "fa:stopwatch"
    color = "#804080"

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the Wait node logic.
        Handles different wait modes: time interval, specific time, and webhook.
        """
            
            # Get input data
        input_data = self.get_input_data()
        
        if not input_data or input_data == [[]]:
            return [[]]
        amount = self.get_node_parameter("amount", 0, 0)
        time.sleep(amount)

        return [input_data]