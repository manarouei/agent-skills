from typing import Dict, List, Any, Optional, Union
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import copy
import logging
import re
from datetime import datetime
from operator import itemgetter

logger = logging.getLogger(__name__)

class FilterNode(BaseNode):
    """
    Filter Node that provides safe filtering, searching, and sorting capabilities.
    Supports declarative configuration without custom code execution.
    """
    
    type = "filter"
    version = 1
    
    description = {
        "displayName": "Filter",
        "name": "filter",
        "group": ["transform"],
        "inputs": [
            {"name": "main", "type": "main", "required": True},
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True},
        ],
    }
    
    properties = {
        "parameters": [
            # Operations - Use simple OPTIONS with multiple operations combined
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "description": "Select operation to perform",
                "options": [
                    {"name": "Filter Only", "value": "filter"},
                    {"name": "Search Only", "value": "search"},
                    {"name": "Sort Only", "value": "sort"},
                    {"name": "Search + Sort", "value": "search_sort"},
                    {"name": "Filter + Sort", "value": "filter_sort"},
                    {"name": "Search + Filter + Sort", "value": "all"}
                ],
                "default": "search_sort",
                "required": True
            },
            
            # Filter Configuration
            {
                "name": "filterConditions",
                "type": NodeParameterType.ARRAY,
                "display_name": "Filter Conditions",
                "default": [],
                "description": "Define conditions to filter items",
                "display_options": {
                    "show": {
                        "operation": ["filter", "filter_sort", "all"]
                    }
                },
                "options": [
                    {
                        "name": "field",
                        "type": NodeParameterType.STRING,
                        "display_name": "Field",
                        "placeholder": "status",
                        "description": "Field name to filter on (supports dot notation like user.name)",
                        "required": True
                    },
                    {
                        "name": "operator",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Operator",
                        "options": [
                            {"name": "Equal", "value": "equal"},
                            {"name": "Not Equal", "value": "notEqual"},
                            {"name": "Greater Than", "value": "greaterThan"},
                            {"name": "Greater Than or Equal", "value": "greaterThanOrEqual"},
                            {"name": "Less Than", "value": "lessThan"},
                            {"name": "Less Than or Equal", "value": "lessThanOrEqual"},
                            {"name": "Contains", "value": "contains"},
                            {"name": "Not Contains", "value": "notContains"},
                            {"name": "Starts With", "value": "startsWith"},
                            {"name": "Ends With", "value": "endsWith"},
                            {"name": "Is Empty", "value": "isEmpty"},
                            {"name": "Is Not Empty", "value": "isNotEmpty"},
                            {"name": "In List", "value": "inList"},
                            {"name": "Not In List", "value": "notInList"}
                        ],
                        "default": "equal",
                        "required": True
                    },
                    {
                        "name": "value",
                        "type": NodeParameterType.STRING,
                        "display_name": "Value",
                        "default": "",
                        "description": "Value to compare against",
                        "display_options": {
                            "hide": {
                                "operator": ["isEmpty", "isNotEmpty"]
                            }
                        }
                    },
                    {
                        "name": "listValues",
                        "type": NodeParameterType.STRING,
                        "display_name": "List Values",
                        "default": "",
                        "placeholder": "value1,value2,value3",
                        "description": "Comma-separated list of values",
                        "display_options": {
                            "show": {
                                "operator": ["inList", "notInList"]
                            }
                        }
                    },
                    {
                        "name": "dataType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Data Type",
                        "options": [
                            {"name": "String", "value": "string"},
                            {"name": "Number", "value": "number"},
                            {"name": "Boolean", "value": "boolean"},
                            {"name": "Date/Time", "value": "dateTime"}
                        ],
                        "default": "string",
                        "description": "How to interpret the field value"
                    },
                    {
                        "name": "caseSensitive",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Case Sensitive",
                        "default": False,
                        "description": "Whether string comparisons should be case sensitive",
                        "display_options": {
                            "show": {
                                "dataType": ["string"]
                            }
                        }
                    }
                ]
            },
            
            # Filter logic combination
            {
                "name": "filterLogic",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Filter Logic",
                "options": [
                    {"name": "AND (all conditions must match)", "value": "and"},
                    {"name": "OR (any condition can match)", "value": "or"}
                ],
                "default": "and",
                "description": "How to combine multiple filter conditions",
                "display_options": {
                    "show": {
                        "operation": ["filter", "filter_sort", "all"]
                    }
                }
            },
            
            # Search Configuration
            {
                "name": "searchQuery",
                "type": NodeParameterType.STRING,
                "display_name": "Search Query",
                "default": "",
                "placeholder": "search term",
                "description": "Text to search for",
                "display_options": {
                    "show": {
                        "operation": ["search", "search_sort", "all"]
                    }
                }
            },
            {
                "name": "searchFields",
                "type": NodeParameterType.STRING,
                "display_name": "Fields to Search",
                "default": "",
                "placeholder": "name,description,tags",
                "description": "Comma-separated list of fields to search in (empty = all string fields)",
                "display_options": {
                    "show": {
                        "operation": ["search", "search_sort", "all"]
                    }
                }
            },
            {
                "name": "searchMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Search Mode",
                "options": [
                    {"name": "Contains", "value": "contains"},
                    {"name": "Exact Match", "value": "exact"},
                    {"name": "Starts With", "value": "startsWith"},
                    {"name": "Ends With", "value": "endsWith"},
                    {"name": "Word Match", "value": "word"}
                ],
                "default": "contains",
                "display_options": {
                    "show": {
                        "operation": ["search", "search_sort", "all"]
                    }
                }
            },
            {
                "name": "searchCaseSensitive",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Case Sensitive Search",
                "default": False,
                "display_options": {
                    "show": {
                        "operation": ["search", "search_sort", "all"]
                    }
                }
            },
            {
                "name": "searchWholeWords",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Whole Words Only",
                "default": False,
                "description": "Match whole words only (for contains mode)",
                "display_options": {
                    "show": {
                        "operation": ["search", "search_sort", "all"]
                    }
                }
            },
            
            # Sort Configuration
            {
                "name": "sortField",
                "type": NodeParameterType.STRING,
                "display_name": "Sort Field",
                "default": "",
                "placeholder": "createdAt",
                "description": "Field to sort by (supports dot notation)",
                "display_options": {
                    "show": {
                        "operation": ["sort", "search_sort", "filter_sort", "all"]
                    }
                }
            },
            {
                "name": "sortDirection",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Sort Direction",
                "options": [
                    {"name": "Ascending (A-Z, 1-9)", "value": "asc"},
                    {"name": "Descending (Z-A, 9-1)", "value": "desc"}
                ],
                "default": "desc",
                "display_options": {
                    "show": {
                        "operation": ["sort", "search_sort", "filter_sort", "all"]
                    }
                }
            },
            {
                "name": "sortDataType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Sort Data Type",
                "options": [
                    {"name": "String", "value": "string"},
                    {"name": "Number", "value": "number"},
                    {"name": "Date/Time", "value": "dateTime"},
                    {"name": "Boolean", "value": "boolean"}
                ],
                "default": "number",
                "description": "How to interpret field values for sorting",
                "display_options": {
                    "show": {
                        "operation": ["sort", "search_sort", "filter_sort", "all"]
                    }
                }
            },
            {
                "name": "sortCaseSensitive",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Case Sensitive Sort",
                "default": False,
                "description": "Whether string sorting should be case sensitive",
                "display_options": {
                    "show": {
                        "operation": ["sort", "search_sort", "filter_sort", "all"],
                        "sortDataType": ["string"]
                    }
                }
            },
            {
                "name": "nullsLast",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Null Values Last",
                "default": True,
                "description": "Whether to put null/empty values at the end",
                "display_options": {
                    "show": {
                        "operation": ["sort", "search_sort", "filter_sort", "all"]
                    }
                }
            },
            
            # Options
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "description": "Additional options",
                "options": [
                    {
                        "name": "continueOnError",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Continue On Error",
                        "default": False,
                        "description": "Continue processing even if some items cause errors"
                    },
                    {
                        "name": "maxResults",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Results",
                        "default": 50,
                        "description": "Maximum number of items to return (0 = no limit)",
                        "type_options": {
                            "min_value": 0
                        }
                    },
                    {
                        "name": "skipItems",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Skip Items",
                        "default": 0,
                        "description": "Number of items to skip from the beginning",
                        "type_options": {
                            "min_value": 0
                        }
                    }
                ]
            }
        ]
    }
    
    icon = "fa:filter"
    color = "#9966CC"
    
    # Update execute method to handle the simplified operation parameter
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute filter operations"""
        try:
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("Filter Node - No input data")
                return [[]]
            
            # Get configuration - Handle single operation parameter  
            operation = self.get_parameter("operation", 0, "search_sort")
            
            # Map operation to operations list
            operations_map = {
                "filter": ["filter"],
                "search": ["search"],
                "sort": ["sort"],
                "search_sort": ["search", "sort"],
                "filter_sort": ["filter", "sort"],
                "all": ["search", "filter", "sort"]
            }
            operations = operations_map.get(operation, ["search"])
            
            options = self.get_parameter("options", 0, {})
            continue_on_error = options.get("continueOnError", False)
            max_results = options.get("maxResults", 50)
            skip_items = options.get("skipItems", 0)
            
            logger.info(f"Filter Node - Processing {len(input_data)} items with operations: {operations}")
            
            result_items = input_data
            
            # Apply operations in sequence
            if "filter" in operations:
                result_items = self._apply_filter(result_items, continue_on_error)
                
            if "search" in operations:
                result_items = self._apply_search(result_items, continue_on_error)
                
            if "sort" in operations:
                result_items = self._apply_sort(result_items, continue_on_error)
            
            # Apply pagination
            if skip_items > 0:
                result_items = result_items[skip_items:]
                
            if max_results > 0:
                result_items = result_items[:max_results]
                
            logger.info(f"Filter Node - Processed {len(input_data)} items, returned {len(result_items)} items")
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Filter Node - Execution error: {str(e)}")
            return [[]]
    
    def _apply_filter(self, items: List[NodeExecutionData], continue_on_error: bool) -> List[NodeExecutionData]:
        """Apply filter conditions"""
        try:
            conditions = self.get_parameter("filterConditions", 0, [])
            logic = self.get_parameter("filterLogic", 0, "and")
            
            if not conditions:
                return items
            
            filtered_items = []
            
            for item in items:
                try:
                    if self._evaluate_filter_conditions(item.json_data, conditions, logic):
                        filtered_items.append(item)
                except Exception as e:
                    if continue_on_error:
                        logger.warning(f"Filter Node - Error evaluating filter for item: {str(e)}")
                        continue
                    else:
                        raise
            
            return filtered_items
            
        except Exception as e:
            logger.error(f"Filter Node - Filter error: {str(e)}")
            if continue_on_error:
                return items
            else:
                raise
    
    def _evaluate_filter_conditions(self, item_data: Dict[str, Any], conditions: List[Dict[str, Any]], logic: str) -> bool:
        """Evaluate all filter conditions for an item"""
        if not conditions:
            return True
        
        results = []
        
        for condition in conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "equal")
            value = condition.get("value", "")
            list_values = condition.get("listValues", "")
            data_type = condition.get("dataType", "string")
            case_sensitive = condition.get("caseSensitive", False)
            
            try:
                result = self._evaluate_single_condition(
                    item_data, field, operator, value, list_values, data_type, case_sensitive
                )
                results.append(result)
            except Exception as e:
                logger.warning(f"Filter Node - Error evaluating condition: {str(e)}")
                results.append(False)
        
        # Combine results based on logic
        if logic == "or":
            return any(results)
        else:  # and
            return all(results)
    
    def _evaluate_single_condition(
        self, item_data: Dict[str, Any], field: str, operator: str, 
        value: str, list_values: str, data_type: str, case_sensitive: bool
    ) -> bool:
        """Evaluate a single filter condition"""
        
        # Get field value using dot notation
        field_value = self._get_nested_field_value(item_data, field)
        
        # Handle isEmpty/isNotEmpty operators
        if operator == "isEmpty":
            return self._is_empty_value(field_value)
        elif operator == "isNotEmpty":
            return not self._is_empty_value(field_value)
        
        # Convert values based on data type
        field_value = self._convert_value(field_value, data_type)
        compare_value = self._convert_value(value, data_type)
        
        # Handle case sensitivity for strings
        if data_type == "string" and not case_sensitive:
            if isinstance(field_value, str):
                field_value = field_value.lower()
            if isinstance(compare_value, str):
                compare_value = compare_value.lower()
        
        # Evaluate based on operator
        if operator == "equal":
            return field_value == compare_value
        elif operator == "notEqual":
            return field_value != compare_value
        elif operator == "greaterThan":
            return field_value > compare_value
        elif operator == "greaterThanOrEqual":
            return field_value >= compare_value
        elif operator == "lessThan":
            return field_value < compare_value
        elif operator == "lessThanOrEqual":
            return field_value <= compare_value
        elif operator == "contains":
            return str(compare_value) in str(field_value)
        elif operator == "notContains":
            return str(compare_value) not in str(field_value)
        elif operator == "startsWith":
            return str(field_value).startswith(str(compare_value))
        elif operator == "endsWith":
            return str(field_value).endswith(str(compare_value))
        elif operator == "inList":
            list_items = [item.strip() for item in list_values.split(",") if item.strip()]
            converted_list = [self._convert_value(item, data_type) for item in list_items]
            if data_type == "string" and not case_sensitive:
                converted_list = [item.lower() if isinstance(item, str) else item for item in converted_list]
            return field_value in converted_list
        elif operator == "notInList":
            list_items = [item.strip() for item in list_values.split(",") if item.strip()]
            converted_list = [self._convert_value(item, data_type) for item in list_items]
            if data_type == "string" and not case_sensitive:
                converted_list = [item.lower() if isinstance(item, str) else item for item in converted_list]
            return field_value not in converted_list
        
        return False
    
    def _apply_search(self, items: List[NodeExecutionData], continue_on_error: bool) -> List[NodeExecutionData]:
        """Apply search operation"""
        try:
            query = self.get_parameter("searchQuery", 0, "")
            fields = self.get_parameter("searchFields", 0, "")
            mode = self.get_parameter("searchMode", 0, "contains")
            case_sensitive = self.get_parameter("searchCaseSensitive", 0, False)
            whole_words = self.get_parameter("searchWholeWords", 0, False)
            
            if not query:
                return items
                
            search_fields = [f.strip() for f in fields.split(",") if f.strip()] if fields else []
            
            # DEBUG: Log search parameters
            logger.info(f"Filter Node - Search: query='{query}', fields={search_fields}, mode={mode}")
            logger.info(f"Filter Node - Sample item data: {items[0].json_data if items else 'No items'}")
            
            filtered_items = []
            for item in items:
                # FIX: Access json_data instead of item['data']
                if self._item_matches_search(item.json_data, query, search_fields, mode, case_sensitive, whole_words):
                    filtered_items.append(item)
                    
            logger.info(f"Filter Node - Search found {len(filtered_items)} matches out of {len(items)} items")
            return filtered_items
            
        except Exception as e:
            logger.error(f"Filter Node - Search error: {str(e)}")
            return items if continue_on_error else []
    
    def _item_matches_search(
        self, item_data: Dict[str, Any], query: str, search_fields: List[str],
        mode: str, case_sensitive: bool, whole_words: bool
    ) -> bool:
        """Check if item matches search query"""
        
        if not case_sensitive:
            query = query.lower()
        
        # Determine which fields to search
        fields_to_search = search_fields if search_fields else self._get_searchable_fields(item_data)
        
        for field in fields_to_search:
            field_value = self._get_nested_field_value(item_data, field)
            
            if field_value is None:
                continue
            
            field_str = str(field_value)
            if not case_sensitive:
                field_str = field_str.lower()
            
            if self._field_matches_query(field_str, query, mode, whole_words):
                return True
        
        return False
    
    def _field_matches_query(self, field_value: str, query: str, mode: str, whole_words: bool) -> bool:
        """Check if a field value matches the search query"""
        
        if mode == "exact":
            return field_value == query
        elif mode == "startsWith":
            return field_value.startswith(query)
        elif mode == "endsWith":
            return field_value.endswith(query)
        elif mode == "contains":
            if whole_words:
                # Use word boundary regex
                pattern = r'\b' + re.escape(query) + r'\b'
                return bool(re.search(pattern, field_value, re.IGNORECASE if not case_sensitive else 0))
            else:
                return query in field_value
        elif mode == "word":
            # Split into words and check for exact word match
            words = field_value.split()
            return query in words
        
        return False
    
    def _get_searchable_fields(self, item_data: Dict[str, Any]) -> List[str]:
        """Get list of searchable string fields from item data"""
        searchable_fields = []
        
        def collect_fields(data, prefix=""):
            if isinstance(data, dict):
                for key, value in data.items():
                    field_path = f"{prefix}.{key}" if prefix else key
                    if isinstance(value, str):
                        searchable_fields.append(field_path)
                    elif isinstance(value, dict):
                        collect_fields(value, field_path)
        
        collect_fields(item_data)
        return searchable_fields
    
    def _apply_sort(self, items: List[NodeExecutionData], continue_on_error: bool) -> List[NodeExecutionData]:
        """Apply sort operation"""
        try:
            sort_field = self.get_parameter("sortField", 0, "")
            direction = self.get_parameter("sortDirection", 0, "desc") 
            data_type = self.get_parameter("sortDataType", 0, "number")
            case_sensitive = self.get_parameter("sortCaseSensitive", 0, False)
            nulls_last = self.get_parameter("nullsLast", 0, True)
            
            if not sort_field:
                return items
                
            return self._sort_items(items, sort_field, direction, data_type, case_sensitive, nulls_last)
            
        except Exception as e:
            logger.error(f"Filter Node - Sort error: {str(e)}")
            return items if continue_on_error else []
    
    def _sort_items(
        self, items: List[NodeExecutionData], sort_field: str, direction: str, 
        data_type: str, case_sensitive: bool, nulls_last: bool
    ) -> List[NodeExecutionData]:
        """Sort items based on field and direction"""
        
        def sort_key(item):
            try:
                # FIX: Access json_data instead of item['data']
                value = self._get_nested_field_value(item.json_data, sort_field)
                converted_value = self._convert_value(value, data_type)
                
                # Handle null values
                if converted_value is None:
                    return (1 if nulls_last else 0, "")
                
                # Handle case sensitivity for strings
                if data_type == "string" and not case_sensitive and isinstance(converted_value, str):
                    converted_value = converted_value.lower()
                
                return (0 if not nulls_last else 0, converted_value)
                
            except Exception as e:
                logger.warning(f"Filter Node - Error getting sort key for item: {str(e)}")
            return (1 if nulls_last else 0, "")
    
        reverse = direction == "desc"
        sorted_items = sorted(items, key=sort_key, reverse=reverse)
        
        return sorted_items
    
    def _get_nested_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get nested field value using dot notation (similar to iterator.py)"""
        if not field_path:
            return data
        
        keys = field_path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current
    
    def _convert_value(self, value: Any, data_type: str) -> Any:
        """Convert value to specified data type"""
        if value is None:
            return None
        
        try:
            if data_type == "number":
                if isinstance(value, (int, float)):
                    return value
                return float(str(value))
            elif data_type == "boolean":
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ("true", "1", "yes", "on")
                return bool(value)
            elif data_type == "dateTime":
                if isinstance(value, datetime):
                    return value
                if isinstance(value, str):
                    # Try common datetime formats
                    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                        try:
                            return datetime.strptime(value, fmt)
                        except ValueError:
                            continue
                    # Try ISO format
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                return datetime.fromtimestamp(float(value))
            else:  # string
                return str(value)
        except (ValueError, TypeError, OverflowError):
            return value
    
    def _is_empty_value(self, value: Any) -> bool:
        """Check if a value is considered empty (similar to iterator.py)"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False