from typing import Dict, List, Any, Optional, Union
from models import NodeExecutionData
from .base import BaseNode, NodeParameter, NodeParameterType, NodeRunMode
import json
import copy
import logging
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class SwitchNode(BaseNode):
    """
    Switch node that routes data to different outputs based on simple rules.
    Each rule has one condition and routes to one output.
    """
    
    type = "switch"
    version = 1
    
    description = {
        "displayName": "Switch",
        "name": "switch", 
        "group": ["transform"],
        "inputs": [
            {"name": "main", "type": "main", "required": True},
        ],
        "outputs": "dynamic",  # Dynamic outputs based on rules
    }
    
    properties = {
        "parameters": [
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "حالت",
                "description": "How data should be routed",
                "options": [
                    {
                        "name": "قوانین",
                        "value": "rules",
                        "description": "Build a simple condition for each output"
                    }
                ],
                "default": "rules",
                "no_data_expression": True
            },
            {
                "name": "rules",
                "type": NodeParameterType.ARRAY,
                "display_name": "قوانین مسیریابی",
                "placeholder": "افزودن قانون مسیریابی",
                "default": [
                    {
                        "leftValue": "",
                        "operator": "equals",
                        "rightValue": "",
                        "dataType": "string",
                        "outputName": ""
                    }
                ],
                "description": "Define one condition for each output",
                "display_options": {
                    "show": {
                        "mode": ["rules"]
                    }
                },
                "options": [
                    {
                        "name": "leftValue",
                        "type": NodeParameterType.STRING,
                        "display_name": "مقدار چپ",
                        "default": "",
                        "placeholder": "{{ $json.field }}",
                        "description": "Value to compare (can use expressions)"
                    },
                    {
                        "name": "dataType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "نوع داده",
                        "options": [
                            {"name": "رشته", "value": "string"},
                            {"name": "عدد", "value": "number"},
                            {"name": "بولی", "value": "boolean"},
                            {"name": "تاریخ", "value": "dateTime"}
                        ],
                        "default": "string",
                        "description": "Type of data to compare"
                    },
                    {
                        "name": "operator",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "عملگر",
                        "options": [
                            {"name": "برابر", "value": "equals"},
                            {"name": "مخالف", "value": "notEquals"},
                            {"name": "شامل", "value": "contains"},
                            {"name": "شامل نمی‌شود", "value": "notContains"},
                            {"name": "شروع می‌شود با", "value": "startsWith"},
                            {"name": "پایان می‌یابد با", "value": "endsWith"},
                            {"name": "بزرگتر از", "value": "gt"},
                            {"name": "بزرگتر مساوی", "value": "gte"},
                            {"name": "کمتر از", "value": "lt"},
                            {"name": "کمتر مساوی", "value": "lte"},
                            {"name": "خالی است", "value": "isEmpty"},
                            {"name": "خالی نیست", "value": "isNotEmpty"},
                            {"name": "regex", "value": "regex"}
                        ],
                        "default": "equals",
                        "description": "Comparison operator"
                    },
                    {
                        "name": "rightValue",
                        "type": NodeParameterType.STRING,
                        "display_name": "مقدار راست",
                        "default": "",
                        "placeholder": "value to compare",
                        "description": "Value to compare against",
                        "display_options": {
                            "hide": {
                                "operator": ["isEmpty", "isNotEmpty"]
                            }
                        }
                    },
                    {
                        "name": "outputName",
                        "type": NodeParameterType.STRING,
                        "display_name": "نام خروجی",
                        "default": "",
                        "placeholder": "e.g. Active Users",
                        "description": "Custom name for this output (optional)"
                    }
                ]
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "تنظیمات",
                "placeholder": "افزودن تنظیم",
                "default": {},
                "description": "Additional routing options",
                "options": [
                    {
                        "name": "fallbackOutput",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "خروجی پیش‌فرض",
                        "default": True,
                        "description": "Add an extra output for items that don't match any rule"
                    },
                    {
                        "name": "fallbackOutputName",
                        "type": NodeParameterType.STRING,
                        "display_name": "نام خروجی پیش‌فرض",
                        "placeholder": "e.g. Others",
                        "default": "سایر",
                        "description": "Name for the fallback output",
                        "display_options": {
                            "show": {
                                "fallbackOutput": [True]
                            }
                        }
                    },
                    {
                        "name": "ignoreCase",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "نادیده گرفتن حروف کوچک/بزرگ",
                        "default": True,
                        "description": "Whether to ignore letter case when comparing strings"
                    },
                    {
                        "name": "sendToFirstMatch",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "ارسال به اولین تطبیق",
                        "default": True,
                        "description": "Send data to the first matching rule only (not all matches)"
                    }
                ]
            }
        ]
    }
    
    icon = "fa:code-branch"
    color = "#506000"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Switch node logic to route data based on simple rules"""
        try:
            logger.info("Switch Node - Starting execution")
            
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("Switch Node - No input data")
                return [[]]
            
            # Get parameters
            rules = self.get_parameter("rules", 0, [])
            options = self.get_parameter("options", 0, {})
            ignore_case = options.get("ignoreCase", True)
            send_to_first_match = options.get("sendToFirstMatch", True)
            
            if not rules:
                logger.warning("Switch Node - No rules defined")
                return [[]]
            
            # Initialize return data based on rules
            return_data: List[List[NodeExecutionData]] = []
            
            # Create outputs for each rule
            for _ in rules:
                return_data.append([])
            
            # Process each input item
            for item_index, item in enumerate(input_data):
                try:
                    item_copy = copy.deepcopy(item)
                    match_found = False
                    
                    #logger.info(f"[Switch] Processing item {item_index}, json_data keys: {list(item.json_data.keys())}")
                    
                    # Check each rule
                    for rule_index, rule in enumerate(rules):
                        try:
                            output_name = rule.get("outputName", f"Rule {rule_index}")
                            #logger.info(f"[Switch] Evaluating rule {rule_index} ('{output_name}')")
                            
                            # Evaluate single rule condition
                            condition_pass = self._evaluate_rule_condition(
                                rule, 
                                item_index,
                                ignore_case
                            )
                            
                            #logger.info(f"[Switch] Rule {rule_index} result: {condition_pass}")
                            
                            if condition_pass:
                                match_found = True
                                return_data[rule_index].append(item_copy)
                                #logger.info(f"[Switch] ✅ Item routed to output {rule_index} ('{output_name}')")
                                
                                # If sending to first match only, stop here
                                if send_to_first_match:
                                    #logger.info(f"[Switch] Stopping at first match (sendToFirstMatch=True)")
                                    break
                                    
                        except Exception as e:
                            logger.error(f"Switch Node - Error evaluating rule {rule_index}: {str(e)}")
                            continue
                    
                    if not match_found:
                        logger.warning(f"[Switch] ⚠️ No rules matched for item {item_index}")
                            
                except Exception as e:
                    logger.error(f"Switch Node - Error processing item {item_index}: {str(e)}")
                    continue
            
            return return_data
            
        except Exception as e:
            logger.error(f"Switch Node - Execution error: {str(e)}")
            return [[]]
    
    def _evaluate_rule_condition(
        self, 
        rule: Dict[str, Any], 
        item_index: int,
        ignore_case: bool
    ) -> bool:
        """Evaluate a single rule condition"""
        try:
            # Get rule parameters
            operator = rule.get("operator", "equals")
            data_type = rule.get("dataType", "string")
            left_expr = rule.get("leftValue", "")
            right_expr = rule.get("rightValue", "")
            
            # Evaluate expressions directly from item data
            input_data = self.get_input_data()
            if not input_data or item_index >= len(input_data):
                return False
            
            item = input_data[item_index]
            
            # Resolve left value
            left_value = self._resolve_expression(left_expr, item)
            # Resolve right value  
            right_value = self._resolve_expression(right_expr, item)

            # logger.info(f"[Switch] Rule evaluation:")
            # logger.info(f"  leftValue expression: {left_expr}")
            # logger.info(f"  leftValue resolved: {left_value} (type: {type(left_value).__name__})")
            # logger.info(f"  operator: {operator}")
            # logger.info(f"  rightValue expression: {right_expr}")
            # logger.info(f"  rightValue resolved: {right_value} (type: {type(right_value).__name__})")
            # logger.info(f"  dataType: {data_type}")

            # Convert values based on data type
            left_val = self._convert_value(left_value, data_type)
            right_val = self._convert_value(right_value, data_type)

            # logger.info(f"  After conversion:")
            # logger.info(f"    left_val: {left_val} (type: {type(left_val).__name__})")
            # logger.info(f"    right_val: {right_val} (type: {type(right_val).__name__})")

            # Apply case sensitivity for string operations
            if data_type == "string" and ignore_case:
                if isinstance(left_val, str):
                    left_val = left_val.lower()
                if isinstance(right_val, str):
                    right_val = right_val.lower()
            
            # Perform comparison based on operation
            result = self._compare_values(left_val, right_val, operator, data_type)
            logger.info(f"  Comparison result: {result}")
            
            return result
            
        except Exception as e:
            logger.error(f"Switch Node - Error in rule condition evaluation: {str(e)}")
            return False
    
    def _resolve_expression(self, expr: str, item: NodeExecutionData) -> Any:
        """
        Resolve expression like ={{ $json.field }} to actual value from item
        
        Args:
            expr: Expression string (e.g., "={{ $json.answerable }}")
            item: NodeExecutionData item containing json_data
            
        Returns:
            Resolved value from item's json_data
        """
        if not isinstance(expr, str):
            return expr
            
        # Check if it's an expression (starts with =)
        if expr.startswith("="):
            expr_content = expr[1:].strip()
            
            # Handle {{ }} wrapped expressions
            if expr_content.startswith("{{") and expr_content.endswith("}}"):
                expr_content = expr_content[2:-2].strip()
            
            # Handle $json.field access
            if expr_content.startswith("$json."):
                field_name = expr_content[6:]  # Remove "$json."
                
                # Access nested fields (e.g., $json.flags.off_topic)
                value = item.json_data
                for part in field_name.split('.'):
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return None
                return value
            
            # For other expressions, try to evaluate safely
            # This is a simplified evaluator - expand as needed
            return expr_content
            
        # Not an expression, return as-is
        return expr
    
    def _convert_value(self, value: Any, value_type: str) -> Any:
        """Convert value to appropriate type"""
        try:
            if value_type == "number":
                if isinstance(value, (int, float)):
                    return value
                elif isinstance(value, str):
                    try:
                        return float(value) if '.' in value else int(value)
                    except ValueError:
                        return 0
                else:
                    return 0
                    
            elif value_type == "boolean":
                if isinstance(value, bool):
                    return value
                elif isinstance(value, str):
                    return value.lower() in ('true', '1', 'yes', 'on')
                else:
                    return bool(value)
                    
            elif value_type == "dateTime":
                if isinstance(value, datetime):
                    return value
                elif isinstance(value, str):
                    try:
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    except ValueError:
                        return datetime.now()
                else:
                    return datetime.now()
                    
            else:  # string
                return str(value) if value is not None else ""
                
        except Exception as e:
            logger.error(f"Switch Node - Error converting value: {str(e)}")
            return value
    
    def _compare_values(
        self, 
        left_val: Any, 
        right_val: Any, 
        operation: str, 
        value_type: str
    ) -> bool:
        """Compare two values based on operation"""
        try:
            if operation == "equals":
                return left_val == right_val
                
            elif operation == "notEquals":
                return left_val != right_val
                
            elif operation == "contains":
                if isinstance(left_val, str) and isinstance(right_val, str):
                    return right_val in left_val
                return False
                
            elif operation == "notContains":
                if isinstance(left_val, str) and isinstance(right_val, str):
                    return right_val not in left_val
                return False
                
            elif operation == "startsWith":
                if isinstance(left_val, str) and isinstance(right_val, str):
                    return left_val.startswith(right_val)
                return False
                
            elif operation == "endsWith":
                if isinstance(left_val, str) and isinstance(right_val, str):
                    return left_val.endswith(right_val)
                return False
                
            elif operation == "gt":
                try:
                    return left_val > right_val
                except TypeError:
                    return False
                    
            elif operation == "gte":
                try:
                    return left_val >= right_val
                except TypeError:
                    return False
                    
            elif operation == "lt":
                try:
                    return left_val < right_val
                except TypeError:
                    return False
                    
            elif operation == "lte":
                try:
                    return left_val <= right_val
                except TypeError:
                    return False
                    
            elif operation == "isEmpty":
                if left_val is None:
                    return True
                elif isinstance(left_val, (str, list, dict)):
                    return len(left_val) == 0
                return False
                
            elif operation == "isNotEmpty":
                if left_val is None:
                    return False
                elif isinstance(left_val, (str, list, dict)):
                    return len(left_val) > 0
                return True
                
            elif operation == "regex":
                if isinstance(left_val, str) and isinstance(right_val, str):
                    try:
                        pattern = re.compile(right_val)
                        return bool(pattern.search(left_val))
                    except re.error:
                        return False
                return False
                
            else:
                logger.warning(f"Switch Node - Unknown operation: {operation}")
                return False
                
        except Exception as e:
            logger.error(f"Switch Node - Error comparing values: {str(e)}")
            return False
    
    def get_dynamic_outputs(self) -> List[Dict[str, Any]]:
        """Get dynamic output configuration based on rules"""
        try:
            rules = self.get_parameter("rules", 0, [])
            options = self.get_parameter("options", 0, {})
            fallback_output = options.get("fallbackOutput", True)
            fallback_name = options.get("fallbackOutputName", "سایر")
            
            outputs = []
            
            # Create outputs for each rule
            for index, rule in enumerate(rules):
                output_name = rule.get("outputName", "").strip()
                if not output_name:
                    output_name = f"خروجی {index + 1}"
                
                outputs.append({
                    "type": "main",
                    "displayName": output_name,
                    "name": f"output{index}"
                })
            
            # Add fallback output if enabled
            if fallback_output:
                outputs.append({
                    "type": "main", 
                    "displayName": fallback_name,
                    "name": "fallback"
                })
            
            return outputs
            
        except Exception as e:
            logger.error(f"Switch Node - Error getting dynamic outputs: {str(e)}")
            return [{"type": "main", "displayName": "خروجی 1", "name": "output0"}]