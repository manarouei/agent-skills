from typing import Dict, List, Any, Union
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import copy
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class LoopNode(BaseNode):
    """
    Loop node that implements loop operations similar to n8n.
    Allows iterating over items multiple times or until a condition is met.
    """
    
    type = "loop"
    version = 1.0
    
    description = {
        "displayName": "Loop",
        "name": "loop",
        "group": ["transform"],
        "description": "Loop over input items multiple times",
        "inputs": [
            {"name": "main", "type": "main", "required": True},
        ],
        "outputs": [
            {"name": "loop", "type": "main", "required": True, "description": "Items being looped"},
            {"name": "done", "type": "main", "required": True, "description": "Items after loop completes"}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "حالت حلقه",
                "description": "Choose how the loop should operate",
                "options": [
                    {
                        "name": "تعداد مشخص",
                        "value": "count",
                        "description": "Loop a specific number of times"
                    },
                    {
                        "name": "تا زمان شرط",
                        "value": "condition",
                        "description": "Loop until a condition is met"
                    },
                    {
                        "name": "روی آیتم‌ها",
                        "value": "items",
                        "description": "Loop over each item"
                    }
                ],
                "default": "count"
            },
            # Count mode parameters
            {
                "name": "iterations",
                "type": NodeParameterType.NUMBER,
                "display_name": "تعداد تکرار",
                "default": 10,
                "description": "Number of times to loop",
                "display_options": {
                    "show": {
                        "mode": ["count"]
                    }
                }
            },
            {
                "name": "maxIterations",
                "type": NodeParameterType.NUMBER,
                "display_name": "حداکثر تعداد تکرار",
                "default": 100,
                "description": "Maximum number of iterations to prevent infinite loops",
                "display_options": {
                    "show": {
                        "mode": ["condition"]
                    }
                }
            },
            # Condition mode parameters
            {
                "name": "conditions",
                "type": NodeParameterType.ARRAY,
                "display_name": "شرایط",
                "default": [],
                "display_options": {
                    "show": {
                        "mode": ["condition"]
                    }
                },
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
                        "display_name": "عملیات",
                        "options": [
                            {"name": "مساوی", "value": "equal"},
                            {"name": "نامساوی", "value": "notEqual"},
                            {"name": "بزرگتر", "value": "larger"},
                            {"name": "بزرگتر مساوی", "value": "largerEqual"},
                            {"name": "کوچکتر", "value": "smaller"},
                            {"name": "کوچکتر مساوی", "value": "smallerEqual"},
                            {"name": "شامل", "value": "contains"},
                            {"name": "شامل نباشد", "value": "notContains"},
                            {"name": "شروع شود با", "value": "startsWith"},
                            {"name": "شروع نشود با", "value": "notStartsWith"},
                            {"name": "پایان یابد با", "value": "endsWith"},
                            {"name": "پایان نیابد با", "value": "notEndsWith"},
                            {"name": "عبارت منظم", "value": "regex"},
                            {"name": "عبارت منظم نباشد", "value": "notRegex"},
                            {"name": "خالی باشد", "value": "isEmpty"},
                            {"name": "خالی نباشد", "value": "isNotEmpty"},
                            {"name": "بعد از", "value": "after"},
                            {"name": "قبل از", "value": "before"}
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
                "display_name": "ترکیب شرایط",
                "description": "نحوه ترکیب شرایط متعدد",
                "options": [
                    {
                        "name": "و",
                        "value": "all",
                        "description": "حلقه تا زمانی ادامه یابد که همه شرایط برقرار باشند"
                    },
                    {
                        "name": "یا",
                        "value": "any",
                        "description": "حلقه تا زمانی ادامه یابد که حداقل یکی از شرایط برقرار باشد"
                    }
                ],
                "default": "all",
                "display_options": {
                    "show": {
                        "mode": ["condition"]
                    }
                }
            },
            # Common parameters
            {
                "name": "loopIndex",
                "type": NodeParameterType.STRING,
                "display_name": "نام فیلد شاخص",
                "default": "loopIndex",
                "description": "Name of the field to store the current loop index"
            },
            {
                "name": "continueOnFail",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "ادامه در صورت خطا",
                "default": False,
                "description": "Continue to the next iteration even if an error occurs"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "تنظیمات",
                "default": {},
                "placeholder": "Add Option",
                "options": [
                    {
                        "name": "resetData",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "بازنشانی داده در هر تکرار",
                        "default": False,
                        "description": "Reset input data for each iteration instead of using output from previous iteration"
                    },
                    {
                        "name": "pauseBetweenIterations",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "توقف بین تکرارها (میلی‌ثانیه)",
                        "default": 0,
                        "description": "Time to wait between iterations in milliseconds"
                    }
                ]
            }
        ]
    }
    
    icon = "fa:repeat"
    color = "#FF6D5A"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute loop node logic"""
        try:
            input_items = self.get_input_data()
            
            # Handle empty input data case
            if not input_items:
                logger.warning("Loop Node - No input items received")
                return [[], []]
            
            mode = self.get_parameter("mode", 0, "count")
            loop_index_field = self.get_parameter("loopIndex", 0, "loopIndex")
            continue_on_fail = self.get_parameter("continueOnFail", 0, False)
            
            # Get options
            options = self.get_parameter("options", 0, {})
            reset_data = options.get("resetData", False)
            pause_between = options.get("pauseBetweenIterations", 0)
            
            loop_items: List[NodeExecutionData] = []
            done_items: List[NodeExecutionData] = []
            
            if mode == "count":
                # Loop a specific number of times
                iterations = self.get_parameter("iterations", 0, 10)
                iterations = max(1, min(iterations, 10000))  # Safety limits
                
                logger.info(f"Loop Node - Count mode: {iterations} iterations")
                
                for item_index, item in enumerate(input_items):
                    current_data = copy.deepcopy(item)
                    original_data = copy.deepcopy(item) if reset_data else None
                    
                    for loop_idx in range(iterations):
                        try:
                            # Create loop item with loop index
                            loop_item = copy.deepcopy(original_data if reset_data else current_data)
                            
                            # Add loop metadata
                            if not hasattr(loop_item, 'json_data') or loop_item.json_data is None:
                                loop_item.json_data = {}
                            
                            loop_item.json_data[loop_index_field] = loop_idx
                            loop_item.json_data['_loopIteration'] = loop_idx
                            loop_item.json_data['_loopTotal'] = iterations
                            
                            loop_items.append(loop_item)
                            
                            # Simulate pause if needed (for rate limiting)
                            if pause_between > 0 and loop_idx < iterations - 1:
                                import time
                                time.sleep(pause_between / 1000.0)
                            
                        except Exception as e:
                            logger.error(f"Loop Node - Error in iteration {loop_idx} for item {item_index}: {str(e)}")
                            if not continue_on_fail:
                                raise
                    
                    # Add to done items after all iterations
                    done_item = copy.deepcopy(current_data)
                    if hasattr(done_item, 'json_data') and done_item.json_data:
                        done_item.json_data[loop_index_field] = iterations
                        done_item.json_data['_loopCompleted'] = True
                    done_items.append(done_item)
            
            elif mode == "condition":
                # Loop until condition is met
                max_iterations = self.get_parameter("maxIterations", 0, 100)
                max_iterations = max(1, min(max_iterations, 10000))  # Safety limits
                conditions = self.get_parameter("conditions", 0, [])
                combine_operation = self.get_parameter("combineOperation", 0, "all")
                
                logger.info(f"Loop Node - Condition mode: max {max_iterations} iterations")
                
                for item_index, item in enumerate(input_items):
                    current_data = copy.deepcopy(item)
                    original_data = copy.deepcopy(item) if reset_data else None
                    loop_idx = 0
                    
                    while loop_idx < max_iterations:
                        try:
                            # Create loop item with loop index
                            loop_item = copy.deepcopy(original_data if reset_data else current_data)
                            
                            # Add loop metadata
                            if not hasattr(loop_item, 'json_data') or loop_item.json_data is None:
                                loop_item.json_data = {}
                            
                            loop_item.json_data[loop_index_field] = loop_idx
                            loop_item.json_data['_loopIteration'] = loop_idx
                            loop_item.json_data['_loopMaxIterations'] = max_iterations
                            
                            loop_items.append(loop_item)
                            
                            # Evaluate continue condition using if node logic
                            should_continue = self._evaluate_conditions(
                                conditions,
                                combine_operation,
                                item_index
                            )
                            
                            if not should_continue:
                                logger.info(f"Loop Node - Condition not met, stopping at iteration {loop_idx}")
                                break
                            
                            loop_idx += 1
                            
                            # Simulate pause if needed
                            if pause_between > 0 and loop_idx < max_iterations:
                                import time
                                time.sleep(pause_between / 1000.0)
                            
                        except Exception as e:
                            logger.error(f"Loop Node - Error in iteration {loop_idx} for item {item_index}: {str(e)}")
                            if not continue_on_fail:
                                raise
                            break
                    
                    # Add to done items
                    done_item = copy.deepcopy(current_data)
                    if hasattr(done_item, 'json_data') and done_item.json_data:
                        done_item.json_data[loop_index_field] = loop_idx
                        done_item.json_data['_loopCompleted'] = True
                        done_item.json_data['_loopIterations'] = loop_idx + 1
                    done_items.append(done_item)
            
            elif mode == "items":
                # Loop over each item individually
                logger.info(f"Loop Node - Items mode: {len(input_items)} items")
                
                for item_index, item in enumerate(input_items):
                    try:
                        loop_item = copy.deepcopy(item)
                        
                        # Add loop metadata
                        if not hasattr(loop_item, 'json_data') or loop_item.json_data is None:
                            loop_item.json_data = {}
                        
                        loop_item.json_data[loop_index_field] = item_index
                        loop_item.json_data['_loopItemIndex'] = item_index
                        loop_item.json_data['_loopTotalItems'] = len(input_items)
                        
                        loop_items.append(loop_item)
                        
                        # Also add to done items
                        done_item = copy.deepcopy(loop_item)
                        done_items.append(done_item)
                        
                    except Exception as e:
                        logger.error(f"Loop Node - Error processing item {item_index}: {str(e)}")
                        if not continue_on_fail:
                            raise
            
            logger.info(f"Loop Node - Completed: {len(loop_items)} loop items, {len(done_items)} done items")
            return [loop_items, done_items]
            
        except Exception as e:
            import traceback
            logger.error(f"Loop Node - Error: {str(e)}")
            logger.error(f"Loop Node - Traceback: {traceback.format_exc()}")
            
            error_data = [NodeExecutionData(**{
                'json_data': {
                    "error": f"Error in Loop node: {str(e)}",
                    "errorType": "LoopExecutionError"
                },
                'binary_data': None
            })]
            return [[], error_data]
    
    def _evaluate_conditions(
        self,
        conditions: List[Dict[str, Any]],
        combine_operation: str,
        item_index: int
    ) -> bool:
        """
        Evaluate conditions to determine if loop should continue.
        Returns True if loop should continue, False if it should stop.
        """
        try:
            if not conditions:
                return True  # No conditions means continue
            
            condition_results = []
            for condition_index, condition in enumerate(conditions):
                try:
                    result = self._evaluate_condition(condition, condition_index, item_index)
                    condition_results.append(result)
                except Exception as e:
                    logger.error(f"Loop Node - Error evaluating condition {condition_index}: {str(e)}")
                    condition_results.append(False)
            
            # Combine results
            if combine_operation == "any":
                return any(condition_results) if condition_results else False
            else:  # "all"
                return all(condition_results) if condition_results else False
                
        except Exception as e:
            logger.error(f"Loop Node - Error evaluating conditions: {str(e)}")
            return False
    
    def _evaluate_condition(self, condition: Dict[str, Any], condition_index: int, item_index: int) -> bool:
        """Evaluate a single condition (same logic as IF node)"""
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
                        
            result = self._compare_values(operation, value1, value2)
            return result
            
        except Exception as e:
            logger.error(f"Loop Node - Error in condition evaluation: {str(e)}")
            return False
    
    def _compare_values(self, operation: str, value1: Any, value2: Any) -> bool:
        """Compare values using n8n-style operators"""
        try:
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
                'after': lambda v1, v2: (v1 or 0) > (v2 or 0),
                'before': lambda v1, v2: (v1 or 0) < (v2 or 0)
            }
            
            if operation in compare_operations:
                return compare_operations[operation](value1, value2)
            else:
                logger.error(f"Loop Node - Unknown operation: {operation}")
                return False
                
        except Exception as e:
            logger.error(f"Loop Node - Comparison error for {operation}: {str(e)}")
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
                if 'T' in value:
                    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return dt.timestamp()
                else:
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
            return False
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
            logger.error(f"Loop Node - Regex error: {str(e)}")
            return False
    
    def _normalize_string(self, value: str) -> str:
        """Remove all whitespace characters for comparison purposes."""
        return re.sub(r'\s+', '', value) if value is not None else ''
    
    def _prepare_string_values(self, value1: Any, value2: Any, operation: str):
        """Prepare string values for comparison"""
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
