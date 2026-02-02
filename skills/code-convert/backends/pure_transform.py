#!/usr/bin/env python3
"""
Pure Transform Backend Converter

Converts data transformation nodes (Merge, IF, Switch, Filter, Set, Iterator)
to Python BaseNode implementations.

These nodes have no external connections - they transform input data to output.
"""

from __future__ import annotations
from typing import Any, Dict, List


# Transform node configurations
TRANSFORM_CONFIGS: Dict[str, Dict[str, Any]] = {
    "merge": {
        "multi_input": True,
        "multi_output": False,
        "item_mapping": "N:M",
    },
    "if": {
        "multi_input": False,
        "multi_output": True,
        "output_names": ["true", "false"],
        "item_mapping": "route",
    },
    "switch": {
        "multi_input": False,
        "multi_output": True,
        "output_names": ["dynamic"],  # Based on rules
        "item_mapping": "route",
    },
    "filter": {
        "multi_input": False,
        "multi_output": False,
        "item_mapping": "filter",
    },
    "set": {
        "multi_input": False,
        "multi_output": False,
        "item_mapping": "1:1",
    },
    "iterator": {
        "multi_input": False,
        "multi_output": False,
        "item_mapping": "1:N",
    },
    "htmlextractor": {
        "multi_input": False,
        "multi_output": False,
        "item_mapping": "1:1",
    },
}


