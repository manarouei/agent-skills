import sys
import os
import base64
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import json
import copy
import logging

logger = logging.getLogger(__name__)

class SetNode(BaseNode):
    """
    Set node that modifies, adds, or removes item fields.
    Equivalent to n8n's Edit Fields (Set) node.
    """
    
    type = "set"
    version = 1
    
    # Memory management constants for files
    MAX_BINARY_SIZE = 50 * 1024 * 1024  # 50MB max per binary field
    MAX_TOTAL_MEMORY = 200 * 1024 * 1024  # 200MB max total memory
    LARGE_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB warning threshold
    
    description = {
        "displayName": "Edit Fields (Set)",
        "name": "set", 
        "group": ["input"],
        "inputs": [
            {"name": "main", "type": "main", "required": True},
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True},
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "mode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Mode",
                "description": "How to modify the data",
                "options": [
                    {
                        "name": "Manual Mapping",
                        "value": "manual",
                        "description": "Edit item fields one by one"
                    },
                    {
                        "name": "JSON",
                        "value": "raw",
                        "description": "Customize item output with JSON"
                    }
                ],
                "default": "manual"
            },
            {
                "name": "duplicateItem",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Duplicate Item",
                "default": False,
                "description": "Whether to duplicate items (for testing)"
            },
            {
                "name": "duplicateCount",
                "type": NodeParameterType.NUMBER,
                "display_name": "Duplicate Item Count",
                "default": 0,
                "description": "How many times the item should be duplicated",
                "display_options": {
                    "show": {
                        "duplicateItem": [True]
                    }
                }
            },
            # Manual mode parameters
            {
                "name": "fields",
                "type": NodeParameterType.ARRAY,
                "display_name": "Fields to Set",
                "default": [],
                "description": "Define the fields to set in manual mode",
                "display_options": {
                    "show": {
                        "mode": ["manual"]
                    }
                },
                "options": [
                    {
                        "name": "name",
                        "type": NodeParameterType.STRING,
                        "display_name": "Name",
                        "placeholder": "field_name",
                        "description": "Name of the field to set",
                        "required": True
                    },
                    {
                        "name": "type",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Type",
                        "options": [
                            {"name": "String", "value": "stringValue"},
                            {"name": "Number", "value": "numberValue"},
                            {"name": "Boolean", "value": "booleanValue"},
                            {"name": "Array", "value": "arrayValue"},
                            {"name": "Object", "value": "objectValue"},
                            {"name": "Binary", "value": "binaryValue"}
                        ],
                        "default": "stringValue"
                    },
                    {
                        "name": "stringValue",
                        "type": NodeParameterType.STRING,
                        "display_name": "Value",
                        "default": "",
                        "placeholder": "field value",
                        "display_options": {
                            "show": {
                                "type": ["stringValue"]
                            }
                        }
                    },
                    {
                        "name": "numberValue",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Value",
                        "default": 0,
                        "display_options": {
                            "show": {
                                "type": ["numberValue"]
                            }
                        }
                    },
                    {
                        "name": "booleanValue",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Value",
                        "default": False,
                        "display_options": {
                            "show": {
                                "type": ["booleanValue"]
                            }
                        }
                    },
                    {
                        "name": "arrayValue",
                        "type": NodeParameterType.STRING,
                        "display_name": "Value",
                        "default": "[]",
                        "placeholder": "[1, 2, 3] or ['a', 'b', 'c']",
                        "display_options": {
                            "show": {
                                "type": ["arrayValue"]
                            }
                        }
                    },
                    {
                        "name": "objectValue",
                        "type": NodeParameterType.JSON,
                        "display_name": "Value",
                        "default": "{}",
                        "placeholder": '{"key": "value"}',
                        "display_options": {
                            "show": {
                                "type": ["objectValue"]
                            }
                        }
                    },
                    {
                        "name": "binaryKey",
                        "type": NodeParameterType.STRING,
                        "display_name": "Binary Property Key",
                        "default": "data",
                        "placeholder": "Enter binary key to set or copy",
                        "display_options": { "show": { "type": ["binaryValue"] } }
                    },
                    {
                        "name": "binaryBase64",
                        "type": NodeParameterType.STRING,
                        "display_name": "Base64 Encoded Data",
                        "default": "",
                        "placeholder": "Base64 encoded content",
                        "description": "Base64 encoded data to decode into binary",
                        "display_options": { "show": { "type": ["binaryValue"] } }
                    },
                    {
                        "name": "filename",
                        "type": NodeParameterType.STRING,
                        "display_name": "Filename",
                        "default": "file.bin",
                        "placeholder": "file.txt",
                        "display_options": { "show": { "type": ["binaryValue"] } }
                    },
                    {
                        "name": "mimeType",
                        "type": NodeParameterType.STRING,
                        "display_name": "MIME Type",
                        "default": "application/octet-stream",
                        "placeholder": "application/pdf",
                        "display_options": { "show": { "type": ["binaryValue"] } }
                    }
                ]
            },
            # Raw mode parameters  
            {
                "name": "jsonOutput",
                "type": NodeParameterType.JSON,
                "display_name": "JSON Output",
                "default": "{}",
                "description": "JSON object to output. Can use expressions.",
                "display_options": {
                    "show": {
                        "mode": ["raw"]
                    }
                }
            },
            # Include options for raw mode
            {
                "name": "includeOtherFields",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Other Input Fields",
                "default": False,
                "description": "Whether to pass all input fields to output",
                "display_options": {
                    "show": {
                        "mode": ["raw"]
                    }
                }
            },
            {
                "name": "include",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Input Fields to Include",
                "options": [
                    {
                        "name": "All",
                        "value": "all",
                        "description": "Include all unchanged fields from input"
                    },
                    {
                        "name": "Selected",
                        "value": "selected",
                        "description": "Include only specified fields"
                    },
                    {
                        "name": "All Except",
                        "value": "except",
                        "description": "Exclude specified fields"
                    }
                ],
                "default": "all",
                "display_options": {
                    "show": {
                        "mode": ["raw"],
                        "includeOtherFields": [True]
                    }
                }
            },
            {
                "name": "includeFields",
                "type": NodeParameterType.STRING,
                "display_name": "Fields to Include",
                "default": "",
                "placeholder": "field1,field2,field3",
                "description": "Comma-separated list of fields to include",
                "display_options": {
                    "show": {
                        "mode": ["raw"],
                        "includeOtherFields": [True],
                        "include": ["selected"]
                    }
                }
            },
            {
                "name": "excludeFields",
                "type": NodeParameterType.STRING,
                "display_name": "Fields to Exclude", 
                "default": "",
                "placeholder": "field1,field2,field3",
                "description": "Comma-separated list of fields to exclude",
                "display_options": {
                    "show": {
                        "mode": ["raw"],
                        "includeOtherFields": [True],
                        "include": ["except"]
                    }
                }
            },
            # Options collection - always visible
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "description": "Additional configuration options",
                "options": [
                    {
                        "name": "ignoreConversionErrors",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Ignore Type Conversion Errors",
                        "default": False,
                        "description": "Whether to ignore field type errors"
                    },
                ]
            },
            {
                "name": "memoryOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Memory Management",
                "default": {},
                "description": "Configure memory and file size limits",
                "options": [
                    {
                        "name": "enableMemoryTracking",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Enable Memory Tracking",
                        "default": True,
                        "description": "Track memory usage for large files and data"
                    },
                    {
                        "name": "maxBinarySize",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Binary File Size (MB)",
                        "default": 50,
                        "description": "Maximum size for individual binary files in MB"
                    },
                    {
                        "name": "skipLargeBinaries",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Skip Large Binary Files",
                        "default": False,
                        "description": "Skip binary fields that exceed size limit"
                    },
                    {
                        "name": "compressLargeData",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Compress Large Data",
                        "default": False,
                        "description": "Attempt to compress large JSON data"
                    }
                ]
            }
        ]
    }
    
    icon = "fa:edit"
    color = "#0066CC"
    
    def _calculate_memory_usage(self, item: NodeExecutionData) -> Dict[str, int]:
        """Calculate detailed memory usage for an item"""
        memory_info = {
            "json_size": 0,
            "binary_size": 0,
            "binary_files": 0,
            "total_size": 0,
            "large_files": []
        }
        
        try:
            # Calculate JSON data size
            if item.json_data:
                json_str = json.dumps(item.json_data, default=str)
                memory_info["json_size"] = len(json_str.encode('utf-8'))
            
            # Calculate binary data size
            if item.binary_data:
                for key, binary_item in item.binary_data.items():
                    file_size = 0
                    
                    if isinstance(binary_item, dict):
                        # Calculate base64 data size
                        if 'data' in binary_item:
                            data = binary_item['data']
                            if isinstance(data, str):
                                # Base64 encoded - calculate actual size
                                file_size = len(data) * 3 // 4
                            else:
                                file_size = sys.getsizeof(data)
                        
                        # Add metadata size
                        metadata_size = sum(
                            sys.getsizeof(v) for k, v in binary_item.items() 
                            if k != 'data'
                        )
                        file_size += metadata_size
                        
                        memory_info["binary_size"] += file_size
                        memory_info["binary_files"] += 1
                        
                        # Track large files
                        if file_size > self.LARGE_FILE_THRESHOLD:
                            memory_info["large_files"].append({
                                "key": key,
                                "size": file_size,
                                "filename": binary_item.get("filename", "unknown")
                            })
                    
                    else:
                        file_size = sys.getsizeof(binary_item)
                        memory_info["binary_size"] += file_size
                        memory_info["binary_files"] += 1
            
            memory_info["total_size"] = memory_info["json_size"] + memory_info["binary_size"]
            
        except Exception as e:
            logger.warning(f"Set Node - Memory calculation error: {str(e)}")
        
        return memory_info

    def _check_memory_limits(self, memory_info: Dict[str, int], options: Dict[str, Any]) -> bool:
        """Check if memory usage exceeds limits"""
        if not options.get("enableMemoryTracking", True):
            return True
        
        max_binary_mb = options.get("maxBinarySize", 50)
        max_binary_size = max_binary_mb * 1024 * 1024
        
        # Check individual large files
        for large_file in memory_info.get("large_files", []):
            if large_file["size"] > max_binary_size:
                if options.get("skipLargeBinaries", False):
                    logger.warning(
                        f"Set Node - Skipping large binary file '{large_file['filename']}': "
                        f"{large_file['size'] / (1024*1024):.1f}MB exceeds limit of {max_binary_mb}MB"
                    )
                    return False
                else:
                    logger.error(
                        f"Set Node - Binary file '{large_file['filename']}' exceeds size limit: "
                        f"{large_file['size'] / (1024*1024):.1f}MB > {max_binary_mb}MB"
                    )
        
        # Check total memory
        if memory_info["total_size"] > self.MAX_TOTAL_MEMORY:
            logger.warning(
                f"Set Node - Total memory usage: {memory_info['total_size'] / (1024*1024):.1f}MB "
                f"exceeds recommended limit: {self.MAX_TOTAL_MEMORY / (1024*1024):.1f}MB"
            )
        
        return True

    def _log_memory_stats(self, input_data: List[NodeExecutionData], result_items: List[NodeExecutionData], options: Dict[str, Any]) -> None:
        """Log memory usage statistics"""
        if not options.get("enableMemoryTracking", True):
            return
        
        try:
            # Calculate input memory
            input_memory = sum(
                self._calculate_memory_usage(item)["total_size"] 
                for item in input_data
            )
            
            # Calculate output memory
            output_memory = sum(
                self._calculate_memory_usage(item)["total_size"] 
                for item in result_items
            )
            
            # Count binary files
            total_binary_files = sum(
                self._calculate_memory_usage(item)["binary_files"] 
                for item in result_items
            )
            
            logger.info(
                f"Set Node - Memory usage: "
                f"Input: {input_memory / (1024*1024):.1f}MB, "
                f"Output: {output_memory / (1024*1024):.1f}MB, "
                f"Binary files: {total_binary_files}, "
                f"Items: {len(result_items)}"
            )
            
            # Warn about large growth (avoid division by zero)
            if input_memory > 0 and output_memory > input_memory * 5:
                logger.warning(
                    f"Set Node - Large memory growth detected: "
                    f"{(output_memory / input_memory):.1f}x increase"
                )
                
        except Exception as e:
            logger.error(f"Set Node - Error logging memory stats: {str(e)}")

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Set node logic with memory tracking"""
        try:
            input_data = self.get_input_data()
            if not input_data:
                logger.info("Set Node - No input data")
                return [[]]
            
            # Get memory management options
            memory_options = self.get_parameter("memoryOptions", 0, {})
            
            result_items: List[NodeExecutionData] = []
            skipped_items = 0
            
            for item_index, item in enumerate(input_data):
                try:
                    # Check input memory before processing
                    if memory_options.get("enableMemoryTracking", True):
                        input_memory = self._calculate_memory_usage(item)
                        if not self._check_memory_limits(input_memory, memory_options):
                            skipped_items += 1
                            logger.warning(f"Set Node - Skipped item {item_index} due to memory limits")
                            continue
                    
                    mode = self.get_parameter("mode", item_index, "manual")
                    duplicate_item = self.get_parameter("duplicateItem", item_index, False)
                    duplicate_count = self.get_parameter("duplicateCount", item_index, 0)

                    if mode == "raw":
                        new_item = self._execute_raw_mode(item, item_index, memory_options)
                    else:
                        new_item = self._execute_manual_mode(item, item_index, memory_options)
                    
                    # Check output memory after processing
                    if memory_options.get("enableMemoryTracking", True):
                        output_memory = self._calculate_memory_usage(new_item)
                        if not self._check_memory_limits(output_memory, memory_options):
                            logger.warning(f"Set Node - Output for item {item_index} exceeds memory limits")
                            # Continue with original item instead of processed item
                            new_item = copy.deepcopy(item)
                    
                    if duplicate_item:
                        duplicate_total = max(1, duplicate_count + 1)
                        for dup_index in range(duplicate_total):
                            duplicated_item = copy.deepcopy(new_item)
                            result_items.append(duplicated_item)
                    else:
                        result_items.append(new_item)
                        
                except Exception as e:
                    logger.error(f"Set Node - Error processing item {item_index}: {str(e)}")
                    result_items.append(copy.deepcopy(item))
            
            # Log final memory statistics
            if memory_options.get("enableMemoryTracking", True):
                self._log_memory_stats(input_data, result_items, memory_options)
                if skipped_items > 0:
                    logger.info(f"Set Node - Skipped {skipped_items} items due to memory limits")
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Set Node - Execution error: {str(e)}")
            return [[]]

    def _execute_manual_mode(self, item: NodeExecutionData, item_index: int, memory_options: Dict[str, Any]) -> NodeExecutionData:
        """Execute manual mode with memory tracking"""
        try:
            fields = self.get_parameter("fields", item_index, [])
            options = self.get_parameter("options", item_index, {})
            
            new_json_data = copy.deepcopy(item.json_data or {})
            new_binary_data = copy.deepcopy(item.binary_data or {})
            
            logger.info(f"Set Node - Processing {len(fields)} fields for item {item_index}")
            
            for field_index, field in enumerate(fields):
                try:
                    #field_name = field.get("name", "")
                    field_name = self.get_node_parameter(f"fields.{field_index}.name", item_index, "")
                    field_type = self.get_parameter(f"fields.{field_index}.type", item_index, "stringValue")

                    if not field_name and field_type != "binaryValue":
                        logger.warning(f"Set Node - Skipping field {field_index}: no name provided")
                        continue 
                    
                    if field_type == "stringValue":
                        # FIXED: Use get_node_parameter for expression evaluation
                        value = self.get_node_parameter(f"fields.{field_index}.stringValue", item_index, "")
                        new_json_data[field_name] = value
                    
                    elif field_type == "numberValue":
                        # FIXED: Use get_node_parameter for expression evaluation
                        value = self.get_node_parameter(f"fields.{field_index}.numberValue", item_index, 0)
                        new_json_data[field_name] = value
                    
                    elif field_type == "booleanValue":
                        # FIXED: Use get_node_parameter for expression evaluation
                        value = self.get_node_parameter(f"fields.{field_index}.booleanValue", item_index, False)
                        new_json_data[field_name] = value
                    
                    elif field_type == "arrayValue":
                        # FIXED: Use get_node_parameter for expression evaluation
                        array_str = self.get_node_parameter(f"fields.{field_index}.arrayValue", item_index, "[]")
                        value = self._parse_array_value(array_str, options.get("ignoreConversionErrors", False))

                        # Check array memory usage
                        if memory_options.get("enableMemoryTracking", True):
                            array_size = sys.getsizeof(json.dumps(value, default=str).encode('utf-8'))
                            if array_size > self.LARGE_FILE_THRESHOLD:
                                logger.warning(f"Set Node - Large array field '{field_name}': {array_size / (1024*1024):.1f}MB")
                        
                        new_json_data[field_name] = value
                    
                    elif field_type == "objectValue":
                        # FIXED: Use get_node_parameter for expression evaluation
                        object_str = self.get_node_parameter(f"fields.{field_index}.objectValue", item_index, "{}")
                        value = self._parse_object_value(object_str, options.get("ignoreConversionErrors", False))  
                        # Check object memory usage
                        if memory_options.get("enableMemoryTracking", True):
                            obj_size = sys.getsizeof(json.dumps(value, default=str).encode('utf-8'))
                            if obj_size > self.LARGE_FILE_THRESHOLD:
                                logger.warning(f"Set Node - Large object field '{field_name}': {obj_size / (1024*1024):.1f}MB")
                        
                        # FIXED: Actually assign the parsed object value to the field!
                        new_json_data[field_name] = value
                    
                    elif field_type == "binaryValue":
                        # FIXED: Handle binary with memory checking
                        self._handle_binary_field_with_memory(new_binary_data, field_index, item_index, memory_options)
                        # Binary fields don't go into json_data, they go into binary_data
                        continue
                    
                    else:
                        logger.warning(f"Set Node - Unknown field type '{field_type}', using empty string")
                        value = ""
                        new_json_data[field_name] = value
            
                except Exception as e:
                    logger.error(f"Set Node - Error setting field {field_index} ('{field_name}'): {str(e)}", exc_info=True)
                    if not options.get("ignoreConversionErrors", False):
                        raise
                    else:
                        logger.warning(f"Set Node - Ignoring error for field '{field_name}' due to ignoreConversionErrors=true")
        
            return NodeExecutionData(
                json_data=new_json_data,
                binary_data=new_binary_data
            )
        
        except Exception as e:
            logger.error(f"Set Node - Manual mode error for item {item_index}: {str(e)}", exc_info=True)
            raise

    def _handle_binary_field_with_memory(self, new_binary_data: Dict[str, Any], field_index: int, item_index: int, memory_options: Dict[str, Any]) -> None:
        """Handle binary field with memory checks"""
        binary_key = self.get_node_parameter(f"fields.{field_index}.binaryKey", item_index, "data")
        binary_base64 = self.get_node_parameter(f"fields.{field_index}.binaryBase64", item_index, "")
        filename = self.get_node_parameter(f"fields.{field_index}.filename", item_index, "file.bin")
        mime_type = self.get_node_parameter(f"fields.{field_index}.mimeType", item_index, "application/octet-stream")
        size = self.get_node_parameter(f"fields.{field_index}.size", item_index, 0)

        if binary_base64:
            # Calculate file size before adding
            # estimated_size = len(binary_base64) * 3 // 4  # Base64 to binary size
            
            if memory_options.get("enableMemoryTracking", True):
                max_size = memory_options.get("maxBinarySize", 50) * 1024 * 1024
                
                if size > max_size:
                    if memory_options.get("skipLargeBinaries", False):
                        logger.warning(
                            f"Set Node - Skipping large binary '{filename}': "
                            f"{size / (1024*1024):.1f}MB exceeds {max_size / (1024*1024)}MB limit"
                        )
                        return
                    else:
                        logger.error(
                            f"Set Node - Binary file '{filename}' exceeds size limit: "
                            f"{size / (1024*1024):.1f}MB"
                        )

                elif size > self.LARGE_FILE_THRESHOLD:
                    logger.info(
                        f"Set Node - Large binary file '{filename}': "
                        f"{size / (1024*1024):.1f}MB"
                    )

            new_binary_data[binary_key] = {
                "data": binary_base64,
                "filename": filename,
                "mimeType": mime_type,
                #"encoding": "base64",
                "size": size  # Track size for monitoring
            }

    def _execute_raw_mode(self, item: NodeExecutionData, item_index: int, memory_options: Dict[str, Any] = None) -> NodeExecutionData:
        """Execute raw mode with memory awareness"""
        try:
            # FIXED: Use get_node_parameter for expression evaluation
            json_output_str = self.get_node_parameter("jsonOutput", item_index, "{}")
            
            try:
                if isinstance(json_output_str, str):
                    new_json_data = json.loads(json_output_str)
                else:
                    new_json_data = json_output_str
            except json.JSONDecodeError as e:
                logger.error(f"Set Node - Invalid JSON output: {str(e)}")
                new_json_data = {}
            
            include_other_fields = self.get_parameter("includeOtherFields", item_index, False)
            if include_other_fields:
                base_data = self._get_base_data(item, item_index)
                merged_data = {**base_data, **new_json_data}
                new_json_data = merged_data
            
            return NodeExecutionData(
                json_data=new_json_data,
                binary_data=item.binary_data
            )
            
        except Exception as e:
            logger.error(f"Set Node - Raw mode error: {str(e)}")
            raise
    
    def _get_base_data(self, item: NodeExecutionData, item_index: int) -> Dict[str, Any]:
        """Get base data based on include settings"""
        include_mode = self.get_parameter("include", item_index, "all")
        base_data = copy.deepcopy(item.json_data or {})
        
        if include_mode == "selected":
            include_fields_str = self.get_parameter("includeFields", item_index, "")
            include_fields = [f.strip() for f in include_fields_str.split(",") if f.strip()]
            
            if include_fields:
                filtered_data = {}
                for field in include_fields:
                    if field in base_data:
                        filtered_data[field] = base_data[field]
                base_data = filtered_data
            else:
                base_data = {}
                
        elif include_mode == "except":
            exclude_fields_str = self.get_parameter("excludeFields", item_index, "")
            exclude_fields = [f.strip() for f in exclude_fields_str.split(",") if f.strip()]
            
            for field in exclude_fields:
                if field in base_data:
                    del base_data[field]
        
        return base_data
    
    def _parse_array_value(self, value_str: str, ignore_errors: bool = False) -> List[Any]:
        """Parse array value from string with proper JSON escaping"""
        try:
            if isinstance(value_str, list):
                logger.info(f"Set Node - Array value is already a list with {len(value_str)} items")
                return value_str
            elif isinstance(value_str, str):
                logger.info(f"Set Node - Parsing array string: {value_str[:200]}...")
                
                # Try to parse directly first
                try:
                    parsed_array = json.loads(value_str)
                    if isinstance(parsed_array, list):
                        logger.info(f"Set Node - Successfully parsed array with {len(parsed_array)} items")
                        return parsed_array
                    else:
                        logger.warning(f"Set Node - Parsed value is not an array: {type(parsed_array)}")
                        return [parsed_array]
                except json.JSONDecodeError as json_error:
                    logger.warning(f"Set Node - JSON parse failed, trying to fix control characters: {str(json_error)}")
                    
                    # Try to fix common JSON issues
                    try:
                        # Replace problematic control characters
                        cleaned_str = value_str.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
                        cleaned_str = cleaned_str.replace('\t', '\\t').replace('\b', '\\b').replace('\f', '\\f')
                        cleaned_str = cleaned_str.replace('"', '\\"')  # Escape quotes that might break JSON
                        
                        # Try parsing the cleaned string
                        parsed_array = json.loads(cleaned_str)
                        logger.info(f"Set Node - Successfully parsed array after cleaning with {len(parsed_array) if isinstance(parsed_array, list) else 1} items")
                        
                        if isinstance(parsed_array, list):
                            return parsed_array
                        else:
                            return [parsed_array]
                            
                    except json.JSONDecodeError as clean_error:
                        logger.error(f"Set Node - Still failed after cleaning: {str(clean_error)}")
                        
                        # Last resort: try to extract JSON using regex or manual parsing
                        if ignore_errors:
                            logger.warning("Set Node - Using empty array due to parsing errors")
                            return []
                        else:
                            raise ValueError(f"Invalid array JSON format: {str(json_error)} (original), {str(clean_error)} (cleaned)")
            else:
                logger.info(f"Set Node - Converting {type(value_str)} to single-item array")
                return [value_str]
                
        except Exception as e:
            logger.error(f"Set Node - Array parsing error: {str(e)}")
            if ignore_errors:
                logger.warning("Set Node - Using empty array due to error")
                return []
            else:
                raise ValueError(f"Invalid array format: {str(e)}")
        
    def _parse_object_value(self, value_str: str, ignore_errors: bool = False) -> Dict[str, Any]:
        """Parse object value from string"""
        try:
            if isinstance(value_str, dict):
                return value_str
            elif isinstance(value_str, str):
                return json.loads(value_str)
            else:
                return {}
        except Exception as e:
            if ignore_errors:
                logger.warning(f"Set Node - Object parsing error (ignored): {str(e)}")
                return {}
            else:
                raise ValueError(f"Invalid object format: {str(e)}")
    
    def _set_nested_field(self, data: Dict[str, Any], field_path: str, value: Any) -> None:
        """Set nested field using dot notation"""
        try:
            keys = field_path.split('.')
            current = data
            
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                elif not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
            
            current[keys[-1]] = value
            
        except Exception as e:
            logger.error(f"Set Node - Error setting nested field '{field_path}': {str(e)}")
            data[field_path] = value
