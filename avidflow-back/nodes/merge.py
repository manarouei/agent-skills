from typing import Dict, Any, List, Optional, Union
from models import NodeExecutionData
from .base import BaseNode, NodeParameter, NodeParameterType, NodeRunMode
import copy


class MergeNode(BaseNode):
    """
    Merge Node combines data from multiple inputs in different ways:
    - Append mode: combines items from all inputs into a single output
    - Merge by key: joins items from different inputs based on matching key values
    - Multiplex by: Creates all possible item combinations from different inputs
    """
    
    type = "merge"
    version = 1
    
    description = {
        "displayName": "Merge",
        "name": "merge",
        "group": ["transform"],
        "inputs": [
            {"name": "main", "type": "main", "required": True, "maxConnections": 10},  # Allow up to 10 inputs
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "numberInputs",
                "type": NodeParameterType.NUMBER,
                "display_name": "Number of Inputs",
                "description": "How many inputs the node should have",
                "default": 2,
                "min": 2,
                "max": 10,
                "required": True,
            },
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "default": "append",
                "required": True,
                "display_name": "Mode",
                "description": "How data from different inputs should be combined",
                "options": [
                    {
                        "name": "Append",
                        "value": "append",
                        "description": "Combine items from all inputs sequentially",
                    },
                    {
                        "name": "Combine",
                        "value": "combine",
                        "description": "Merge items together from different inputs",
                    },
                    {
                        "name": "Merge By Key",
                        "value": "mergeByKey",
                        "description": "Join items from inputs based on matching keys",
                    },
                    {
                        "name": "Multiplex",
                        "value": "multiplex",
                        "description": "Create all possible combinations from inputs (cross product)",
                    }
                ]
            },
            {
                "name": "mergeByKey",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Merge Options",
                "description": "Options to configure the merge by key operation",
                "display_options": {
                    "show": {
                        "mode": ["mergeByKey"]
                    }
                },
                "options": [
                    {
                        "name": "matchKey",
                        "type": NodeParameterType.STRING,
                        "display_name": "Match Key",
                        "description": "Key to match items from different inputs",
                        "placeholder": "id",
                        "required": True,
                    },
                    {
                        "name": "joinMode",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Join Mode",
                        "description": "Type of join to perform",
                        "options": [
                            {
                                "name": "Inner Join (only matching items)",
                                "value": "inner",
                            },
                            {
                                "name": "Left Join (all items from input 1)",
                                "value": "left",
                            },
                            {
                                "name": "Outer Join (all items from both inputs)",
                                "value": "outer",
                            }
                        ],
                        "default": "inner",
                    }
                ]
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "description": "Additional options",
                "default": {},
                "options": [
                    {
                        "name": "outputPrefix",
                        "type": NodeParameterType.STRING,
                        "display_name": "Output Prefix",
                        "description": "Add prefix to all merged items",
                        "default": "",
                    },
                    {
                        "name": "keepMissingItems",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Keep Missing Items",
                        "description": "Include items that don't have a match",
                        "default": False,
                    }
                ]
            },
            {
                "name": "combineMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Combination Mode",
                "description": "How to combine the data from inputs",
                "display_options": {
                    "show": {
                        "mode": ["combine"]
                    }
                },
                "options": [
                    {
                        "name": "Merge By Position",
                        "value": "mergeByPosition",
                        "description": "Combine items based on their order",
                    },
                    {
                        "name": "Merge By Fields",
                        "value": "mergeByFields",
                        "description": "Combine items with the same field values",
                    }
                ],
                "default": "mergeByPosition",
            },
            {
                "name": "mergeFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Fields to Match",
                "description": "Configure which fields should be matched between inputs",
                "display_options": {
                    "show": {
                        "mode": ["combine"],
                        "combineMode": ["mergeByFields"]
                    }
                },
                "options": [
                    {
                        "name": "field1",
                        "type": NodeParameterType.STRING,
                        "display_name": "Input 1 Field",
                        "description": "Field to match from first input",
                        "required": True,
                        "placeholder": "id",
                    },
                    {
                        "name": "field2",
                        "type": NodeParameterType.STRING,
                        "display_name": "Input 2 Field",
                        "description": "Field to match from second input",
                        "required": True,
                        "placeholder": "id",
                    }
                ]
            },
        ]
    }
    
    icon = "fa:object-group"
    color = "#00aaff"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the merge operation based on selected mode"""
        try:
            # Get mode and number of inputs from parameters
            mode = self.get_parameter("mode", 0, "append")
            number_inputs = self.get_parameter("numberInputs", 0, 2)

            # Get data from all inputs
            all_input_data = []
            for i in range(number_inputs):
                input_data = self.get_input_data(i, "main") or []
                all_input_data.append(input_data)
            
            # Process based on merge mode
            if mode == "append":
                output_data = self._merge_append(all_input_data)
            elif mode == "mergeByKey":
                output_data = self._merge_by_key(all_input_data)
            elif mode == "multiplex":
                output_data = self._merge_multiplex(all_input_data)
            elif mode == "combine":
                output_data = self._combine(all_input_data)
            else:
                result_items = [NodeExecutionData(**{'json_data': {"error": f"Unsupported merge mode: {mode}"}, 'binary_data': None})]
                return [result_items]
            
            return [output_data]
            
        except Exception as e:
            return [[NodeExecutionData(**{'json_data': {"error": f"Error in Merge node: {str(e)}"}, 'binary_data': None})]]

    def _merge_append(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Simply concatenate items from all inputs"""
        output_items = []
        
        for input_data in all_input_data:
            # Convert NodeExecutionData to dict and append
            for item in input_data:
                if hasattr(item, 'json_data'):
                    # Create new NodeExecutionData with copied data
                    output_items.append(NodeExecutionData(
                        json_data=copy.deepcopy(item.json_data),
                        binary_data=copy.deepcopy(item.binary_data) if hasattr(item, 'binary_data') else None
                    ))
                else:
                    # If it's already a dict, wrap it in NodeExecutionData
                    output_items.append(NodeExecutionData(
                        json_data=copy.deepcopy(item),
                        binary_data=None
                    ))
        
        return output_items
    
    def _merge_by_key(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Merge items from all inputs based on a common key"""
        if not all_input_data or len(all_input_data) < 2:
            return []
        
        # Get merge options
        merge_options = self.get_parameter("mergeByKey", {})
        match_key = merge_options.get("matchKey", "id")
        join_mode = merge_options.get("joinMode", "inner")
        
        # Start with first input as base
        result_items = []
        for item in all_input_data[0]:
            json_data = item.json_data if hasattr(item, 'json_data') else item
            result_items.append({
                'data': copy.deepcopy(json_data),
                'binary': copy.deepcopy(item.binary_data) if hasattr(item, 'binary_data') else None,
                'key': json_data.get(match_key)
            })
        
        # Merge with each subsequent input
        for input_index in range(1, len(all_input_data)):
            input_data = all_input_data[input_index]
            
            # Create lookup for this input
            input_lookup = {}
            for item in input_data:
                json_data = item.json_data if hasattr(item, 'json_data') else item
                key_value = json_data.get(match_key)
                if key_value is not None:
                    input_lookup[key_value] = json_data
            
            # Merge with existing results
            new_result_items = []
            processed_keys = set()
            
            for result_item in result_items:
                key_value = result_item['key']
                processed_keys.add(key_value)
                
                if key_value in input_lookup:
                    # Merge the data
                    merged_data = copy.deepcopy(result_item['data'])
                    
                    # Add data from current input (skip match key to avoid duplication)
                    for k, v in input_lookup[key_value].items():
                        if k != match_key:
                            merged_data[k] = copy.deepcopy(v)
                    
                    new_result_items.append({
                        'data': merged_data,
                        'binary': result_item['binary'],
                        'key': key_value
                    })
                elif join_mode in ["left", "outer"]:
                    # Keep the item even without a match
                    new_result_items.append(result_item)
            
            # For outer join, add unmatched items from current input
            if join_mode == "outer":
                for key_value, item_data in input_lookup.items():
                    if key_value not in processed_keys:
                        new_result_items.append({
                            'data': copy.deepcopy(item_data),
                            'binary': None,
                            'key': key_value
                        })
            
            result_items = new_result_items
        
        # Convert back to NodeExecutionData
        output_items = []
        for item in result_items:
            output_items.append(NodeExecutionData(
                json_data=item['data'],
                binary_data=item['binary']
            ))
        
        return output_items
    
    def _merge_multiplex(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Create all possible combinations between items from all inputs"""
        # Filter out empty inputs
        non_empty_inputs = [input_data for input_data in all_input_data if input_data]
        
        if not non_empty_inputs:
            return []
        
        # Convert NodeExecutionData to dict format for easier processing
        processed_inputs = []
        for input_data in non_empty_inputs:
            processed_input = []
            for item in input_data:
                if hasattr(item, 'json_data'):
                    processed_input.append({
                        'data': item.json_data,
                        'binary': item.binary_data if hasattr(item, 'binary_data') else None
                    })
                else:
                    processed_input.append({
                        'data': item,
                        'binary': None
                    })
            processed_inputs.append(processed_input)
        
        # Generate all combinations using itertools.product
        import itertools
        output_items = []
        options = self.get_parameter("options", {})
        output_prefix = options.get("outputPrefix", "")
        
        for combination in itertools.product(*processed_inputs):
            # Merge all items in this combination
            merged_data = {}
            merged_binary = None
            
            for input_index, item in enumerate(combination):
                item_data = item['data']
                
                # Use the first item's binary data, or prefer non-None binary data
                if merged_binary is None and item['binary'] is not None:
                    merged_binary = copy.deepcopy(item['binary'])
                
                # Add data with optional prefix for inputs after the first
                for k, v in item_data.items():
                    if input_index == 0:
                        # First input: use keys as-is
                        key_name = k
                    else:
                        # Subsequent inputs: add prefix or suffix
                        if output_prefix:
                            key_name = f"{output_prefix}{k}"
                        else:
                            key_name = f"{k}_{input_index + 1}" if k in merged_data else k
                    
                    merged_data[key_name] = copy.deepcopy(v)
            
            output_items.append(NodeExecutionData(
                json_data=merged_data,
                binary_data=merged_binary
            ))
        
        return output_items
    
    def _combine(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Combine data from inputs based on position or fields"""
        if not all_input_data or len(all_input_data) < 2:
            return []
        
        # Get combine mode
        combine_mode = self.get_parameter("combineMode", 0, "mergeByPosition")
        
        if combine_mode == "mergeByPosition":
            return self._combine_by_position(all_input_data)
        elif combine_mode == "mergeByFields":
            return self._combine_by_fields(all_input_data)
        else:
            return [NodeExecutionData(**{'json_data': {"error": f"Unsupported combine mode: {combine_mode}"}, 'binary_data': None})]
    
    def _combine_by_position(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Combine items based on their position in each input"""
        output_items = []
        
        # Get the maximum number of items from all inputs
        max_items = max((len(input_data) for input_data in all_input_data), default=0)
        
        # Iterate through positions
        for i in range(max_items):
            merged_data = {}
            merged_binary = None
            
            # Go through each input
            for input_index, input_data in enumerate(all_input_data):
                # Skip if this input doesn't have an item at this position
                if i >= len(input_data):
                    continue
                
                # Get the item at this position
                item = input_data[i]
                item_data = item.json_data if hasattr(item, 'json_data') else item
                item_binary = item.binary_data if hasattr(item, 'binary_data') else None
                
                # Use first available binary data
                if merged_binary is None and item_binary is not None:
                    merged_binary = copy.deepcopy(item_binary)
                
                # Merge data
                for key, value in item_data.items():
                    merged_data[key] = copy.deepcopy(value)
            
            # Add merged item
            if merged_data:
                output_items.append(NodeExecutionData(
                    json_data=merged_data,
                    binary_data=merged_binary
                ))
        
        return output_items
    
    def _combine_by_fields(self, all_input_data: List[List[NodeExecutionData]]) -> List[NodeExecutionData]:
        """Combine items that have matching field values"""
        if not all_input_data or len(all_input_data) < 2:
            return []
        
        # Get merge fields
        merge_fields = self.get_parameter("mergeFields", {})
        field1 = merge_fields.get("field1", "id")
        field2 = merge_fields.get("field2", "id")
        
        # Process first input
        output_items = []
        input1_data = all_input_data[0]
        input2_data = all_input_data[1]
        
        # Create lookup for second input
        input2_lookup = {}
        for item in input2_data:
            item_data = item.json_data if hasattr(item, 'json_data') else item
            key_value = item_data.get(field2)
            if key_value is not None:
                input2_lookup[key_value] = item
        
        # Merge matching items
        for item1 in input1_data:
            item1_data = item1.json_data if hasattr(item1, 'json_data') else item1
            item1_binary = item1.binary_data if hasattr(item1, 'binary_data') else None
            key_value = item1_data.get(field1)
            
            if key_value is not None and key_value in input2_lookup:
                # Found a match, merge the items
                item2 = input2_lookup[key_value]
                item2_data = item2.json_data if hasattr(item2, 'json_data') else item2
                item2_binary = item2.binary_data if hasattr(item2, 'binary_data') else None
                
                # Create merged data
                merged_data = copy.deepcopy(item1_data)
                for key, value in item2_data.items():
                    # Avoid overwriting the match field if they have the same name
                    if key != field2 or field1 != field2:
                        merged_data[key] = copy.deepcopy(value)
                
                # Use binary data from first item or second if first is None
                binary_data = copy.deepcopy(item1_binary) if item1_binary is not None else copy.deepcopy(item2_binary)
                
                output_items.append(NodeExecutionData(
                    json_data=merged_data,
                    binary_data=binary_data
                ))
        
        return output_items