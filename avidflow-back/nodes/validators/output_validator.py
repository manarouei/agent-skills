"""
Output validator node for AI agent responses.

Validates and formats AI agent outputs with multiple modes:
- Intent: Parse and validate intent classification JSON
- Citation: Validate non-empty responses with fallback messages
- Custom: User-defined validation rules
"""
from typing import Dict, List, Any
import logging
import json

from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class OutputValidatorNode(BaseNode):
    """
    Validate and format AI agent outputs.
    
    This node handles post-processing of AI agent responses, ensuring they
    conform to expected formats and providing fallback behavior for edge cases.
    
    Supports three validation modes:
    1. Intent: Parse JSON intent classification with structured field extraction
    2. Citation: Ensure non-empty responses, use fallback message if empty
    3. Custom: Extensible validation for future use cases
    """
    
    type = "outputValidator"
    version = 1
    
    description = {
        "displayName": "Output Validator",
        "name": "outputValidator",
        "icon": "fa:check-circle",
        "group": ["transform"],
        "description": "Validate and format AI agent outputs",
        "defaults": {"name": "Output Validator"},
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}]
    }
    
    properties = {
        "parameters": [
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Validation Mode",
                "options": [
                    {
                        "name": "Parse Intent JSON",
                        "value": "intent",
                        "description": "Parse and validate intent classification output"
                    },
                    {
                        "name": "Validate Citation",
                        "value": "citation",
                        "description": "Ensure response is not empty, use fallback if needed"
                    },
                    {
                        "name": "Custom Validation",
                        "value": "custom",
                        "description": "Custom validation rules"
                    }
                ],
                "default": "intent",
                "no_data_expression": True
            },
            {
                "name": "inputField",
                "type": NodeParameterType.STRING,
                "display_name": "Input Field",
                "default": "output",
                "description": "Field containing AI agent output"
            },
            {
                "name": "requiredFields",
                "type": NodeParameterType.JSON,
                "display_name": "Required Fields",
                "default": '["answerable", "domain", "flags"]',
                "description": "JSON array of required fields in parsed output",
                "display_options": {
                    "show": {
                        "mode": ["intent"]
                    }
                }
            },
            {
                "name": "defaultResponse",
                "type": NodeParameterType.STRING,
                "display_name": "Default Response",
                "default": "پاسخی دریافت نشد. لطفاً دوباره بپرسید.",
                "description": "Fallback message for empty outputs",
                "display_options": {
                    "show": {
                        "mode": ["citation"]
                    }
                }
            },
            {
                "name": "preserveOriginalData",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Preserve Original Data",
                "default": True,
                "description": "Keep all fields from input data"
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute output validation"""
        try:
            input_data = self.get_input_data()
            
            # Handle empty input data case
            if not input_data:
                return [[]]
            
            results = []
            
            for i, item in enumerate(input_data):
                try:
                    mode = self.get_node_parameter("mode", i, "intent")
                    input_field = self.get_node_parameter("inputField", i, "output")
                    preserve = self.get_node_parameter("preserveOriginalData", i, True)
                    
                    output_data = item.json_data.copy() if preserve else {}
                    raw_output = item.json_data.get(input_field, "")
                    
                    if mode == "intent":
                        validated = self._validate_intent(raw_output, i)
                        output_data.update(validated)
                        
                    elif mode == "citation":
                        validated = self._validate_citation(raw_output, i)
                        output_data.update(validated)
                        
                    elif mode == "custom":
                        # Custom validation logic can be added here
                        output_data["validated"] = True
                        logger.debug(f"[OutputValidator] Item {i}: Custom validation passed")
                    
                    results.append(NodeExecutionData(json_data=output_data))
                    
                except Exception as e:
                    logger.error(f"[OutputValidator] Error validating item {i}: {e}", exc_info=True)
                    # Return error info
                    results.append(NodeExecutionData(
                        json_data={
                            "error": True,
                            "message": str(e),
                            "original": item.json_data
                        }
                    ))
            
            logger.info(f"[OutputValidator] Validated {len(results)} items")
            return [results]  # Single output
            
        except Exception as e:
            logger.error(f"[OutputValidator] Execute error: {e}", exc_info=True)
            return [[]]
    
    def _validate_intent(self, raw_output: str, item_index: int) -> Dict[str, Any]:
        """
        Parse and validate intent classification JSON.
        
        Expected format:
        {
          "answerable": true/false,
          "domain": "string",
          "flags": {"ambiguous": bool, "off_topic": bool}
        }
        
        Args:
            raw_output: Raw JSON string from AI agent
            item_index: Index of item being processed
            
        Returns:
            Normalized intent dict with extracted fields
        """
        required_fields_json = self.get_node_parameter("requiredFields", item_index, '[]')
        try:
            required_fields = json.loads(required_fields_json)
        except Exception as e:
            logger.warning(f"[OutputValidator] Invalid requiredFields JSON: {e}")
            required_fields = ["answerable", "domain", "flags"]
        
        # Try to parse JSON
        try:
            # Handle cases where AI returns wrapped JSON or markdown code blocks
            text = str(raw_output).strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
            intent = json.loads(text)
            
        except json.JSONDecodeError as e:
            logger.error(
                f"[OutputValidator] Failed to parse intent JSON: {raw_output[:100]}... "
                f"Error: {e}"
            )
            return {
                "error": True,
                "message": "Intent JSON invalid",
                "raw": raw_output
            }
        
        # Validate required fields
        missing_fields = [f for f in required_fields if f not in intent]
        if missing_fields:
            logger.warning(f"[OutputValidator] Missing required fields: {missing_fields}")
        
        # Extract and normalize fields
        result = {
            "answerable": bool(intent.get("answerable", False)),
            "domain": str(intent.get("domain", "other")),
            "off_topic": bool(intent.get("flags", {}).get("off_topic", False)),
            "ambiguous": bool(intent.get("flags", {}).get("ambiguous", False))
        }
        
        logger.info(
            f"[OutputValidator] Parsed intent: answerable={result['answerable']}, "
            f"domain={result['domain']}, off_topic={result['off_topic']}, "
            f"ambiguous={result['ambiguous']}"
        )
        
        return result
    
    def _validate_citation(self, raw_output: str, item_index: int) -> Dict[str, Any]:
        """
        Validate citation/response output is not empty.
        
        If output is empty or whitespace-only, returns default fallback message.
        
        Args:
            raw_output: Response text from AI agent
            item_index: Index of item being processed
            
        Returns:
            Dict with 'text' field containing validated or default response
        """
        default_msg = self.get_node_parameter(
            "defaultResponse",
            item_index,
            "پاسخی دریافت نشد. لطفاً دوباره بپرسید."
        )
        
        # Clean and check output
        text = str(raw_output).strip()
        
        if not text:
            logger.warning("[OutputValidator] Empty output, using default response")
            return {
                "text": default_msg,
                "isEmpty": True
            }
        
        logger.info(f"[OutputValidator] Valid citation output ({len(text)} chars)")
        return {
            "text": text,
            "isEmpty": False
        }
