"""
WooCommerce node for interacting with WooCommerce API.
"""
import json
import math
import time
import requests
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from models import NodeExecutionData
from .base import BaseNode, GetNodeParameterOptions, NodeParameterType
from utils.serialization import deep_serialize
from utils.expression_evaluator import ExpressionEngine

logger = logging.getLogger(__name__)


class WooCommerceNode(BaseNode):
    """WooCommerce Node for interacting with WooCommerce API"""
    
    type = "wooCommerce"
    version = 1
    description = {
        "displayName": "WooCommerce",
        "name": "wooCommerce",
        "group": ["transform"],
        "version": 1,
        "description": "Consume WooCommerce REST API",
        "defaults": {
            "name": "WooCommerce"
        },
        "inputs": [
            {
                "name": "main",
                "type": "main",
                "required": False
            }
        ],
        "outputs": [
            {
                "name": "main",
                "type": "main",
                "required": False
            }
        ],
        "credentials": [
            {
                "name": "wooCommerceApi",
                "required": True
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Resource",
                "description": "The resource to operate on",
                "default": "product",
                "options": [
                    {"name": "Customer", "value": "customer"},
                    {"name": "Order", "value": "order"},
                    {"name": "Product", "value": "product"},
                    {"name": "Product Category", "value": "productCategory"}
                ]
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Operation",
                "description": "The operation to perform",
                "default": "get",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Get", "value": "get"},
                    {"name": "Get All", "value": "getAll"},
                    {"name": "Update", "value": "update"}
                ]
            },
            {
                "name": "resourceId",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "ID",
                "description": "ID of the resource to operate on",
                "default": "",
                "display_options": {
                    "show": {
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            {
                "name": "filters",
                "type": NodeParameterType.COLLECTION,
                "required": False,
                "display_name": "Filters",
                "description": "Filter options for retrieving resources",
                "placeholder": "Add filters",
                "default": {},
                "display_options": {
                    "show": {
                        "operation": ["getAll"]
                    }
                },
                "options": [
                    {
                        "name": "search",
                        "type": NodeParameterType.STRING,
                        "display_name": "Search",
                        "description": "Search term to filter results by",
                        "default": ""
                    },
                    {
                        "name": "after",
                        "type": NodeParameterType.STRING,
                        "display_name": "After Date",
                        "description": "Limit response to resources published after a given ISO8601 compliant date",
                        "default": ""
                    },
                    {
                        "name": "before",
                        "type": NodeParameterType.STRING,
                        "display_name": "Before Date",
                        "description": "Limit response to resources published before a given ISO8601 compliant date",
                        "default": ""
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "Limit result set to resources with a specific status",
                        "default": "any",
                        "options": [
                            {"name": "Any", "value": "any"},
                            {"name": "Draft", "value": "draft"},
                            {"name": "Pending", "value": "pending"},
                            {"name": "Private", "value": "private"},
                            {"name": "Published", "value": "publish"}
                        ]
                    },
                    {
                        "name": "page",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Page",
                        "description": "Current page of the collection",
                        "default": 1,
                        "type_options": {
                            "minValue": 1
                        }
                    },
                    {
                        "name": "per_page",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Items Per Page",
                        "description": "Maximum number of items to be returned in result set",
                        "default": 10,
                        "type_options": {
                            "minValue": 1,
                            "maxValue": 100
                        }
                    },
                    {
                        "name": "orderby",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Order By",
                        "description": "Sort collection by object attribute",
                        "default": "date",
                        "options": [
                            {"name": "Date", "value": "date"},
                            {"name": "ID", "value": "id"},
                            {"name": "Title", "value": "title"},
                            {"name": "Slug", "value": "slug"}
                        ]
                    },
                    {
                        "name": "order",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Order",
                        "description": "Order sort attribute ascending or descending",
                        "default": "desc",
                        "options": [
                            {"name": "Ascending", "value": "asc"},
                            {"name": "Descending", "value": "desc"}
                        ]
                    }
                ]
            },
            {
                "name": "productOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Product Options",
                "description": "Options for product creation or update",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "name",
                        "type": NodeParameterType.STRING,
                        "display_name": "Name",
                        "description": "Product name",
                        "default": ""
                    },
                    {
                        "name": "type",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Type",
                        "description": "Product type",
                        "default": "simple",
                        "options": [
                            {"name": "Simple", "value": "simple"},
                            {"name": "Grouped", "value": "grouped"},
                            {"name": "External", "value": "external"},
                            {"name": "Variable", "value": "variable"}
                        ]
                    },
                    {
                        "name": "regular_price",
                        "type": NodeParameterType.STRING,
                        "display_name": "Regular Price",
                        "description": "Product regular price",
                        "default": ""
                    },
                    {
                        "name": "sale_price",
                        "type": NodeParameterType.STRING,
                        "display_name": "Sale Price",
                        "description": "Product sale price",
                        "default": ""
                    },
                    {
                        "name": "description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Description",
                        "description": "Product description",
                        "default": ""
                    },
                    {
                        "name": "short_description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Short Description",
                        "description": "Product short description",
                        "default": ""
                    },
                    {
                        "name": "categories",
                        "type": NodeParameterType.JSON,
                        "display_name": "Categories",
                        "description": "List of categories this product is in",
                        "default": "[]",
                        "type_options": {
                            "multipleValues": True
                        }
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "Product status",
                        "default": "publish",
                        "options": [
                            {"name": "Draft", "value": "draft"},
                            {"name": "Pending", "value": "pending"},
                            {"name": "Private", "value": "private"},
                            {"name": "Published", "value": "publish"}
                        ]
                    }
                ]
            },
            {
                "name": "orderOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Order Options",
                "description": "Options for order creation or update",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "Order status",
                        "default": "pending",
                        "options": [
                            {"name": "Pending payment", "value": "pending"},
                            {"name": "Processing", "value": "processing"},
                            {"name": "On hold", "value": "on-hold"},
                            {"name": "Completed", "value": "completed"},
                            {"name": "Cancelled", "value": "cancelled"},
                            {"name": "Refunded", "value": "refunded"},
                            {"name": "Failed", "value": "failed"}
                        ]
                    },
                    {
                        "name": "customer_id",
                        "type": NodeParameterType.STRING,
                        "display_name": "Customer ID",
                        "description": "Customer ID",
                        "default": ""
                    },
                    {
                        "name": "payment_method",
                        "type": NodeParameterType.STRING,
                        "display_name": "Payment Method",
                        "description": "Payment method ID",
                        "default": ""
                    },
                    {
                        "name": "payment_method_title",
                        "type": NodeParameterType.STRING,
                        "display_name": "Payment Method Title",
                        "description": "Payment method title",
                        "default": ""
                    },
                    {
                        "name": "billing",
                        "type": NodeParameterType.JSON,
                        "display_name": "Billing",
                        "description": "Billing information",
                        "default": "{}"
                    },
                    {
                        "name": "shipping",
                        "type": NodeParameterType.JSON,
                        "display_name": "Shipping",
                        "description": "Shipping information",
                        "default": "{}"
                    },
                    {
                        "name": "line_items",
                        "type": NodeParameterType.JSON,
                        "display_name": "Line Items",
                        "description": "Line items data",
                        "default": "[]"
                    }
                ]
            },
            {
                "name": "customerOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Customer Options",
                "description": "Options for customer creation or update",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["customer"],
                        "operation": ["create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "email",
                        "type": NodeParameterType.STRING,
                        "display_name": "Email",
                        "description": "Customer email",
                        "default": ""
                    },
                    {
                        "name": "first_name",
                        "type": NodeParameterType.STRING,
                        "display_name": "First Name",
                        "description": "Customer first name",
                        "default": ""
                    },
                    {
                        "name": "last_name",
                        "type": NodeParameterType.STRING,
                        "display_name": "Last Name",
                        "description": "Customer last name",
                        "default": ""
                    },
                    {
                        "name": "username",
                        "type": NodeParameterType.STRING,
                        "display_name": "Username",
                        "description": "Customer username",
                        "default": ""
                    },
                    {
                        "name": "password",
                        "type": NodeParameterType.STRING,
                        "display_name": "Password",
                        "description": "Customer password",
                        "default": "",
                        "type_options": {
                            "password": True
                        }
                    },
                    {
                        "name": "billing",
                        "type": NodeParameterType.JSON,
                        "display_name": "Billing",
                        "description": "Billing information",
                        "default": "{}"
                    },
                    {
                        "name": "shipping",
                        "type": NodeParameterType.JSON,
                        "display_name": "Shipping",
                        "description": "Shipping information",
                        "default": "{}"
                    }
                ]
            },
            {
                "name": "categoryOptions",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Category Options",
                "description": "Options for product category creation or update",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["productCategory"],
                        "operation": ["create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "name",
                        "type": NodeParameterType.STRING,
                        "display_name": "Name",
                        "description": "Category name",
                        "default": ""
                    },
                    {
                        "name": "slug",
                        "type": NodeParameterType.STRING,
                        "display_name": "Slug",
                        "description": "Category slug",
                        "default": ""
                    },
                    {
                        "name": "parent",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Parent ID",
                        "description": "Parent category ID",
                        "default": 0
                    },
                    {
                        "name": "description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Description",
                        "description": "Category description",
                        "default": ""
                    }
                ]
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "description": "Additional fields to include in the request",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "operation": ["create", "update"]
                    }
                },
                "options": [
                    {
                        "name": "categories",
                        "type": NodeParameterType.JSON,
                        "display_name": "Categories",
                        "description": "Product categories as JSON array",
                        "default": "[]"
                    },
                    {
                        "name": "stock_status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Stock Status",
                        "description": "Product inventory status",
                        "default": "instock",
                        "options": [
                            {"name": "In Stock", "value": "instock"},
                            {"name": "Out of Stock", "value": "outofstock"},
                            {"name": "On Backorder", "value": "onbackorder"}
                        ]
                    },
                    {
                        "name": "featured",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Featured",
                        "description": "Featured product",
                        "default": False
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "wooCommerceApi",
                "required": True
            }
        ]
    }
       
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the WooCommerce node operation"""
        try:
            # Get credentials
            credentials = self.get_credentials("wooCommerceApi")
            if not credentials:
                raise ValueError("No credentials provided")
            
            # Get input items (for processing multiple items if needed)
            items = self.get_input_data()
            
            # If no items, process with default params
            if not items:
                items = [NodeExecutionData(json_data={})]
            
            # Get base parameters
            resource = self.get_node_parameter("resource")
            operation = self.get_node_parameter("operation")
            
            # Process each input item
            result_items = []
            
            for item_index, item in enumerate(items):
                try:
                    # Execute the appropriate operation based on resource and operation
                    result = self._process_operation(credentials, resource, operation, item_index)
                    
                    # Handle list results (e.g., from getAll operations)
                    if isinstance(result, list):
                        if operation == "getAll":
                            # For getAll operations, wrap the list in a dictionary with a 'data' key
                            serialized_result = deep_serialize({"data": result, "count": len(result)})
                            result_items.append(NodeExecutionData(json_data=serialized_result))
                        else:
                            # For other operations that might return lists, handle each item
                            for item_data in result:
                                serialized_item = deep_serialize(item_data)
                                result_items.append(NodeExecutionData(json_data=serialized_item))
                    else:
                        # For dictionary results, just pass them along
                        serialized_result = deep_serialize(result)
                        result_items.append(NodeExecutionData(json_data=serialized_result))
                except Exception as e:
                    error_message = str(e)
                    logger.error(f"WooCommerce Node Error processing item {item_index}: {error_message}")
                    result_items.append(NodeExecutionData(json_data={"error": True, "message": error_message}))
            
            # Return results in n8n format
            return [result_items]
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"WooCommerce Node Error: {error_message}")
            return [[NodeExecutionData(json_data={"error": True, "message": error_message})]]
    
    def _process_operation(self, credentials, resource, operation, item_index):
        """Process the operation based on resource type"""
        if resource == "product":
            return self._process_product_operations(credentials, operation, item_index)
        elif resource == "order":
            return self._process_order_operations(credentials, operation, item_index)
        elif resource == "customer":
            return self._process_customer_operations(credentials, operation, item_index)
        elif resource == "productCategory":
            return self._process_category_operations(credentials, operation, item_index)
        else:
            raise ValueError(f"Unsupported resource '{resource}'")

    def _process_product_operations(self, credentials, operation, item_index):
        """Process product operations"""
        if operation == "create":
            return self._create_product(credentials, item_index)
        elif operation == "get":
            return self._get_product(credentials, item_index)
        elif operation == "update":
            return self._update_product(credentials, item_index)
        elif operation == "delete":
            return self._delete_product(credentials, item_index)
        elif operation == "getAll":
            return self._get_all_products(credentials, item_index)
        else:
            raise ValueError(f"Unsupported operation '{operation}' for resource 'product'")

    def _process_order_operations(self, credentials, operation, item_index):
        """Process order operations"""
        if operation == "create":
            return self._create_order(credentials, item_index)
        elif operation == "get":
            return self._get_order(credentials, item_index)
        elif operation == "update":
            return self._update_order(credentials, item_index)
        elif operation == "delete":
            return self._delete_order(credentials, item_index)
        elif operation == "getAll":
            return self._get_all_orders(credentials, item_index)
        else:
            raise ValueError(f"Unsupported operation '{operation}' for resource 'order'")

    def _process_customer_operations(self, credentials, operation, item_index):
        """Process customer operations"""
        if operation == "create":
            return self._create_customer(credentials, item_index)
        elif operation == "get":
            return self._get_customer(credentials, item_index)
        elif operation == "update":
            return self._update_customer(credentials, item_index)
        elif operation == "delete":
            return self._delete_customer(credentials, item_index)
        elif operation == "getAll":
            return self._get_all_customers(credentials, item_index)
        else:
            raise ValueError(f"Unsupported operation '{operation}' for resource 'customer'")

    def _process_category_operations(self, credentials, operation, item_index):
        """Process category operations"""
        if operation == "create":
            return self._create_product_category(credentials, item_index)
        elif operation == "get":
            return self._get_product_category(credentials, item_index)
        elif operation == "update":
            return self._update_product_category(credentials, item_index)
        elif operation == "delete":
            return self._delete_product_category(credentials, item_index)
        elif operation == "getAll":
            return self._get_all_product_categories(credentials, item_index)
        else:
            raise ValueError(f"Unsupported operation '{operation}' for resource 'productCategory'")
    
    def _get_api_url(self, credentials, resource):
        """Get the API URL for a specific resource"""
        # Map resource names to API endpoints
        resource_endpoints = {
            "product": "products",
            "order": "orders",
            "customer": "customers",
            "productCategory": "products/categories"
        }
        
        # Get API parameters
        endpoint = resource_endpoints.get(resource, "")
        if not endpoint:
            raise ValueError(f"Unknown resource type: {resource}")
        
        # Base URL from credentials
        base_url = credentials.get("url", "").rstrip("/")
        api_url = f"{base_url}/wp-json/wc/v3/{endpoint}"
        
        return api_url
    
    def _get_auth(self, credentials):
        """Get authentication for WooCommerce API requests"""
        auth = None
        params = {}
        
        # Check if credentials should be in query params
        if credentials.get("includeCredentialsInQuery", False):
            params.update({
                "consumer_key": credentials.get("consumerKey", ""),
                "consumer_secret": credentials.get("consumerSecret", "")
            })
        else:
            auth = (
                credentials.get("consumerKey", ""),
                credentials.get("consumerSecret", "")
            )
        
        return auth, params

    def _prepare_product_data(self, item_index):
        """Prepare product data with proper expression evaluation"""
        data = {}
        
        # Get product options
        product_options = self.get_node_parameter("productOptions", item_index, {})
        
        # Process each product option and evaluate any expressions
        for key, value in product_options.items():
            if value is not None:
                data[key] = self._process_value_recursively(value, item_index)
    
        # Get and process additional fields
        additional_fields = self.get_node_parameter("additionalFields", item_index, {})
        
        # Process the additional fields dictionary
        if isinstance(additional_fields, dict):
            for key, value in additional_fields.items():
                if value is not None:
                    # Process nested structures recursively
                    data[key] = self._process_value_recursively(value, item_index)
        return data
        
    def _prepare_order_data(self, item_index):
        """Prepare order data with proper expression evaluation"""
        data = {}
        
        # Get order options
        order_options = self.get_node_parameter("orderOptions", item_index, {})
        
        # Process each order option and evaluate any expressions
        for key, value in order_options.items():
            if value is not None:
                data[key] = self._process_value_recursively(value, item_index)
    
        # Get and process additional fields
        additional_fields = self.get_node_parameter("additionalFields", item_index, {})
        
        # Process the additional fields dictionary
        if isinstance(additional_fields, dict):
            for key, value in additional_fields.items():
                if value is not None:
                    data[key] = self._process_value_recursively(value, item_index)

        return data  # Important! Return the processed data
                
    def _prepare_customer_data(self, item_index):
        """Prepare customer data with proper expression evaluation"""
        data = {}
        
        # Get customer options
        customer_options = self.get_node_parameter("customerOptions", item_index, {})
        
        # Process each customer option and evaluate any expressions
        for key, value in customer_options.items():
            if value is not None:
                data[key] = self._process_value_recursively(value, item_index)
    
        # Get and process additional fields
        additional_fields = self.get_node_parameter("additionalFields", item_index, {})
        
        # Process the additional fields dictionary
        if isinstance(additional_fields, dict):
            for key, value in additional_fields.items():
                if value is not None:
                    data[key] = self._process_value_recursively(value, item_index)

        return data
                
    def _prepare_category_data(self, item_index):
        """Prepare category data with proper expression evaluation"""
        data = {}
        
        # Get category options
        category_options = self.get_node_parameter("categoryOptions", item_index, {})
        
        # Process each category option and evaluate any expressions
        for key, value in category_options.items():
            if value is not None:
                data[key] = self._process_value_recursively(value, item_index)
    
        # Get and process additional fields
        additional_fields = self.get_node_parameter("additionalFields", item_index, {})
        
        # Process the additional fields dictionary
        if isinstance(additional_fields, dict):
            for key, value in additional_fields.items():
                if value is not None:
                    data[key] = self._process_value_recursively(value, item_index)
    
        logger.info(f"Prepared category data: {json.dumps(data, indent=2)}")
        return data  # Add this return statement!

    def _process_value_recursively(self, value, item_index):
        """Process a value recursively, evaluating expressions at any level"""
        # Handle strings with expressions
        if isinstance(value, str) and "{{" in value:
            return self._process_custom_expression(value, item_index)
        
        # Handle lists - process each item recursively
        elif isinstance(value, list):
            return [self._process_value_recursively(item, item_index) for item in value]
        
        # Handle dictionaries - process each value recursively
        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                result[k] = self._process_value_recursively(v, item_index)
            return result
        
        # Return other types unchanged
        else:
            return value
        
    def _process_custom_expression(self, expression_value, item_index):
        """Process expression in a custom string value not directly from parameters"""
        if not isinstance(expression_value, str) or "{{" not in expression_value:
            return expression_value
            
        # Use the base node's evaluation method
        options = GetNodeParameterOptions()
        return self._evaluate_expressions(
            expression_value,
            item_index,
            "custom_expression",  # Parameter name (for error context)
            options
        )

    # PRODUCT METHODS

    def _create_product(self, credentials, item_index):
        """Create a product with proper expression evaluation"""
        try:
            # Get all parameters using proper expression evaluation
            product_data = self._prepare_product_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="product",
                operation="create",
                data=product_data
            )
    
        except Exception as e:
            logger.error(f"Error in _create_product: {str(e)}")
            raise

    def _get_all_products(self, credentials, item_index):
        """Get all products with filters"""
        try:
            # Get filters
            filters = self.get_node_parameter("filters", item_index, {})
            
            # Process filters with expression evaluation
            processed_filters = {}
            for key, value in filters.items():
                if value is not None:
                    processed_filters[key] = self._process_value_recursively(value, item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="product",
                operation="getAll",
                params=processed_filters
            )
        except Exception as e:
            logger.error(f"Error in _get_all_products: {str(e)}")
            raise

    def _get_product(self, credentials, item_index):
        """Get a single product by ID"""
        try:
            # Get the product ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Product ID is required for get operation")
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="product",
                operation="get",
                resource_id=resource_id
            )
        except Exception as e:
            logger.error(f"Error in _get_product: {str(e)}")
            raise

    def _update_product(self, credentials, item_index):
        """Update a product with proper expression evaluation"""
        try:
            # Get the product ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Product ID is required for update operation")
            
            # Prepare product data with expression evaluation
            product_data = self._prepare_product_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="product",
                operation="update",
                resource_id=resource_id,
                data=product_data
            )
        except Exception as e:
            logger.error(f"Error in _update_product: {str(e)}")
            raise

    def _delete_product(self, credentials, item_index):
        """Delete a product by ID"""
        try:
            # Get the product ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Product ID is required for delete operation")
            
            # Get force parameter (permanently delete or trash)
            force = self.get_node_parameter("force", item_index, False)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="product",
                operation="delete",
                resource_id=resource_id,
                params={"force": force}
            )
        except Exception as e:
            logger.error(f"Error in _delete_product: {str(e)}")
            raise

    # ORDER METHODS

    def _create_order(self, credentials, item_index):
        """Create an order with proper expression evaluation"""
        try:
            # Prepare order data with expression evaluation
            order_data = self._prepare_order_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="order",
                operation="create",
                data=order_data
            )
    
        except Exception as e:
            logger.error(f"Error in _create_order: {str(e)}")
            raise

    def _get_order(self, credentials, item_index):
        """Get a single order by ID"""
        try:
            # Get the order ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Order ID is required for get operation")
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="order",
                operation="get",
                resource_id=resource_id
            )
        except Exception as e:
            logger.error(f"Error in _get_order: {str(e)}")
            raise

    def _update_order(self, credentials, item_index):
        """Update an order by ID with proper expression evaluation"""
        try:
            # Get the order ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Order ID is required for update operation")
            
            # Prepare order data with expression evaluation
            order_data = self._prepare_order_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="order",
                operation="update",
                resource_id=resource_id,
                data=order_data
            )
        except Exception as e:
            logger.error(f"Error in _update_order: {str(e)}")
            raise

    def _delete_order(self, credentials, item_index):
        """Delete an order by ID"""
        try:
            # Get the order ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Order ID is required for delete operation")
            
            # Get force parameter (permanently delete or trash)
            force = self.get_node_parameter("force", item_index, False)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="order",
                operation="delete",
                resource_id=resource_id,
                params={"force": force}
            )
        except Exception as e:
            logger.error(f"Error in _delete_order: {str(e)}")
            raise
    
    def _get_all_orders(self, credentials, item_index):
        """Get all orders with filters"""
        try:
            # Get filters
            filters = self.get_node_parameter("filters", item_index, {})
            
            # Process filters with expression evaluation
            processed_filters = {}
            for key, value in filters.items():
                if value is not None:
                    processed_filters[key] = self._process_value_recursively(value, item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="order",
                operation="getAll",
                params=processed_filters
            )
        except Exception as e:
            logger.error(f"Error in _get_all_orders: {str(e)}")
            raise

    # CUSTOMER METHODS

    def _create_customer(self, credentials, item_index):
        """Create a customer with proper expression evaluation"""
        try:
            # Prepare customer data with expression evaluation
            customer_data = self._prepare_customer_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="customer",
                operation="create",
                data=customer_data
            )
    
        except Exception as e:
            logger.error(f"Error in _create_customer: {str(e)}")
            raise

    def _get_customer(self, credentials, item_index):
        """Get a single customer by ID"""
        try:
            # Get the customer ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Customer ID is required for get operation")
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="customer",
                operation="get",
                resource_id=resource_id
            )
        except Exception as e:
            logger.error(f"Error in _get_customer: {str(e)}")
            raise

    def _update_customer(self, credentials, item_index):
        """Update a customer with proper expression evaluation"""
        try:
            # Get the customer ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Customer ID is required for update operation")
            
            # Prepare customer data with expression evaluation
            customer_data = self._prepare_customer_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="customer",
                operation="update",
                resource_id=resource_id,
                data=customer_data
            )
        except Exception as e:
            logger.error(f"Error in _update_customer: {str(e)}")
            raise

    def _delete_customer(self, credentials, item_index):
        """Delete a customer by ID"""
        try:
            # Get the customer ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Customer ID is required for delete operation")
            
            # Get force parameter (permanently delete or trash)
            force = self.get_node_parameter("force", item_index, False)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="customer",
                operation="delete",
                resource_id=resource_id,
                params={"force": force}
            )
        except Exception as e:
            logger.error(f"Error in _delete_customer: {str(e)}")
            raise
    
    def _get_all_customers(self, credentials, item_index):
        """Get all customers with filters"""
        try:
            # Get filters
            filters = self.get_node_parameter("filters", item_index, {})
            
            # Process filters with expression evaluation
            processed_filters = {}
            for key, value in filters.items():
                if value is not None:
                    processed_filters[key] = self._process_value_recursively(value, item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="customer",
                operation="getAll",
                params=processed_filters
            )
        except Exception as e:
            logger.error(f"Error in _get_all_customers: {str(e)}")
            raise

    # CATEGORY METHODS

    def _create_product_category(self, credentials, item_index):
        """Create a product category with proper expression evaluation"""
        try:
            # Prepare category data with expression evaluation
            category_data = self._prepare_category_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="productCategory",
                operation="create",
                data=category_data
            )
    
        except Exception as e:
            logger.error(f"Error in _create_product_category: {str(e)}")
            raise

    def _update_product_category(self, credentials, item_index):
        """Update a product category by ID with proper expression evaluation"""
        try:
            # Get the category ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Category ID is required for update operation")
            
            # Prepare category data with expression evaluation
            category_data = self._prepare_category_data(item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="productCategory",
                operation="update",
                resource_id=resource_id,
                data=category_data
            )
        except Exception as e:
            logger.error(f"Error in _update_product_category: {str(e)}")
            raise
    
    def _delete_product_category(self, credentials, item_index):
        """Delete a product category by ID"""
        try:
            # Get the category ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Category ID is required for delete operation")
            
            # Get force parameter (permanently delete or trash)
            force = self.get_node_parameter("force", item_index, False)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="productCategory",
                operation="delete",
                resource_id=resource_id,
                params={"force": force}
            )
        except Exception as e:
            logger.error(f"Error in _delete_product_category: {str(e)}")
            raise
    
    def _get_all_product_categories(self, credentials, item_index):
        """Get all product categories with filters"""
        try:
            # Get filters
            filters = self.get_node_parameter("filters", item_index, {})
            
            # Process filters with expression evaluation
            processed_filters = {}
            for key, value in filters.items():
                if value is not None:
                    processed_filters[key] = self._process_value_recursively(value, item_index)
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="productCategory",
                operation="getAll",
                params=processed_filters
            )
        except Exception as e:
            logger.error(f"Error in _get_all_product_categories: {str(e)}")
            raise

    def _get_product_category(self, credentials, item_index):
        """Get a single product category by ID"""
        try:
            # Get the category ID
            resource_id = self.get_node_parameter("resourceId", item_index)
            
            if not resource_id:
                raise ValueError("Category ID is required for get operation")
            
            # Make the API request
            return self._make_api_request(
                credentials=credentials,
                resource="productCategory",
                operation="get",
                resource_id=resource_id
            )
        except Exception as e:
            logger.error(f"Error in _get_product_category: {str(e)}")
            raise



    def _make_api_request(self, credentials, resource, operation, resource_id=None, data=None, params=None):
        """Make an API request to the WooCommerce REST API"""
        try:
            # Get the API URL
            api_url = self._get_api_url(credentials, resource)
            
            # Get authentication
            auth, query_params = self._get_auth(credentials)
            
            # Add query parameters for GET requests
            if operation in ["get", "getAll"] and query_params:
                # For get and getAll operations, add query parameters to the URL
                api_url += "?" + requests.compat.urlencode(query_params)
            
            
            # Make the request based on the operation type
            if operation == "get":
                response = requests.get(api_url, auth=auth)
            elif operation == "getAll":
                response = requests.get(api_url, auth=auth, params=params)
            elif operation == "create":
                response = requests.post(api_url, auth=auth, json=data)
            elif operation == "update":
                response = requests.put(f"{api_url}/{resource_id}", auth=auth, json=data)
            elif operation == "delete":
                response = requests.delete(f"{api_url}/{resource_id}", auth=auth)
            else:
                raise ValueError(f"Unsupported operation '{operation}'")
            
            # Check for request errors
            response.raise_for_status()
            
            # Return the JSON response
            return response.json()
        
        except Exception as e:
            logger.error(f"API request error: {str(e)}")
            raise


