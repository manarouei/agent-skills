import sys
import gc
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import copy
import logging
import traceback

logger = logging.getLogger(__name__)

class IteratorNode(BaseNode):
    """
    Iterator Node that loops through data items or arrays with memory management.
    Can iterate over input items one by one or through array fields within items.
    """
    type = "iterator"
    version = 1

    # Memory management constants
    MAX_MEMORY_BYTES = 64 * 1024 * 1024  # 64MB per iteration batch
    MAX_TOTAL_ITEMS = 10000  # Maximum items to process
    MEMORY_CHECK_INTERVAL = 100  # Check memory every N items
    LARGE_ITEM_THRESHOLD = 1024 * 1024  # 1MB per item warning

    description = {
        "displayName": "Iterator",
        "name": "iterator", 
        "group": ["transform"],
        "version": 1,
        "description": "Iterate through data items or arrays",
        "defaults": {
            "name": "Iterator",
            "color": "#FF6B6B"
        },
        "inputs": ["main"],
        "outputs": ["main"],
        "icon": "fa:repeat"
    }

    properties = {
        "parameters": [
            {
                "name": "iterationMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Iteration Mode",
                "description": "How to iterate through the data",
                "options": [
                    {
                        "name": "Each Item",
                        "value": "eachItem",
                        "description": "Iterate through each input item separately"
                    },
                    {
                        "name": "Array Field",
                        "value": "arrayField",
                        "description": "Iterate through values in an array field"
                    },
                    {
                        "name": "Object Properties",
                        "value": "objectProperties",
                        "description": "Iterate through object properties as key-value pairs"
                    },
                    {
                        "name": "Range",
                        "value": "range",
                        "description": "Iterate through a numeric range"
                    }
                ],
                "default": "eachItem",
                "required": True
            },
            {
                "name": "arrayField",
                "type": NodeParameterType.STRING,
                "display_name": "Array Field",
                "description": "Name of the field containing the array to iterate",
                "default": "items",
                "placeholder": "items",
                "display_options": {
                    "show": {
                        "iterationMode": ["arrayField"]
                    }
                },
                "required": True
            },
            {
                "name": "includeOriginalData",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Original Data",
                "description": "Whether to include the original item data with each iteration",
                "default": True,
                "display_options": {
                    "show": {
                        "iterationMode": ["arrayField", "objectProperties"]
                    }
                }
            },
            {
                "name": "outputFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Output Fields",
                "description": "Configure output field names",
                "default": {},
                "options": [
                    {
                        "name": "itemFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Item Field Name",
                        "description": "Name for the field containing the current iteration item",
                        "default": "item",
                        "placeholder": "currentItem"
                    },
                    {
                        "name": "indexFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Index Field Name",
                        "description": "Name for the field containing the current iteration index",
                        "default": "index",
                        "placeholder": "currentIndex"
                    }
                ]
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "description": "Additional iteration options",
                "default": {},
                "options": [
                    {
                        "name": "skipEmptyValues",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Skip Empty Values",
                        "description": "Skip null, undefined, or empty string values during iteration",
                        "default": False
                    },
                    {
                        "name": "maxIterations",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Iterations",
                        "description": "Maximum number of iterations (0 = no limit)",
                        "default": 0,
                        "min": 0
                    },
                    {
                        "name": "includeMetadata",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Include Metadata",
                        "description": "Include metadata about the iteration (total count, etc.)",
                        "default": False
                    },
                    {
                        "name": "flattenStructure",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Flatten Structure",
                        "description": "Flatten nested objects to avoid reserved keyword issues",
                        "default": False
                    },
                    {
                        "name": "enableMemoryManagement",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Enable Memory Management",
                        "description": "Enable automatic memory monitoring and limits",
                        "default": True
                    },
                    {
                        "name": "memoryLimitMB",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Memory Limit (MB)",
                        "description": "Memory limit in megabytes (0 = use default 64MB)",
                        "default": 0,
                        "min": 0
                    },
                    {
                        "name": "skipLargeItems",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Skip Large Items",
                        "description": "Skip items that exceed memory threshold",
                        "default": False
                    }
                ]
            },
            {
                "name": "rangeOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Range Options",
                "description": "Range iteration configuration",
                "display_options": {
                    "show": {
                        "iterationMode": ["range"]
                    }
                },
                "default": {},
                "options": [
                    {
                        "name": "rangeStart",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Start",
                        "description": "Starting number for range iteration",
                        "default": 0
                    },
                    {
                        "name": "rangeEnd",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "End",
                        "description": "Ending number for range iteration",
                        "default": 10
                    },
                    {
                        "name": "rangeStep",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Step",
                        "description": "Step size for range iteration",
                        "default": 1
                    }
                ]
            },
            {
                "name": "objectOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Object Options",
                "description": "Object properties iteration configuration",
                "display_options": {
                    "show": {
                        "iterationMode": ["objectProperties"]
                    }
                },
                "default": {},
                "options": [
                    {
                        "name": "objectField",
                        "type": NodeParameterType.STRING,
                        "display_name": "Object Field",
                        "description": "Name of the field containing the object to iterate",
                        "default": "data"
                    },
                    {
                        "name": "keyFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Key Field Name",
                        "description": "Name for the field containing the property key",
                        "default": "key"
                    },
                    {
                        "name": "valueFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Value Field Name",
                        "description": "Name for the field containing the property value",
                        "default": "value"
                    }
                ]
            },
            {
                "name": "batchProcessing",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Batch Processing",
                "description": "Configure batch processing options",
                "default": {},
                "options": [
                    {
                        "name": "enableBatching",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Enable Batching",
                        "description": "Process items in batches instead of individually",
                        "default": False
                    },
                    {
                        "name": "batchSize",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Batch Size",
                        "description": "Number of items per batch",
                        "default": 10,
                        "min": 1,
                        "displayOptions": {
                            "show": {
                                "enableBatching": [True]
                            }
                        }
                    },
                    {
                        "name": "batchMode",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Batch Mode",
                        "description": "How to structure the batches",
                        "options": [
                            {"name": "Array Field", "value": "arrayField", "description": "Put batch items in an array field"},
                            {"name": "Separate Items", "value": "separateItems", "description": "Keep items separate but group in batches"},
                            {"name": "Merge Objects", "value": "mergeObjects", "description": "Merge batch items into single objects"}
                        ],
                        "default": "arrayField",
                        "displayOptions": {
                            "show": {
                                "enableBatching": [True]
                            }
                        }
                    },
                    {
                        "name": "batchFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Batch Field Name",
                        "description": "Name of the field to store batch items",
                        "default": "batch",
                        "displayOptions": {
                            "show": {
                                "enableBatching": [True],
                                "batchMode": ["arrayField"]
                            }
                        }
                    }
                ]
            }
        ]
    }

    def _get_nested_param(self, param_path: str, item_index: int, default: Any = None) -> Any:
        """
        Get nested parameter using dot notation, compatible with get_node_parameter.
        """
        try:
            if '.' not in param_path:
                return self.get_node_parameter(param_path, item_index, default)
            parts = param_path.split('.')
            value = self.get_node_parameter(parts[0], item_index, {})
            for part in parts[1:]:
                if isinstance(value, dict):
                    value = value.get(part, default)
                elif hasattr(value, 'root'):
                    value = getattr(value, 'root', {}).get(part, default)
                else:
                    return default
            return value if value is not None else default
        except Exception as e:
            logger.error(f"Iterator Node - Error getting nested parameter '{param_path}': {str(e)}")
            return default

    def _calculate_item_size(self, item: NodeExecutionData) -> int:
        """Calculate approximate memory size of an item"""
        try:
            json_size = sys.getsizeof(item.json_data) if item.json_data else 0
            binary_size = sys.getsizeof(item.binary_data) if item.binary_data else 0
            return json_size + binary_size
        except:
            return 1024  # Fallback estimate

    def _log_largest_items(self, items: List[NodeExecutionData], top_n: int = 5) -> None:
        """Log the largest items for debugging"""
        try:
            item_sizes = [(i, self._calculate_item_size(item)) for i, item in enumerate(items)]
            largest_items = sorted(item_sizes, key=lambda x: x[1], reverse=True)[:top_n]
            
            for item_idx, size in largest_items:
                logger.error(f"Iterator Node - Large item #{item_idx}: {size:,} bytes")
                item = items[item_idx]
                if item.json_data:
                    for key, value in item.json_data.items():
                        field_size = sys.getsizeof(value)
                        if field_size > 100000:  # > 100KB
                            logger.error(f"Iterator Node - Large field '{key}': {field_size:,} bytes, type: {type(value)}")
        except Exception as e:
            logger.error(f"Iterator Node - Error logging largest items: {str(e)}")

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Iterator node logic with memory management and batch support"""
        try:
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("Iterator Node - No input data")
                return [[]]

            # Check if batching is enabled
            enable_batching = self._get_nested_param('batchProcessing.enableBatching', 0, False)
            
            if enable_batching:
                return self._execute_with_batching()
            else:
                return self._execute_individual_items()

        except Exception as e:
            logger.error(f"Iterator Node - Execution error: {str(e)}")
            return [[]]

    def _execute_with_batching(self) -> List[List[NodeExecutionData]]:
        """Execute with batch processing"""
        try:
            input_data = self.get_input_data()
            batch_size = self._get_nested_param('batchProcessing.batchSize', 0, 10)
            batch_mode = self._get_nested_param('batchProcessing.batchMode', 0, 'arrayField')
            batch_field_name = self._get_nested_param('batchProcessing.batchFieldName', 0, 'batch')
            
            iteration_mode = self.get_node_parameter("iterationMode", 0, "eachItem")
            
            # First, get all individual items based on iteration mode
            all_individual_items = []
            for item_index, item in enumerate(input_data):
                if iteration_mode == "eachItem":
                    items = self._iterate_each_item(item, item_index)
                elif iteration_mode == "arrayField":
                    items = self._iterate_array_field(item, item_index)
                elif iteration_mode == "objectProperties":
                    items = self._iterate_object_properties(item, item_index)
                elif iteration_mode == "range":
                    items = self._iterate_range(item, item_index)
                else:
                    continue
                
                all_individual_items.extend(items)
            
            # Now create batches
            batched_results = []
            for i in range(0, len(all_individual_items), batch_size):
                batch_items = all_individual_items[i:i + batch_size]
                
                if batch_mode == "arrayField":
                    # Put all batch items in an array field
                    batch_data = {
                        batch_field_name: [item.json_data for item in batch_items],
                        "batchIndex": i // batch_size,
                        "batchSize": len(batch_items),
                        "totalBatches": (len(all_individual_items) + batch_size - 1) // batch_size
                    }
                    batched_results.append(NodeExecutionData(json_data=batch_data))
                    
                elif batch_mode == "separateItems":
                    # Keep items separate but add batch metadata
                    for idx, item in enumerate(batch_items):
                        item_data = item.json_data.copy()
                        item_data["_batch"] = {
                            "batchIndex": i // batch_size,
                            "itemIndex": idx,
                            "batchSize": len(batch_items),
                            "totalBatches": (len(all_individual_items) + batch_size - 1) // batch_size
                        }
                        batched_results.append(NodeExecutionData(json_data=item_data))
                        
                elif batch_mode == "mergeObjects":
                    # Merge all batch items into a single object
                    merged_data = {
                        "batchIndex": i // batch_size,
                        "batchSize": len(batch_items),
                        "totalBatches": (len(all_individual_items) + batch_size - 1) // batch_size
                    }
                    for idx, item in enumerate(batch_items):
                        merged_data[f"item_{idx}"] = item.json_data
                    batched_results.append(NodeExecutionData(json_data=merged_data))
            
            return [batched_results]
            
        except Exception as e:
            logger.error(f"Iterator Node - Batch execution error: {str(e)}")
            return [[]]

    def _execute_individual_items(self) -> List[List[NodeExecutionData]]:
        """Execute with individual item processing (original logic)"""
        try:
            input_data = self.get_input_data()
            iteration_mode = self.get_node_parameter("iterationMode", 0, "eachItem")
            
            # Check memory management settings
            enable_memory_mgmt = self._get_nested_param('options.enableMemoryManagement', 0, True)
            memory_limit_mb = self._get_nested_param('options.memoryLimitMB', 0, 0)
            skip_large_items = self._get_nested_param('options.skipLargeItems', 0, False)
            
            if memory_limit_mb > 0:
                memory_limit = memory_limit_mb * 1024 * 1024
            else:
                memory_limit = self.MAX_MEMORY_BYTES

            all_results = []
            total_memory_used = 0

            for item_index, item in enumerate(input_data):
                try:
                    # Memory check before processing
                    if enable_memory_mgmt:
                        item_size = self._calculate_item_size(item)
                        if skip_large_items and item_size > self.LARGE_ITEM_THRESHOLD:
                            logger.warning(f"Iterator Node - Skipping large item #{item_index}: {item_size:,} bytes")
                            continue
                        
                        if total_memory_used + item_size > memory_limit:
                            logger.warning(f"Iterator Node - Memory limit reached at item #{item_index}")
                            break
                        
                        total_memory_used += item_size

                    # Process based on iteration mode
                    if iteration_mode == "eachItem":
                        items = self._iterate_each_item(item, item_index)
                    elif iteration_mode == "arrayField":
                        items = self._iterate_array_field(item, item_index)
                    elif iteration_mode == "objectProperties":
                        items = self._iterate_object_properties(item, item_index)
                    elif iteration_mode == "range":
                        items = self._iterate_range(item, item_index)
                    else:
                        logger.warning(f"Iterator Node - Unknown iteration mode: {iteration_mode}")
                        continue

                    all_results.extend(items)

                    # Memory cleanup every few iterations
                    if enable_memory_mgmt and item_index % self.MEMORY_CHECK_INTERVAL == 0:
                        gc.collect()

                except Exception as e:
                    logger.error(f"Iterator Node - Error processing item #{item_index}: {str(e)}")
                    continue

            # Final memory logging if enabled
            if enable_memory_mgmt and all_results:
                total_items = len(all_results)
                avg_size = total_memory_used / total_items if total_items > 0 else 0
                logger.info(f"Iterator Node - Processed {total_items} items, total memory: {total_memory_used:,} bytes, avg: {avg_size:.0f} bytes/item")
                
                # Log largest items if memory usage is high
                if total_memory_used > memory_limit * 0.8:
                    self._log_largest_items(all_results)

            return [all_results]

        except Exception as e:
            logger.error(f"Iterator Node - Individual execution error: {str(e)}")
            logger.error(f"Iterator Node - Traceback: {traceback.format_exc()}")
            return [[]]

    def _iterate_each_item(self, item: NodeExecutionData, item_index: int) -> List[NodeExecutionData]:
        """Iterate through each item separately (pass through with index)"""
        try:
            item_field_name = self._get_nested_param('outputFields.itemFieldName', item_index, 'item')
            index_field_name = self._get_nested_param('outputFields.indexFieldName', item_index, 'index')
            include_metadata = self._get_nested_param('options.includeMetadata', item_index, False)

            new_json_data = copy.deepcopy(item.json_data or {})
            new_json_data[item_field_name] = copy.deepcopy(item.json_data)
            new_json_data[index_field_name] = item_index

            if include_metadata:
                new_json_data["_iteration"] = {
                    "mode": "eachItem",
                    "index": item_index,
                    "total": 1
                }

            return [NodeExecutionData(
                json_data=new_json_data,
                binary_data=copy.deepcopy(item.binary_data)
            )]

        except Exception as e:
            logger.error(f"Iterator Node - Error in each item iteration: {str(e)}")
            return []

    def _iterate_array_field(self, item: NodeExecutionData, item_index: int) -> List[NodeExecutionData]:
        """Iterate through values in an array field with all original functionality"""
        try:
            # Get ALL the original parameters
            array_field = self.get_node_parameter("arrayField", item_index, "items")
            include_original = self.get_node_parameter("includeOriginalData", item_index, True)
            item_field_name = self._get_nested_param('outputFields.itemFieldName', item_index, 'item')
            index_field_name = self._get_nested_param('outputFields.indexFieldName', item_index, 'index')
            skip_empty = self._get_nested_param('options.skipEmptyValues', item_index, False)
            max_iterations = self._get_nested_param('options.maxIterations', item_index, 0)
            include_metadata = self._get_nested_param('options.includeMetadata', item_index, False)
            flatten_structure = self._get_nested_param('options.flattenStructure', item_index, False)

            # Handle the array data extraction (your existing logic)
            if array_field in item.json_data:
                field_value = item.json_data[array_field]
                if isinstance(field_value, dict):
                    # If it's a dict with one key that contains the array, use that
                    for key, val in field_value.items():
                        if isinstance(val, list):
                            array_data = val
                            break
                    else:
                        logger.warning(f"Iterator Node - No array found inside the dict")
                        return []
                else:
                    array_data = self._get_nested_value(item.json_data, array_field)
            else:
                # Try to get from body.result directly
                array_data = self._get_nested_value(item.json_data, 'body.result')

            if not isinstance(array_data, list):
                # Last attempt: look for any array in the data
                array_data = self._find_first_array(item.json_data)
                if not array_data:
                    logger.warning("Iterator Node - No arrays found in the data")
                    return []

            # Memory management: limit array size if needed
            original_length = len(array_data)
            enable_memory_mgmt = self._get_nested_param('options.enableMemoryManagement', item_index, True)
            if enable_memory_mgmt and original_length > self.MAX_TOTAL_ITEMS:
                logger.warning(f"Iterator Node - Large array detected: {original_length} items, limiting to {self.MAX_TOTAL_ITEMS}")
                array_data = array_data[:self.MAX_TOTAL_ITEMS]

            result_items = []
            iteration_count = 0
            current_batch_size = 0

            for index, array_item in enumerate(array_data):
                if skip_empty and self._is_empty_value(array_item):
                    continue
                if max_iterations and max_iterations > 0 and iteration_count >= max_iterations:
                    break

                # Memory check for large arrays
                if enable_memory_mgmt and index % 100 == 0 and result_items:
                    current_batch_size = sum(self._calculate_item_size(r) for r in result_items)
                    if current_batch_size > self.MAX_MEMORY_BYTES:
                        logger.warning(f"Iterator Node - Array iteration memory limit reached at index {index}")
                        break

                if include_original:
                    new_json_data = copy.deepcopy(item.json_data)
                else:
                    new_json_data = {}

                # Store the current item with all your original logic
                if flatten_structure and isinstance(array_item, dict):
                    # Flatten the structure to avoid reserved keyword issues
                    flattened_item = self._flatten_object(array_item)
                    new_json_data[item_field_name] = flattened_item
                    
                    # Also add commonly accessed fields directly to root for easier access
                    if 'message' in array_item:
                        message = array_item['message']
                        if isinstance(message, dict):
                            new_json_data['message_text'] = message.get('text', '')
                            new_json_data['message_chat_type'] = message.get('chat', {}).get('type', '')
                            
                            # Handle the 'from' field safely
                            from_data = message.get('from', {})
                            if isinstance(from_data, dict):
                                new_json_data['message_from_first_name'] = from_data.get('first_name', '')
                                new_json_data['message_from_last_name'] = from_data.get('last_name', '')
                                new_json_data['message_from_id'] = from_data.get('id', '')
                    
                    if 'update_id' in array_item:
                        new_json_data['update_id'] = array_item['update_id']
                else:
                    new_json_data[item_field_name] = copy.deepcopy(array_item)

                new_json_data[index_field_name] = index

                if include_metadata:
                    new_json_data["_iteration"] = {
                        "mode": "arrayField",
                        "field": array_field,
                        "index": index,
                        "total": len(array_data),
                        "originalTotal": original_length
                    }

                result_items.append(NodeExecutionData(
                    json_data=new_json_data,
                    binary_data=copy.deepcopy(item.binary_data)
                ))

                iteration_count += 1

            return result_items

        except Exception as e:
            logger.error(f"Iterator Node - Error in array field iteration: {str(e)}")
            logger.error(f"Iterator Node - Traceback: {traceback.format_exc()}")
            return []

    def _iterate_object_properties(self, item: NodeExecutionData, item_index: int) -> List[NodeExecutionData]:
        """Iterate through object properties as key-value pairs"""
        try:
            # Get all required parameters
            object_field = self._get_nested_param('objectOptions.objectField', item_index, 'data')
            include_original = self.get_node_parameter('includeOriginalData', item_index, True)
            key_field_name = self._get_nested_param('objectOptions.keyFieldName', item_index, 'key')
            value_field_name = self._get_nested_param('objectOptions.valueFieldName', item_index, 'value')
            index_field_name = self._get_nested_param('outputFields.indexFieldName', item_index, 'index')
            skip_empty = self._get_nested_param('options.skipEmptyValues', item_index, False)
            max_iterations = self._get_nested_param('options.maxIterations', item_index, 0)
            include_metadata = self._get_nested_param('options.includeMetadata', item_index, False)

            object_data = item.json_data.get(object_field, {})

            if not isinstance(object_data, dict):
                logger.warning(f"Iterator Node - Field '{object_field}' is not an object")
                return []

            result_items = []
            iteration_count = 0

            for index, (key, value) in enumerate(object_data.items()):
                if skip_empty and self._is_empty_value(value):
                    continue
                if max_iterations > 0 and iteration_count >= max_iterations:
                    break

                if include_original:
                    new_json_data = copy.deepcopy(item.json_data)
                else:
                    new_json_data = {}

                new_json_data[key_field_name] = key
                new_json_data[value_field_name] = copy.deepcopy(value)
                new_json_data[index_field_name] = index

                if include_metadata:
                    new_json_data["_iteration"] = {
                        "mode": "objectProperties",
                        "field": object_field,
                        "index": index,
                        "total": len(object_data)
                    }

                result_items.append(NodeExecutionData(
                    json_data=new_json_data,
                    binary_data=copy.deepcopy(item.binary_data)
                ))

                iteration_count += 1

            return result_items

        except Exception as e:
            logger.error(f"Iterator Node - Error in object properties iteration: {str(e)}")
            return []

    def _iterate_range(self, item: NodeExecutionData, item_index: int) -> List[NodeExecutionData]:
        """Iterate through a numeric range"""
        try:
            # Get all required parameters
            start = self._get_nested_param('rangeOptions.rangeStart', item_index, 0)
            end = self._get_nested_param('rangeOptions.rangeEnd', item_index, 10)
            step = self._get_nested_param('rangeOptions.rangeStep', item_index, 1)
            item_field_name = self._get_nested_param('outputFields.itemFieldName', item_index, 'item')
            index_field_name = self._get_nested_param('outputFields.indexFieldName', item_index, 'index')
            max_iterations = self._get_nested_param('options.maxIterations', item_index, 0)
            include_metadata = self._get_nested_param('options.includeMetadata', item_index, False)

            if step == 0:
                logger.error("Iterator Node - Range step cannot be zero")
                return []

            result_items = []
            iteration_count = 0
            current = start
            index = 0

            while (step > 0 and current < end) or (step < 0 and current > end):
                if max_iterations > 0 and iteration_count >= max_iterations:
                    break

                new_json_data = copy.deepcopy(item.json_data or {})
                new_json_data[item_field_name] = current
                new_json_data[index_field_name] = index

                if include_metadata:
                    total_iterations = abs((end - start) // step) if step != 0 else 0
                    new_json_data["_iteration"] = {
                        "mode": "range",
                        "start": start,
                        "end": end,
                        "step": step,
                        "index": index,
                        "total": int(total_iterations)
                    }

                result_items.append(NodeExecutionData(
                    json_data=new_json_data,
                    binary_data=copy.deepcopy(item.binary_data)
                ))

                current += step
                index += 1
                iteration_count += 1

            return result_items

        except Exception as e:
            logger.error(f"Iterator Node - Error in range iteration: {str(e)}")
            return []

    def _flatten_object(self, obj: Dict[str, Any], prefix: str = '', max_depth: int = 3) -> Dict[str, Any]:
        """
        Flatten nested object to avoid reserved keyword issues
        """
        if max_depth <= 0:
            return obj
        
        flattened = {}
        
        for key, value in obj.items():
            # Replace reserved keywords and special characters
            safe_key = self._make_safe_key(key)
            new_key = f"{prefix}_{safe_key}" if prefix else safe_key
            
            if isinstance(value, dict) and max_depth > 1:
                # Recursively flatten nested objects
                nested = self._flatten_object(value, new_key, max_depth - 1)
                flattened.update(nested)
            else:
                flattened[new_key] = value
        
        return flattened

    def _make_safe_key(self, key: str) -> str:
        """
        Convert potentially problematic keys to safe ones
        """
        # Handle Python reserved keywords
        reserved_keywords = {
            'from': 'from_field',
            'to': 'to_field', 
            'class': 'class_field',
            'def': 'def_field',
            'if': 'if_field',
            'else': 'else_field',
            'for': 'for_field',
            'while': 'while_field',
            'import': 'import_field',
            'return': 'return_field'
        }
        
        if key in reserved_keywords:
            return reserved_keywords[key]
        
        # Replace special characters that might cause issues
        safe_key = key.replace('-', '_').replace(' ', '_').replace('.', '_')
        
        return safe_key

    def _find_first_array(self, data: Dict[str, Any]) -> Optional[List[Any]]:
        """Find the first array in the data structure"""
        if not isinstance(data, dict):
            return None
        
        # Check direct fields first
        for key, value in data.items():
            if isinstance(value, list):
                return value
        
        # Check nested structures
        for key, value in data.items():
            if isinstance(value, dict):
                nested_array = self._find_first_array(value)
                if nested_array:
                    return nested_array
        
        return None

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """
        Get nested value from dictionary using dot notation path
        """
        if not path:
            return data
        if not data:
            logger.warning(f"Iterator Node - No data provided for path '{path}'")
            return None
        keys = path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current

    def _is_empty_value(self, value: Any) -> bool:
        """Check if a value is considered empty"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False