def convert_pure_transform_node(
    node_name: str,
    node_schema: Dict[str, Any],
    ts_code: str,
    properties: List[Dict[str, Any]],
    execution_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert a pure transformation node to Python.
    
    Args:
        node_name: Node type name
        node_schema: Complete inferred schema
        ts_code: Raw TypeScript source code
        properties: Node parameters
        execution_contract: The node's execution contract
    
    Returns:
        Dict with python_code, imports, helpers, conversion_notes
    """
    node_name_lower = node_name.lower().replace("-", "").replace("_", "")
    io_cardinality = execution_contract.get("io_cardinality", {})
    transform_config = execution_contract.get("transform_config", {})
    
    # Get transform configuration
    config = TRANSFORM_CONFIGS.get(node_name_lower, {})
    multi_input = config.get("multi_input", False)
    multi_output = config.get("multi_output", False)
    output_names = io_cardinality.get("output_names", ["main"])
    item_mapping = io_cardinality.get("item_mapping", "1:1")
    
    # Generate helper methods based on transform type
    if node_name_lower == "merge":
        helpers = _generate_merge_helpers()
    elif node_name_lower == "if":
        helpers = _generate_if_helpers()
    elif node_name_lower == "switch":
        helpers = _generate_switch_helpers()
    elif node_name_lower == "filter":
        helpers = _generate_filter_helpers()
    elif node_name_lower == "set":
        helpers = _generate_set_helpers()
    elif node_name_lower == "iterator":
        helpers = _generate_iterator_helpers()
    else:
        helpers = _generate_generic_transform_helpers(node_name_lower)
    
    # Generate imports
    imports = [
        "import copy",
        "import logging",
        "from typing import Any, Dict, List, Optional",
    ]
    
    # Add regex if needed
    if node_name_lower in ("filter", "if", "switch"):
        imports.append("import re")
    
    conversion_notes = [
        f"Using pure_transform backend for {node_name}",
        f"Multi-input: {multi_input}",
        f"Multi-output: {multi_output}",
        f"Output names: {output_names}",
        f"Item mapping: {item_mapping}",
    ]
    
    return {
        "python_code": "",  # Execute method generated based on config
        "imports": imports,
        "helpers": helpers,
        "conversion_notes": conversion_notes,
        "multi_input": multi_input,
        "multi_output": multi_output,
        "output_names": output_names,
    }


def _generate_merge_helpers() -> str:
    """Generate merge node helper methods."""
    return '''
    def _merge_append(
        self,
        inputs: List[List["NodeExecutionData"]],
    ) -> List["NodeExecutionData"]:
        """
        Merge inputs by appending all items sequentially.
        """
        result = []
        for input_items in inputs:
            result.extend(input_items)
        return result
    
    def _merge_by_position(
        self,
        inputs: List[List["NodeExecutionData"]],
    ) -> List["NodeExecutionData"]:
        """
        Merge inputs by position (zip-like merge).
        """
        result = []
        max_len = max(len(inp) for inp in inputs) if inputs else 0
        
        for i in range(max_len):
            merged_data = {}
            for j, input_items in enumerate(inputs):
                if i < len(input_items):
                    item = input_items[i]
                    # Prefix keys with input index to avoid collisions
                    for key, value in (item.json_data or {}).items():
                        merged_data[f"input{j+1}_{key}"] = value
            
            if merged_data:
                result.append(NodeExecutionData(json_data=merged_data, binary_data=None))
        
        return result
    
    def _merge_by_key(
        self,
        inputs: List[List["NodeExecutionData"]],
        match_key: str,
        join_mode: str = "inner",
    ) -> List["NodeExecutionData"]:
        """
        Merge inputs by matching key values.
        """
        if len(inputs) < 2:
            return inputs[0] if inputs else []
        
        # Build index from first input
        index = {}
        for item in inputs[0]:
            key_value = (item.json_data or {}).get(match_key)
            if key_value is not None:
                index[key_value] = item
        
        result = []
        matched_keys = set()
        
        # Match against second input
        for item in inputs[1]:
            key_value = (item.json_data or {}).get(match_key)
            if key_value in index:
                merged_data = {**(index[key_value].json_data or {}), **(item.json_data or {})}
                result.append(NodeExecutionData(json_data=merged_data, binary_data=None))
                matched_keys.add(key_value)
            elif join_mode in ("left", "outer"):
                # Include unmatched from second input
                result.append(item)
        
        # Include unmatched from first input for outer join
        if join_mode == "outer":
            for key_value, item in index.items():
                if key_value not in matched_keys:
                    result.append(item)
        
        return result
'''


def _generate_if_helpers() -> str:
    """Generate IF node helper methods."""
    return '''
    def _evaluate_condition(
        self,
        item: "NodeExecutionData",
        conditions: List[Dict[str, Any]],
        combine_mode: str = "all",
    ) -> bool:
        """
        Evaluate conditions against an item.
        
        Args:
            item: The item to evaluate
            conditions: List of condition definitions
            combine_mode: "all" (AND) or "any" (OR)
        
        Returns:
            True if conditions are met
        """
        if not conditions:
            return True
        
        results = []
        data = item.json_data or {}
        
        for cond in conditions:
            value1 = self._get_value(data, cond.get("value1", ""))
            operation = cond.get("operation", "equal")
            value2 = cond.get("value2", "")
            
            result = self._compare(value1, operation, value2)
            results.append(result)
        
        if combine_mode == "all":
            return all(results)
        else:
            return any(results)
    
    def _get_value(self, data: Dict, path: str) -> Any:
        """Get a value from data using dot notation path."""
        if not path:
            return None
        
        # Handle expression references
        if path.startswith("{{") and path.endswith("}}"):
            # Expression - would need expression evaluator
            path = path[2:-2].strip()
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _compare(self, value1: Any, operation: str, value2: Any) -> bool:
        """Compare two values using the specified operation."""
        if operation == "equal":
            return str(value1) == str(value2)
        elif operation == "notEqual":
            return str(value1) != str(value2)
        elif operation == "contains":
            return str(value2) in str(value1)
        elif operation == "notContains":
            return str(value2) not in str(value1)
        elif operation == "startsWith":
            return str(value1).startswith(str(value2))
        elif operation == "endsWith":
            return str(value1).endswith(str(value2))
        elif operation == "isEmpty":
            return value1 is None or value1 == "" or value1 == []
        elif operation == "isNotEmpty":
            return value1 is not None and value1 != "" and value1 != []
        elif operation == "larger":
            try:
                return float(value1) > float(value2)
            except (ValueError, TypeError):
                return False
        elif operation == "smaller":
            try:
                return float(value1) < float(value2)
            except (ValueError, TypeError):
                return False
        elif operation == "regex":
            try:
                return bool(re.search(str(value2), str(value1)))
            except re.error:
                return False
        else:
            return False
'''


def _generate_switch_helpers() -> str:
    """Generate Switch node helper methods."""
    return '''
    def _route_item(
        self,
        item: "NodeExecutionData",
        rules: List[Dict[str, Any]],
        fallback_output: int = -1,
    ) -> int:
        """
        Determine which output to route an item to.
        
        Args:
            item: The item to route
            rules: List of routing rules
            fallback_output: Output index for items matching no rules (-1 for drop)
        
        Returns:
            Output index (0-based)
        """
        for i, rule in enumerate(rules):
            conditions = rule.get("conditions", [])
            if self._evaluate_conditions(item, conditions):
                return rule.get("output", i)
        
        return fallback_output
    
    def _evaluate_conditions(
        self,
        item: "NodeExecutionData",
        conditions: List[Dict[str, Any]],
    ) -> bool:
        """Evaluate conditions for routing."""
        if not conditions:
            return True
        
        data = item.json_data or {}
        
        for cond in conditions:
            value1 = self._get_value(data, cond.get("value1", ""))
            operation = cond.get("operation", "equal")
            value2 = cond.get("value2", "")
            
            if not self._compare(value1, operation, value2):
                return False
        
        return True
    
    def _get_value(self, data: Dict, path: str) -> Any:
        """Get a value from data using dot notation path."""
        if not path:
            return None
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _compare(self, value1: Any, operation: str, value2: Any) -> bool:
        """Compare two values."""
        if operation == "equal":
            return str(value1) == str(value2)
        elif operation == "notEqual":
            return str(value1) != str(value2)
        elif operation == "contains":
            return str(value2) in str(value1)
        elif operation == "regex":
            try:
                return bool(re.search(str(value2), str(value1)))
            except re.error:
                return False
        else:
            return str(value1) == str(value2)
'''


def _generate_filter_helpers() -> str:
    """Generate Filter node helper methods."""
    return '''
    def _filter_items(
        self,
        items: List["NodeExecutionData"],
        conditions: List[Dict[str, Any]],
        combine_mode: str = "all",
    ) -> List["NodeExecutionData"]:
        """
        Filter items based on conditions.
        
        Args:
            items: Input items
            conditions: Filter conditions
            combine_mode: "all" (AND) or "any" (OR)
        
        Returns:
            Filtered items
        """
        result = []
        
        for item in items:
            if self._matches_conditions(item, conditions, combine_mode):
                result.append(item)
        
        return result
    
    def _matches_conditions(
        self,
        item: "NodeExecutionData",
        conditions: List[Dict[str, Any]],
        combine_mode: str,
    ) -> bool:
        """Check if item matches conditions."""
        if not conditions:
            return True
        
        data = item.json_data or {}
        results = []
        
        for cond in conditions:
            field = cond.get("field", "")
            operator = cond.get("operator", "equal")
            value = cond.get("value", "")
            
            field_value = self._get_nested_value(data, field)
            result = self._apply_operator(field_value, operator, value)
            results.append(result)
        
        if combine_mode == "all":
            return all(results)
        else:
            return any(results)
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value using dot notation."""
        if not path:
            return None
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
        
        return current
    
    def _apply_operator(self, value: Any, operator: str, compare_value: Any) -> bool:
        """Apply comparison operator."""
        if operator == "equal":
            return str(value) == str(compare_value)
        elif operator == "notEqual":
            return str(value) != str(compare_value)
        elif operator == "contains":
            return str(compare_value) in str(value)
        elif operator == "notContains":
            return str(compare_value) not in str(value)
        elif operator == "greaterThan":
            try:
                return float(value) > float(compare_value)
            except (ValueError, TypeError):
                return False
        elif operator == "lessThan":
            try:
                return float(value) < float(compare_value)
            except (ValueError, TypeError):
                return False
        elif operator == "isEmpty":
            return value is None or value == "" or value == []
        elif operator == "isNotEmpty":
            return value is not None and value != "" and value != []
        elif operator == "regex":
            try:
                return bool(re.search(str(compare_value), str(value)))
            except re.error:
                return False
        else:
            return False
'''


def _generate_set_helpers() -> str:
    """Generate Set node helper methods."""
    return '''
    def _set_field(
        self,
        data: Dict[str, Any],
        field_name: str,
        value: Any,
        use_dot_notation: bool = True,
    ) -> Dict[str, Any]:
        """
        Set a field in the data, supporting dot notation.
        
        Args:
            data: The data dictionary to modify
            field_name: Field name (may use dot notation)
            value: Value to set
            use_dot_notation: Whether to interpret dots as nesting
        
        Returns:
            Modified data
        """
        result = copy.deepcopy(data)
        
        if not use_dot_notation or "." not in field_name:
            result[field_name] = value
            return result
        
        parts = field_name.split(".")
        current = result
        
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        current[parts[-1]] = value
        return result
    
    def _remove_field(
        self,
        data: Dict[str, Any],
        field_name: str,
        use_dot_notation: bool = True,
    ) -> Dict[str, Any]:
        """
        Remove a field from the data.
        """
        result = copy.deepcopy(data)
        
        if not use_dot_notation or "." not in field_name:
            result.pop(field_name, None)
            return result
        
        parts = field_name.split(".")
        current = result
        
        for part in parts[:-1]:
            if part not in current:
                return result  # Path doesn't exist
            current = current[part]
        
        current.pop(parts[-1], None)
        return result
'''


def _generate_iterator_helpers() -> str:
    """Generate Iterator node helper methods."""
    return '''
    def _iterate_items(
        self,
        items: List["NodeExecutionData"],
        field: str | None = None,
    ) -> List["NodeExecutionData"]:
        """
        Iterate over items, optionally expanding array fields.
        
        Args:
            items: Input items
            field: If specified, iterate over this array field within each item
        
        Returns:
            Expanded items
        """
        if not field:
            # Just pass through items with index
            result = []
            for i, item in enumerate(items):
                data = copy.deepcopy(item.json_data or {})
                data["_itemIndex"] = i
                result.append(NodeExecutionData(json_data=data, binary_data=item.binary_data))
            return result
        
        # Expand array field
        result = []
        for item in items:
            data = item.json_data or {}
            array_value = self._get_nested_value(data, field)
            
            if isinstance(array_value, list):
                for i, element in enumerate(array_value):
                    new_data = copy.deepcopy(data)
                    new_data["_iteratedItem"] = element
                    new_data["_iterationIndex"] = i
                    result.append(NodeExecutionData(json_data=new_data, binary_data=None))
            else:
                # Not an array - pass through
                result.append(item)
        
        return result
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value using dot notation."""
        if not path:
            return None
        
        parts = path.split(".")
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
'''


def _generate_generic_transform_helpers(node_name: str) -> str:
    """Generate generic transform helpers."""
    return f'''
    def _transform_item(
        self,
        item: "NodeExecutionData",
        **kwargs,
    ) -> "NodeExecutionData":
        """
        Transform a single item.
        
        Override this method with node-specific logic.
        """
        # Default: pass through unchanged
        return item
    
    def _transform_items(
        self,
        items: List["NodeExecutionData"],
        **kwargs,
    ) -> List["NodeExecutionData"]:
        """
        Transform all items.
        """
        return [self._transform_item(item, **kwargs) for item in items]
'''
