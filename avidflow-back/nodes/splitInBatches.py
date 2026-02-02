import logging
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class SplitInBatchesNode(BaseNode):
    """
    Split In Batches node for dividing large datasets into smaller, manageable batches.
    Useful for processing large amounts of data without overwhelming memory or API limits.
    """

    type = "splitInBatches"
    version = 1

    description = {
        "displayName": "Split In Batches",
        "name": "splitInBatches",
        "group": ["transform"],
        "version": 1,
        "description": "Split large datasets into smaller batches for efficient processing",
        "defaults": {
            "name": "Split In Batches",
            "color": "#007755"
        },
        "inputs": ["main"],
        "outputs": ["main"],
        "icon": "fa:th-list"
    }

    properties = {
        "parameters": [
            {
                "name": "batchSize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Batch Size",
                "description": "Number of items per batch",
                "default": 10,
                "min": 1,
                "max": 1000,
                "required": True
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "description": "Additional batch processing options",
                "default": {},
                "options": [
                    {
                        "name": "reset",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Reset",
                        "description": "Resets the batch counter. Use this in combination with a loop.",
                        "default": False
                    },
                    {
                        "name": "destinationFieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Destination Field Name",
                        "description": "Field name to store batch items (default: 'items')",
                        "default": "items",
                        "placeholder": "items"
                    },
                    {
                        "name": "includeMetadata",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Include Metadata",
                        "description": "Include batch metadata (batch number, total batches, etc.)",
                        "default": True
                    },
                    {
                        "name": "preserveOrder",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Preserve Order",
                        "description": "Maintain the original order of items",
                        "default": True
                    },
                    {
                        "name": "flattenSingleItem",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Flatten Single Item Batches",
                        "description": "If batch contains only one item, return it directly instead of wrapped in array",
                        "default": False
                    }
                ]
            }
        ]
    }

    icon = "fa:th-list"
    color = "#007755"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize batch state (could be stored in workflow context in production)
        self._batch_counter = 0
        self._total_items_processed = 0

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the Split In Batches node logic.
        Splits input data into batches and processes them sequentially.
        """
        try:
            # Get input data
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("Split In Batches - No input data")
                return [[]]

            # Get parameters
            batch_size = self.get_node_parameter("batchSize", 0, 10)
            reset = self.get_node_parameter("options.reset", 0, False)
            destination_field = self.get_node_parameter("options.destinationFieldName", 0, "items")
            include_metadata = self.get_node_parameter("options.includeMetadata", 0, True)
            preserve_order = self.get_node_parameter("options.preserveOrder", 0, True)
            flatten_single = self.get_node_parameter("options.flattenSingleItem", 0, False)

            # Validate batch size
            if batch_size <= 0:
                return self._create_error_result("Batch size must be greater than 0")

            # Reset batch counter if requested
            if reset:
                self._batch_counter = 0
                self._total_items_processed = 0
                logger.info("Split In Batches - Counter reset")

            # Calculate total batches
            total_items = len(input_data)
            total_batches = (total_items + batch_size - 1) // batch_size  # Ceiling division

            if total_items == 0:
                return [[]]

            # Split data into batches
            batches = []
            for i in range(0, total_items, batch_size):
                batch_items = input_data[i:i + batch_size]
                batch_number = (i // batch_size) + 1

                # Create batch result
                batch_result = self._create_batch_result(
                    batch_items=batch_items,
                    batch_number=batch_number,
                    total_batches=total_batches,
                    destination_field=destination_field,
                    include_metadata=include_metadata,
                    flatten_single=flatten_single,
                    preserve_order=preserve_order
                )

                batches.append(batch_result)

            # Update counters
            self._total_items_processed += total_items
            self._batch_counter += total_batches

            logger.info(f"Split In Batches - Created {total_batches} batches from {total_items} items")
            
            # Return all batches as separate executions
            return [[batch] for batch in batches]

        except Exception as e:
            logger.error(f"Split In Batches - Execution error: {str(e)}")
            return self._create_error_result(f"Error splitting data: {str(e)}")

    def _create_batch_result(
        self,
        batch_items: List[NodeExecutionData],
        batch_number: int,
        total_batches: int,
        destination_field: str,
        include_metadata: bool,
        flatten_single: bool,
        preserve_order: bool
    ) -> NodeExecutionData:
        """Create a batch result with proper structure"""
        
        # Extract JSON data from batch items
        if preserve_order:
            batch_data = [item.json_data for item in batch_items]
        else:
            # Could implement different ordering logic here if needed
            batch_data = [item.json_data for item in batch_items]

        # Handle single item flattening
        if flatten_single and len(batch_data) == 1:
            result_data = batch_data[0].copy() if batch_data[0] else {}
            
            # Add metadata to the flattened item if requested
            if include_metadata:
                result_data["_batch"] = {
                    "batchNumber": batch_number,
                    "totalBatches": total_batches,
                    "itemsInBatch": 1,
                    "flattened": True
                }
        else:
            # Create batch container
            result_data = {
                destination_field: batch_data
            }
            
            # Add metadata if requested
            if include_metadata:
                result_data["batch"] = {
                    "batchNumber": batch_number,
                    "totalBatches": total_batches,
                    "itemsInBatch": len(batch_data),
                    "batchSize": len(batch_data),
                    "isLastBatch": batch_number == total_batches,
                    "isFirstBatch": batch_number == 1
                }

        # Handle binary data (take from first item if available)
        binary_data = None
        if batch_items and hasattr(batch_items[0], 'binary_data') and batch_items[0].binary_data:
            binary_data = batch_items[0].binary_data

        return NodeExecutionData(
            json_data=result_data,
            binary_data=binary_data
        )

    def _create_error_result(self, error_message: str) -> List[List[NodeExecutionData]]:
        """Create an error result"""
        error_data = NodeExecutionData(
            json_data={
                "error": error_message,
                "node": "Split In Batches",
                "timestamp": self._get_execution_context().get('id', '')
            },
            binary_data=None
        )
        return [[error_data]]

    def reset_batch_counter(self) -> None:
        """Reset the batch counter - useful for loops"""
        self._batch_counter = 0
        self._total_items_processed = 0

    def get_batch_stats(self) -> Dict[str, int]:
        """Get current batch statistics"""
        return {
            "batchesCreated": self._batch_counter,
            "totalItemsProcessed": self._total_items_processed
        }

    # Additional utility methods for advanced use cases
    def _calculate_optimal_batch_size(self, total_items: int, target_batches: int) -> int:
        """Calculate optimal batch size for a target number of batches"""
        if target_batches <= 0:
            return total_items
        
        return max(1, (total_items + target_batches - 1) // target_batches)

    def _estimate_memory_usage(self, batch_items: List[NodeExecutionData]) -> int:
        """Estimate memory usage of a batch (in bytes)"""
        import sys
        total_size = 0
        
        for item in batch_items:
            if hasattr(item, 'json_data') and item.json_data:
                total_size += sys.getsizeof(str(item.json_data))
            if hasattr(item, 'binary_data') and item.binary_data:
                total_size += sys.getsizeof(item.binary_data)
        
        return total_size