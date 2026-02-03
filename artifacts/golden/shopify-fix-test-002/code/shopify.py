#!/usr/bin/env python3
"""
Shopify Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: shopify-fix-test-002
Generated: 2026-02-02T13:56:10.085428

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameter, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class ShopifyNode(BaseNode):
    """
    Shopify node.
    
    
    """

    node_type = "shopify"
    node_version = 1
    display_name = "Shopify"
    description = ""
    icon = "file:shopify.svg"
    group = ['output']
    
    credentials = [
        {
            "name": "shopifyApi",
            "required": True,
        }
    ]

    properties = [
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Authentication", "options": [
                {"name": "Shopifyapi", "value": "shopifyApi"},
                {"name": "Shopifyaccesstokenapi", "value": "shopifyAccessTokenApi"},
                {"name": "Shopifyoauth2api", "value": "shopifyOAuth2Api"}
            ], "default": "shopifyApi", "description": "Authentication method to use"},
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "Order", "value": "order"},
                {"name": "Product", "value": "product"}
            ], "default": "order", "description": "The resource to operate on"},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create a product"},
                {"name": "Delete", "value": "delete", "description": "Delete a product"},
                {"name": "Get", "value": "get", "description": "Get a product"},
                {"name": "Get Many", "value": "getAll", "description": "Get many products"},
                {"name": "Update", "value": "update", "description": "Update a product"}
            ], "default": "create", "description": "Operation to perform on product", "display_options": {'show': {'resource': ['product']}}},
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Create", "value": "create", "description": "Create an order"},
                {"name": "Delete", "value": "delete", "description": "Delete an order"},
                {"name": "Get", "value": "get", "description": "Get an order"},
                {"name": "Get Many", "value": "getAll", "description": "Get many orders"},
                {"name": "Update", "value": "update", "description": "Update an order"}
            ], "default": "create", "description": "Operation to perform on order", "display_options": {'show': {'resource': ['order']}}}
        ]

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the node operations.
        
        SYNC-CELERY SAFE: All HTTP calls use timeout parameter.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list where outer list is output branches,
            inner list is items in that branch.
        """
        # Get input data from previous node
        input_data = self.get_input_data()
        
        # Handle empty input
        if not input_data:
            return [[]]
        
        return_items: List[NodeExecutionData] = []

        for i, item in enumerate(input_data):
            try:
                resource = self.get_node_parameter("resource", i)
                operation = self.get_node_parameter("operation", i)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {})
                
                if resource == "order" and operation == "create":
                    result = self._order_create(i, item_data)
                elif resource == "order" and operation == "delete":
                    result = self._order_delete(i, item_data)
                elif resource == "order" and operation == "get":
                    result = self._order_get(i, item_data)
                elif resource == "order" and operation == "getAll":
                    result = self._order_getAll(i, item_data)
                elif resource == "order" and operation == "update":
                    result = self._order_update(i, item_data)
                elif resource == "product" and operation == "create":
                    result = self._product_create(i, item_data)
                elif resource == "product" and operation == "delete":
                    result = self._product_delete(i, item_data)
                elif resource == "product" and operation == "get":
                    result = self._product_get(i, item_data)
                elif resource == "product" and operation == "getAll":
                    result = self._product_getAll(i, item_data)
                elif resource == "product" and operation == "update":
                    result = self._product_update(i, item_data)
                else:
                    raise ValueError(f"Unknown resource/operation: {resource}/{operation}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                
            except Exception:
                logger.error(f"Error in {resource}/{operation}: {e}")
                if self.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={"error": str(e)}))
                else:
                    raise
        
        return [return_items]

    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        credentials = self.get_credentials("shopifyApi")
        
        # TODO: Configure authentication based on credential type
        query = query or {}
        # For API key auth: query["api_key"] = credentials.get("apiKey")
        # For Bearer auth: headers["Authorization"] = f"Bearer {credentials.get('accessToken')}"
        
        url = f"https://api.example.com{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

    def _order_create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Order Create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        additional_fields = self.get_node_parameter('additionalFields', item_index)
        
        # Build request body
        body = {'test': True, 'line_items': keys_to_snake_case, 'fulfillment_status': additional_fields.get('fulfillmentStatus'), 'inventory_behaviour': additional_fields.get('inventoryBehaviour'), 'location_id': additional_fields.get('locationId'), 'note': additional_fields.get('note'), 'send_fulfillment_receipt': additional_fields.get('sendFulfillmentReceipt'), 'send_receipt': additional_fields.get('sendReceipt'), 'send_receipt': additional_fields.get('sendReceipt'), 'source_name': additional_fields.get('sourceName'), 'tags': additional_fields.get('tags'), 'test': additional_fields.get('test'), 'email': additional_fields.get('email'), 'discount_codes': discount_discount_codes_values, 'billing_address': keys_to_snake_case(
								billing_billing_address_values,
							)[0], 'shipping_address': keys_to_snake_case(
								shipping_shipping_address_values,
							)[0]}
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _order_delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Order Delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        order_id = self.get_node_parameter('orderId', item_index)
        
        # Make API request
        response = self._api_request('DELETE', '/orders/${orderId}.json', body=None, query=None)
        response = response.get('data', response)
        
        return response

    def _order_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Order Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        order_id = self.get_node_parameter('orderId', item_index)
        options = self.get_node_parameter('options', item_index)
        
        # Build query parameters
        query = {}
        query['fields'] = options.get('fields')
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _order_getAll(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Order Getall operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        return_all = self.get_node_parameter('returnAll', item_index)
        options = self.get_node_parameter('options', item_index)
        limit = self.get_node_parameter('limit', item_index)
        
        # Build query parameters
        query = {}
        query['fields'] = options.get('fields')
        query['attribution_app_id'] = options.get('attributionAppId')
        query['created_at_min'] = options.get('createdAtMin')
        query['created_at_max'] = options.get('createdAtMax')
        query['updated_at_max'] = options.get('updatedAtMax')
        query['updated_at_min'] = options.get('updatedAtMin')
        query['processed_at_min'] = options.get('processedAtMin')
        query['processed_at_max'] = options.get('processedAtMax')
        query['since_id'] = options.get('sinceId')
        query['ids'] = options.get('ids')
        query['status'] = options.get('status')
        query['financial_status'] = options.get('financialStatus')
        query['fulfillment_status'] = options.get('fulfillmentStatus')
        query['limit'] = this_get_node_parameter('limit', i)
        
        # Make API request
        response = self._api_request('GET', '/orders.json', body=None, query=query)
        response = response.get('data', response)
        
        return response

    def _order_update(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Order Update operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        order_id = self.get_node_parameter('orderId', item_index)
        update_fields = self.get_node_parameter('updateFields', item_index)
        
        # Build request body
        body = {'location_id': update_fields.get('locationId'), 'note': update_fields.get('note'), 'source_name': update_fields.get('sourceName'), 'tags': update_fields.get('tags'), 'email': update_fields.get('email'), 'shipping_address': keys_to_snake_case(
								shipping_shipping_address_values,
							)[0]}
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _product_create(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Product Create operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        title = self.get_node_parameter('title', item_index)
        additional_fields = self.get_node_parameter('additionalFields', item_index)
        
        # Build request body
        body = {'title': title}
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _product_delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Product Delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _product_get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Product Get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        additional_fields = self.get_node_parameter('additionalFields', item_index)
        
        # TODO: Implement API call
        response = {}
        
        return response

    def _product_getAll(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Product Getall operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        additional_fields = self.get_node_parameter('additionalFields', item_index)
        return_all = self.get_node_parameter('returnAll', item_index)
        limit = self.get_node_parameter('limit', item_index)
        
        # Build query parameters
        query = {}
        query['limit'] = this_get_node_parameter('limit', i)
        
        # Make API request
        response = self._api_request('GET', '/products.json', body=None, query=query)
        response = response.get('data', response)
        
        return response

    def _product_update(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Product Update operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """
        update_fields = self.get_node_parameter('updateFields', item_index)
        
        # TODO: Implement API call
        response = {}
        
        return response

