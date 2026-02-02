from typing import Dict, List, Any, Union, Callable
from models import NodeExecutionData
from .base import BaseNode, NodeParameter, NodeParameterType, NodeRunMode
import operator
import re
import copy
import logging
from datetime import datetime
import json

class IfNode(BaseNode):
    """
    IF node that implements conditional logic operations to filter workflow items.
    """
    
    type = "if"
    version = 1.0
    
    description = {
        "displayName": "IF",
        "name": "if",
        "group": ["transform"],
        "inputs": [
            {"name": "main", "type": "main", "required": True},
        ],
        "outputs": [
            {"name": "true", "type": "main", "required": True, "description": "Items that match condition"},
            {"name": "false", "type": "main", "required": True, "description": "Items that don't match condition"}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "conditions",
                "type": NodeParameterType.ARRAY,  # Using ARRAY instead of FIXED_COLLECTION
                "display_name": "Conditions",
                "default": [],
                "options": [
                    {
                        "name": "dataType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "نوع داده",
                        "options": [
                            {"name": "بولی", "value": "boolean"},
                            {"name": "عدد", "value": "number"},
                            {"name": "رشته", "value": "string"},
                            {"name": "تاریخ و زمان", "value": "dateTime"}
                        ],
                        "default": "string"
                    },
                    {
                        "name": "value1",
                        "type": NodeParameterType.STRING,
                        "display_name": "مقدار اول",
                        "default": ""
                    },
                    {
                        "name": "operation",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Operation",
                        "options": [
                            {"name": "Equal", "value": "equal"},
                            {"name": "Not Equal", "value": "notEqual"},
                            {"name": "Larger", "value": "larger"},
                            {"name": "Larger Equal", "value": "largerEqual"},
                            {"name": "Smaller", "value": "smaller"},
                            {"name": "Smaller Equal", "value": "smallerEqual"},
                            {"name": "Contains", "value": "contains"},
                            {"name": "Not Contains", "value": "notContains"},
                            {"name": "Starts With", "value": "startsWith"},
                            {"name": "Not Starts With", "value": "notStartsWith"},
                            {"name": "Ends With", "value": "endsWith"},
                            {"name": "Not Ends With", "value": "notEndsWith"},
                            {"name": "Regex", "value": "regex"},
                            {"name": "Not Regex", "value": "notRegex"},
                            {"name": "Is Empty", "value": "isEmpty"},
                            {"name": "Is Not Empty", "value": "isNotEmpty"},
                            {"name": "After", "value": "after"},
                            {"name": "Before", "value": "before"}
                        ],
                        "default": "equal"
                    },
                    {
                      "name": "value2",
                      "type": "string",
                      "display_name": "مقدار دوم",
                      "default": "",
                      "displayOptions": {
                        "hide": {
                            "operation": [
                              "isEmpty",
                              "isNotEmpty"
                            ]
                        }
                    }
                    }
                ]
            },
            {
                "name": "combineOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Combine",
                "description": "How to combine multiple conditions",
                "options": [
                    {
                        "name": "و",
                        "value": "all",
                        "description": "Only if all conditions are met it goes into 'true' branch"
                    },
                    {
                        "name": "یا",
                        "value": "any",
                        "description": "If any of the conditions is met it goes into 'true' branch"
                    }
                ],
                "default": "all"
            }
        ]
    }
    
    icon = "fa:map-signs"
    color = "#408000"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute IF node logic to filter items based on conditions"""
        try:


            input_items = self.get_input_data()
            # Handle empty input data case
            if not input_items:
                return [[]]

            true_items: List[NodeExecutionData] = []
            false_items: List[NodeExecutionData] = []

            for item_index, item in enumerate(input_items):
                try:
                    conditions = self.get_parameter("conditions", item_index, [])
                    combine_operation = self.get_parameter("combineOperation", item_index, "all")

                    if not conditions:
                        return [[], input_items]

                    condition_results = []
                    for condition_index, condition in enumerate(conditions):
                        try:
                            result = self._evaluate_condition(condition, condition_index, item_index)
                            condition_results.append(result)
                        except Exception as e:
                            logging.error("IF Node - Error evaluating condition %d for item %d: %s",
                                          condition_index, item_index, str(e))
                            condition_results.append(False)

                    if combine_operation == "any":
                        item_passes = any(condition_results) if condition_results else False
                    else:
                        item_passes = all(condition_results) if condition_results else False

                    if item_passes:
                        true_items.append(copy.deepcopy(item))
                    else:
                        false_items.append(copy.deepcopy(item))

                except Exception as e:
                    logging.error("IF Node - Error processing item %d: %s", item_index, str(e))
                    false_items.append(copy.deepcopy(item))

            return [true_items, false_items]

        except Exception as e:
            import traceback
            logging.error(f"IF Node - Error: {str(e)}")
            logging.error(f"IF Node - Traceback: {traceback.format_exc()}")
            error_data = [NodeExecutionData(**{
                'json_data': {"error": f"Error in IF node: {str(e)}"},
                'binary_data': None
            })]
            return [[], error_data]
    
    def _evaluate_condition(self, condition: Dict[str, Any], condition_index: int, item_index: int) -> bool:
        """Evaluate a single condition"""
        try:
            data_type = condition.get("dataType", "string")
            value1 = self.get_parameter(f'conditions.{condition_index}.value1', item_index)
            value2 = self.get_parameter(f'conditions.{condition_index}.value2', item_index)
            operation = condition.get("operation", "equal")
            
            if data_type == "number":
                value1 = self._convert_to_number(value1)
                value2 = self._convert_to_number(value2)
            elif data_type == "boolean":
                value1 = self._convert_to_boolean(value1)
                value2 = self._convert_to_boolean(value2)
            elif data_type == "dateTime":
                value1 = self._convert_datetime(value1)
                value2 = self._convert_datetime(value2)
            else:  # string
                value1, value2, debug = self._prepare_string_values(value1, value2, operation)
                # You can log or use debug here if needed
                        
            result = self._compare_values(operation, value1, value2)
            return result
            
        except Exception as e:
            logging.error(f"IF Node - Error in condition evaluation: {str(e)}")
            return False
    
    def _compare_values(self, operation: str, value1: Any, value2: Any) -> bool:
        """Compare values using n8n-style operators"""
        try:
            # Handle n8n-style comparisons with proper null/undefined handling
            compare_operations = {
                'equal': lambda v1, v2: v1 == v2,
                'notEqual': lambda v1, v2: v1 != v2,
                'larger': lambda v1, v2: (v1 or 0) > (v2 or 0),
                'largerEqual': lambda v1, v2: (v1 or 0) >= (v2 or 0),
                'smaller': lambda v1, v2: (v1 or 0) < (v2 or 0),
                'smallerEqual': lambda v1, v2: (v1 or 0) <= (v2 or 0),
                'contains': lambda v1, v2: str(v2 or '') in str(v1 or ''),
                'notContains': lambda v1, v2: str(v2 or '') not in str(v1 or ''),
                'startsWith': lambda v1, v2: str(v1 or '').startswith(str(v2 or '')),
                'notStartsWith': lambda v1, v2: not str(v1 or '').startswith(str(v2 or '')),
                'endsWith': lambda v1, v2: str(v1 or '').endswith(str(v2 or '')),
                'notEndsWith': lambda v1, v2: not str(v1 or '').endswith(str(v2 or '')),
                'isEmpty': lambda v1, v2=None: self._is_empty_n8n_style(v1),
                'isNotEmpty': lambda v1, v2=None: not self._is_empty_n8n_style(v1),
                'regex': lambda v1, v2: self._regex_match(v1, v2),
                'notRegex': lambda v1, v2: not self._regex_match(v1, v2),
                'after': lambda v1, v2: (v1 or 0) > (v2 or 0),  # For dates
                'before': lambda v1, v2: (v1 or 0) < (v2 or 0)   # For dates
            }
            
            if operation in compare_operations:
                return compare_operations[operation](value1, value2)
            else:
                logging.error(f"IF Node - Unknown operation: {operation}")
                return False
                
        except Exception as e:
            logging.error(f"IF Node - Comparison error for {operation}: {str(e)}")
            return False
    
    def _convert_to_number(self, value: Any) -> Union[float, int]:
        """Convert value to number"""
        if value is None:
            return 0
        try:
            if isinstance(value, (int, float)):
                return value
            elif isinstance(value, str):
                if value.strip() == "":
                    return 0
                # Try int first, then float
                try:
                    return int(value)
                except ValueError:
                    return float(value)
            else:
                return float(value)
        except (ValueError, TypeError):
            return 0
    
    def _convert_to_boolean(self, value: Any) -> bool:
        """Convert value to boolean"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on']
        if isinstance(value, (int, float)):
            return value != 0
        return bool(value)
    
    def _convert_datetime(self, value: Any) -> float:
        """Convert datetime value to timestamp"""
        if value is None:
            return 0
        
        try:
            if isinstance(value, str):
                # Handle ISO format dates
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.timestamp()
                else:
                    # Try parsing as date
                    dt = datetime.strptime(value, '%Y-%m-%d')
                    return dt.timestamp()
            elif isinstance(value, (int, float)):
                return float(value)
            elif isinstance(value, datetime):
                return value.timestamp()
            else:
                return 0
        except Exception:
            return 0
    
    def _is_empty_n8n_style(self, value: Any) -> bool:
        """Check if value is empty using n8n logic"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        if isinstance(value, (int, float)) and value == 0:
            return False  # 0 is not considered empty in n8n
        return False
    
    def _regex_match(self, value1: Any, value2: Any) -> bool:
        """Regex matching with n8n-style pattern parsing"""
        try:
            pattern = str(value2 or '')
            text = str(value1 or '')
            if not pattern:
                return False
            regex_match = re.match(r'^/(.*?)/([gimusy]*)$', pattern)
            if regex_match:
                pattern_text = regex_match.group(1)
                flags_text = regex_match.group(2)
                flags = 0
                if 'i' in flags_text:
                    flags |= re.IGNORECASE
                if 'm' in flags_text:
                    flags |= re.MULTILINE
                if 's' in flags_text:
                    flags |= re.DOTALL
                regex = re.compile(pattern_text, flags)
            else:
                regex = re.compile(pattern)
            return bool(regex.search(text))
        except Exception as e:
            logging.error(f"IF Node - Regex error: {str(e)}")
            return False

    def _normalize_string(self, value: str) -> str:
        """Remove all whitespace characters for comparison purposes."""
        return re.sub(r'\s+', '', value) if value is not None else ''
    

    def _prepare_string_values(self, value1: Any, value2: Any, operation: str):
        """
        Prepare string values for comparison:
        - Convert None to ""
        - Normalize (remove all whitespace) for non-regex ops
        - Keep raw values for regex operations
        Returns: (prepared_value1, prepared_value2, debug_dict)
        """
        raw1 = "" if value1 is None else str(value1)
        raw2 = "" if value2 is None else str(value2)
        norm1 = self._normalize_string(raw1)
        norm2 = self._normalize_string(raw2)
        if operation in {"regex", "notRegex"}:
            used1, used2 = raw1, raw2
        else:
            used1, used2 = norm1, norm2
        debug = {
            "operation": operation,
            "raw1": raw1,
            "raw2": raw2,
            "norm1": norm1,
            "norm2": norm2
        }
        return used1, used2, debug
