import requests
import json
import copy
import logging
from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class HesabfaNode(BaseNode):
    """
    Hesabfa node for accounting system operations
    """
    
    type = "hesabfa"
    version = 1.0

    description = {
        "displayName": "Hesabfa",
        "name": "hesabfa",
        "icon": "file:hesabfa.svg",
        "group": ["input", "output"],
        "description": "Connect to Hesabfa accounting system API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True
    }

    properties = {

        "credentials": [
            {
                "name": "hesabfaTokenApi",
                "required": True
            }
        ],
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Item/Service", "value": "item"},
                    {"name": "Invoice", "value": "invoice"}
                ],
                "default": "item",
                "description": "Resource for operation"
            },

            # Item operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get", "value": "get", "description": "Get item/service information"},
                    {"name": "Get by Barcode", "value": "getByBarcode", "description": "Get item by barcode"},
                    {"name": "Get by ID", "value": "getById", "description": "Get by ID"},
                    {"name": "Get List", "value": "getList", "description": "Get list of items/services"},
                    {"name": "Inventory List", "value": "getInventoryList", "description": "Get inventory list"},
                    {"name": "Inventory List 2", "value": "getInventoryList2", "description": "Get inventory list version 2"}
                ],
                "default": "get",
                "display_options": {
                    "show": {
                        "resource": ["item"]
                    }
                }
            },

            # Invoice operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get", "value": "get", "description": "Get invoice information"},
                    {"name": "Get by ID", "value": "getById", "description": "Get by ID"},
                    {"name": "Get List", "value": "getList", "description": "Get list of invoices"},
                    {"name": "Save", "value": "save", "description": "Save/update invoice"},
                    {"name": "Delete", "value": "delete", "description": "Delete invoice"},
                    {"name": "Save Payment", "value": "savePayment", "description": "Register invoice payment/receipt"},
                    {"name": "Get Online URL", "value": "getOnlineUrl", "description": "Get online invoice URL"},
                    {"name": "Save Waybill", "value": "saveWaybill", "description": "Save waybill"},
                    {"name": "Change Payment Status", "value": "changePaymentStatus", "description": "Change payment status"},
                    {"name": "Change Delivery Status", "value": "changeDeliveryStatus", "description": "Change delivery status"}
                ],
                "default": "get",
                "display_options": {
                    "show": {
                        "resource": ["invoice"]
                    }
                }
            },

            # Common parameters for Get operations
            {
                "name": "code",
                "type": NodeParameterType.STRING,
                "display_name": "Code",
                "default": "",
                "description": "Item/Invoice code",
                "display_options": {
                    "show": {
                        "resource": ["item", "invoice"],
                        "operation": ["get"]
                    }
                }
            },

            # ID parameter for Get by ID operations
            {
                "name": "id",
                "type": NodeParameterType.STRING,
                "display_name": "ID",
                "default": "",
                "description": "Unique identifier",
                "display_options": {
                    "show": {
                        "resource": ["item", "invoice"],
                        "operation": ["getById", "delete"]
                    }
                }
            },

            # Barcode parameter for Item
            {
                "name": "barcode",
                "type": NodeParameterType.STRING,
                "display_name": "Barcode",
                "default": "",
                "description": "Item barcode",
                "display_options": {
                    "show": {
                        "resource": ["item"],
                        "operation": ["getByBarcode"]
                    }
                }
            },

            # Query Info for List operations
            {
                "name": "queryInfo",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Query Options",
                "description": "Filter, sort and pagination parameters",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["item", "invoice"],
                        "operation": ["getList", "getInventoryList", "getInventoryList2"]
                    }
                },
                "options": [
                    {
                        "name": "sortBy",
                        "type": NodeParameterType.STRING,
                        "display_name": "Sort By",
                        "description": "Field name for sorting (e.g., Name, Code, Date)",
                        "default": ""
                    },
                    {
                        "name": "sortDesc",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Sort Descending",
                        "description": "Sort in descending order",
                        "default": False
                    },
                    {
                        "name": "take",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Take",
                        "description": "Maximum number of records to return (default: 10)",
                        "default": 10,
                        "type_options": {
                            "minValue": 1,
                            "maxValue": 100
                        }
                    },
                    {
                        "name": "skip",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Skip",
                        "description": "Number of records to skip from the beginning",
                        "default": 0,
                        "type_options": {
                            "minValue": 0
                        }
                    },
                    {
                        "name": "search",
                        "type": NodeParameterType.STRING,
                        "display_name": "Search",
                        "description": "Search term",
                        "default": ""
                    },
                    {
                        "name": "searchFields",
                        "type": NodeParameterType.STRING,
                        "display_name": "Search Fields",
                        "description": "Comma-separated field names to search in (e.g., name,code)",
                        "default": ""
                    }
                ]
            },

            # Filters for advanced filtering
            {
                "name": "filters",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Filters",
                "description": "Advanced filtering options",
                "placeholder": "Add filter",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["item", "invoice"],
                        "operation": ["getList", "getInventoryList", "getInventoryList2"]
                    }
                },
                "options": [
                    {
                        "name": "conditions",
                        "display_name": "Conditions",
                        "values": [
                            {
                                "name": "property",
                                "type": NodeParameterType.STRING,
                                "display_name": "Property",
                                "description": "Field name to filter on",
                                "default": ""
                            },
                            {
                                "name": "operator",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Operator",
                                "description": "Filter operator",
                                "default": "=",
                                "options": [
                                    {"name": "Equals (=)", "value": "="},
                                    {"name": "Greater than (>)", "value": ">"},
                                    {"name": "Greater than or equal (>=)", "value": ">="},
                                    {"name": "Less than (<)", "value": "<"},
                                    {"name": "Less than or equal (<=)", "value": "<="},
                                    {"name": "Not equal (!=)", "value": "!="},
                                    {"name": "Contains (*)", "value": "*"},
                                    {"name": "Ends with (?*)", "value": "?*"},
                                    {"name": "Starts with (*?)", "value": "*?"},
                                    {"name": "In array (in)", "value": "in"}
                                ]
                            },
                            {
                                "name": "value",
                                "type": NodeParameterType.STRING,
                                "display_name": "Value",
                                "description": "Filter value (for 'in' operator, use comma-separated values)",
                                "default": ""
                            }
                        ]
                    }
                ]
            },

            # Invoice Data for Save operations
            {
                "name": "invoiceData",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Invoice Options",
                "description": "Invoice information for save operations",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["invoice"],
                        "operation": ["save", "saveWaybill", "changeDeliveryStatus"]
                    }
                },
                "options": [
                    {
                        "name": "number",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Invoice Number",
                        "description": "Invoice number (0 for auto-generated)",
                        "default": 0
                    },
                    {
                        "name": "invoiceType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Invoice Type",
                        "description": "Type of invoice",
                        "default": 0,
                        "options": [
                            {"name": "Sales Invoice", "value": 0},
                            {"name": "Purchase Invoice", "value": 1},
                            {"name": "Sales Return", "value": 2},
                            {"name": "Purchase Return", "value": 3}
                        ]
                    },
                    {
                        "name": "contactCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Contact Code",
                        "description": "Customer/vendor contact code",
                        "default": ""
                    },
                    {
                        "name": "contactTitle",
                        "type": NodeParameterType.STRING,
                        "display_name": "Contact Title",
                        "description": "Customer/vendor contact title",
                        "default": ""
                    },
                    {
                        "name": "date",
                        "type": NodeParameterType.STRING,
                        "display_name": "Invoice Date",
                        "description": "Invoice date (YYYY-MM-DD format)",
                        "default": ""
                    },
                    {
                        "name": "dueDate",
                        "type": NodeParameterType.STRING,
                        "display_name": "Due Date",
                        "description": "Invoice due date (YYYY-MM-DD format)",
                        "default": ""
                    },
                    {
                        "name": "reference",
                        "type": NodeParameterType.STRING,
                        "display_name": "Reference Number",
                        "description": "Invoice reference number",
                        "default": ""
                    },
                    {
                        "name": "note",
                        "type": NodeParameterType.STRING,
                        "display_name": "Notes",
                        "description": "Invoice notes",
                        "default": ""
                    },
                    {
                        "name": "tag",
                        "type": NodeParameterType.STRING,
                        "display_name": "Tag",
                        "description": "Invoice tag or label",
                        "default": ""
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "Invoice status",
                        "default": 0,
                        "options": [
                            {"name": "Open", "value": 0},
                            {"name": "Paid", "value": 1},
                            {"name": "Overdue", "value": 2},
                            {"name": "Draft", "value": 3}
                        ]
                    },
                    {
                        "name": "discount",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Total Discount",
                        "description": "Total discount amount",
                        "default": 0
                    },
                    {
                        "name": "tax",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Total Tax",
                        "description": "Total tax amount",
                        "default": 0
                    },
                    {
                        "name": "shipping",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Shipping Cost",
                        "description": "Shipping cost",
                        "default": 0
                    },
                    {
                        "name": "otherCosts",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Other Costs",
                        "description": "Other additional costs",
                        "default": 0
                    },
                    {
                        "name": "currency",
                        "type": NodeParameterType.STRING,
                        "display_name": "Currency",
                        "description": "Invoice currency",
                        "default": "IRR"
                    },
                    {
                        "name": "departmentCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Department Code",
                        "description": "Department code",
                        "default": ""
                    },
                    {
                        "name": "projectCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Project Code",
                        "description": "Project code",
                        "default": ""
                    },
                    {
                        "name": "salesmanCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Salesman Code",
                        "description": "Salesman code",
                        "default": ""
                    },
                    {
                        "name": "deliveryDate",
                        "type": NodeParameterType.STRING,
                        "display_name": "Delivery Date",
                        "description": "Delivery date (YYYY-MM-DD format)",
                        "default": ""
                    },
                    {
                        "name": "billNumber",
                        "type": NodeParameterType.STRING,
                        "display_name": "Bill Number",
                        "description": "Bill number",
                        "default": ""
                    },
                    {
                        "name": "businessCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Business Code",
                        "description": "Business transaction code",
                        "default": ""
                    }
                ]
            },

            # Invoice Items for Save operations
            {
                "name": "invoiceItems",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Invoice Items",
                "description": "Items in the invoice",
                "placeholder": "Add item",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["invoice"],
                        "operation": ["save"]
                    }
                },
                "options": [
                    {
                        "name": "items",
                        "display_name": "Items",
                        "values": [
                            {
                                "name": "itemCode",
                                "type": NodeParameterType.STRING,
                                "display_name": "Item Code",
                                "description": "Product/service code",
                                "default": ""
                            },
                            {
                                "name": "itemName",
                                "type": NodeParameterType.STRING,
                                "display_name": "Item Name",
                                "description": "Product/service name",
                                "default": ""
                            },
                            {
                                "name": "description",
                                "type": NodeParameterType.STRING,
                                "display_name": "Description",
                                "description": "Item description",
                                "default": ""
                            },
                            {
                                "name": "quantity",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Quantity",
                                "description": "Item quantity",
                                "default": 1
                            },
                            {
                                "name": "unit",
                                "type": NodeParameterType.STRING,
                                "display_name": "Unit",
                                "description": "Unit of measurement",
                                "default": ""
                            },
                            {
                                "name": "unitPrice",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Unit Price",
                                "description": "Price per unit",
                                "default": 0
                            },
                            {
                                "name": "discount",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Discount",
                                "description": "Item discount amount",
                                "default": 0
                            },
                            {
                                "name": "tax",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Tax",
                                "description": "Item tax amount",
                                "default": 0
                            },
                            {
                                "name": "serialNumber",
                                "type": NodeParameterType.STRING,
                                "display_name": "Serial Number",
                                "description": "Item serial number",
                                "default": ""
                            },
                            {
                                "name": "batchNumber",
                                "type": NodeParameterType.STRING,
                                "display_name": "Batch Number",
                                "description": "Item batch number",
                                "default": ""
                            },
                            {
                                "name": "expiryDate",
                                "type": NodeParameterType.STRING,
                                "display_name": "Expiry Date",
                                "description": "Item expiry date (YYYY-MM-DD format)",
                                "default": ""
                            },
                            {
                                "name": "warehouseCode",
                                "type": NodeParameterType.STRING,
                                "display_name": "Warehouse Code",
                                "description": "Warehouse code",
                                "default": ""
                            }
                        ]
                    }
                ]
            },

            # Payment Data for payment operations
            {
                "name": "paymentData",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Payment Information",
                "description": "Payment information",
                "placeholder": "Add option",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["invoice"],
                        "operation": ["savePayment", "changePaymentStatus"]
                    }
                },
                "options": [
                    {
                        "name": "amount",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Amount",
                        "description": "Payment amount",
                        "default": 0
                    },
                    {
                        "name": "date",
                        "type": NodeParameterType.STRING,
                        "display_name": "Payment Date",
                        "description": "Payment date (YYYY-MM-DD format)",
                        "default": ""
                    },
                    {
                        "name": "transactionType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Transaction Type",
                        "description": "Transaction type",
                        "default": "receipt",
                        "options": [
                            {"name": "Receipt", "value": "receipt"},
                            {"name": "Payment", "value": "payment"}
                        ]
                    },
                    {
                        "name": "bankCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Bank Code",
                        "description": "Bank code for payment",
                        "default": ""
                    },
                    {
                        "name": "accountCode",
                        "type": NodeParameterType.STRING,
                        "display_name": "Account Code",
                        "description": "Account code",
                        "default": ""
                    },
                    {
                        "name": "reference",
                        "type": NodeParameterType.STRING,
                        "display_name": "Reference Number",
                        "description": "Payment reference number",
                        "default": ""
                    },
                    {
                        "name": "checkNumber",
                        "type": NodeParameterType.STRING,
                        "display_name": "Check Number",
                        "description": "Check number for check payments",
                        "default": ""
                    },
                    {
                        "name": "checkDate",
                        "type": NodeParameterType.STRING,
                        "display_name": "Check Date",
                        "description": "Check date (YYYY-MM-DD format)",
                        "default": ""
                    },
                    {
                        "name": "checkAccountNumber",
                        "type": NodeParameterType.STRING,
                        "display_name": "Check Account Number",
                        "description": "Check account number",
                        "default": ""
                    },
                    {
                        "name": "note",
                        "type": NodeParameterType.STRING,
                        "display_name": "Notes",
                        "description": "Payment notes",
                        "default": ""
                    },
                    {
                        "name": "tag",
                        "type": NodeParameterType.STRING,
                        "display_name": "Tag",
                        "description": "Payment tag or label",
                        "default": ""
                    }
                ]
            }
        ]
    }
   
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the Hesabfa node operations
        """
        try:
            # Get input data using the base class method
            input_data = self.get_input_data()
            
            # Handle empty input data case
            if not input_data:
                input_data = [NodeExecutionData(json_data={}, binary_data=None)]
            
            result_items: List[NodeExecutionData] = []
            
            # Get resource and operation
            resource = self.get_node_parameter("resource", 0, "item")
            operation = self.get_node_parameter("operation", 0, "get")
            
            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Extract json_data properly
                    if hasattr(item, 'json_data'):
                        item_data = item.json_data if item.json_data else {}
                    elif isinstance(item, dict) and 'json_data' in item:
                        item_data = item['json_data'] if item['json_data'] else {}
                        # Convert dict to NodeExecutionData
                        item = NodeExecutionData(**item)
                    else:
                        item_data = {}
                    
                    result = None
                    
                    # Route to appropriate resource handler
                    if resource == "item":
                        result = self._handle_item(i, operation)
                    elif resource == "invoice":
                        result = self._handle_invoice(i, operation)
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")
                    
                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(NodeExecutionData(
                                json_data=res_item,
                                binary_data=None
                            ))
                    else:
                        result_items.append(NodeExecutionData(
                            json_data=result,
                            binary_data=None
                        ))
                
                except Exception as e:
                    logger.error(f"Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": resource,
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
            
            return [result_items]
        
        except Exception as e:
            logger.error(f"Error in Hesabfa node: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Hesabfa node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]
    
    def _get_api_config(self) -> Dict[str, Any]:
        """Get API configuration from credentials"""
        credentials = self.get_credentials("hesabfaTokenApi")
        
        if not credentials:
            raise ValueError("Hesabfa Token API credentials not found")
        
        api_key = credentials.get("apiKey")
        api_url = credentials.get("apiUrl", "https://api.hesabfa.com/v1").rstrip('/')
        
        config = {
            "apiKey": api_key,
            "apiUrl": api_url,
            "authType": "loginToken",
            "loginToken": credentials.get("loginToken")
        }
        
        year_id = credentials.get("yearId")
        if year_id:
            config["yearId"] = year_id
        
        return config
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a request to Hesabfa API"""
        config = self._get_api_config()
        
        url = f"{config['apiUrl']}/{endpoint}"
        
        # Build request data
        request_data = {
            "apiKey": config["apiKey"],
            "loginToken": config["loginToken"]
        }
        
        # Add yearId if present
        if "yearId" in config:
            request_data["yearId"] = config["yearId"]
        
        # Merge with operation-specific data
        request_data.update(data)
        
        try:
            response = requests.post(url, json=request_data, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            result = response.json()
            
            if not result.get("Success"):
                error_code = result.get("ErrorCode", "N/A")
                error_message = result.get("ErrorMessage", "Unknown error")
                raise Exception(f"Hesabfa API Error (Code: {error_code}): {error_message}")
            
            return result.get("Result")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"Request failed: {str(e)}")
    
    def _build_query_info(self, item_index: int) -> Dict[str, Any]:
        """Build queryInfo object from structured parameters"""
        query_info = {}
        
        # Get queryInfo parameters
        query_options = self.get_node_parameter("queryInfo", item_index, {})
        
        # Process basic query options
        if query_options.get("sortBy"):
            query_info["sortBy"] = query_options["sortBy"]
        
        if query_options.get("sortDesc") is not None:
            query_info["sortDesc"] = query_options["sortDesc"]
            
        if query_options.get("take"):
            query_info["take"] = query_options["take"]
            
        if query_options.get("skip") is not None:
            query_info["skip"] = query_options["skip"]
            
        if query_options.get("search"):
            query_info["search"] = query_options["search"]
            
        if query_options.get("searchFields"):
            # Convert comma-separated string to array
            search_fields = query_options["searchFields"].split(",")
            query_info["searchFields"] = [field.strip() for field in search_fields if field.strip()]
        
        # Process filters
        filters = self.get_node_parameter("filters", item_index, {})
        if filters and "conditions" in filters:
            filter_list = []
            for condition in filters["conditions"]:
                if condition.get("property") and condition.get("operator") and condition.get("value"):
                    filter_obj = {
                        "property": condition["property"],
                        "operator": condition["operator"],
                        "value": condition["value"]
                    }
                    
                    # Handle 'in' operator - convert comma-separated values to array
                    if condition["operator"] == "in" and isinstance(condition["value"], str):
                        filter_obj["value"] = [v.strip() for v in condition["value"].split(",") if v.strip()]
                    
                    filter_list.append(filter_obj)
            
            if filter_list:
                query_info["filters"] = filter_list
        
        return query_info
    
    def _build_invoice_data(self, item_index: int) -> Dict[str, Any]:
        """Build invoice object from structured parameters"""
        invoice_data = {}
        
        # Get invoice options
        invoice_options = self.get_node_parameter("invoiceData", item_index, {})
        
        # Process basic invoice fields
        for field in ["number", "invoiceType", "contactCode", "contactTitle", "date", "dueDate", 
                     "reference", "note", "tag", "status", "discount", "tax", "shipping", "otherCosts",
                     "currency", "departmentCode", "projectCode", "salesmanCode", "deliveryDate",
                     "billNumber", "businessCode"]:
            if field in invoice_options and invoice_options[field] is not None:
                invoice_data[field] = invoice_options[field]
        
        # Process invoice items
        invoice_items = self.get_node_parameter("invoiceItems", item_index, {})
        if invoice_items and "items" in invoice_items:
            items_list = []
            for item in invoice_items["items"]:
                if item.get("itemCode") and item.get("quantity"):
                    item_obj = {}
                    for field in ["itemCode", "itemName", "description", "quantity", "unit", "unitPrice", 
                                "discount", "tax", "serialNumber", "batchNumber", "expiryDate", "warehouseCode"]:
                        if field in item and item[field] is not None:
                            item_obj[field] = item[field]
                    items_list.append(item_obj)
            
            if items_list:
                invoice_data["invoiceItems"] = items_list
        
        return invoice_data
    
    def _build_payment_data(self, item_index: int) -> Dict[str, Any]:
        """Build payment object from structured parameters"""
        payment_data = {}
        
        # Get payment options
        payment_options = self.get_node_parameter("paymentData", item_index, {})
        
        # Get invoice ID for payment operations
        invoice_id = self.get_node_parameter("id", item_index, "")
        if invoice_id:
            payment_data["invoiceId"] = invoice_id
        
        # Process payment fields
        for field in ["amount", "date", "transactionType", "bankCode", "accountCode", "reference", 
                     "checkNumber", "checkDate", "checkAccountNumber", "note", "tag"]:
            if field in payment_options and payment_options[field] is not None:
                payment_data[field] = payment_options[field]
        
        return payment_data
    
    # Item operations
    def _handle_item(self, item_index: int, operation: str) -> Any:
        """Handle item resource operations"""
        # Validate that the operation is supported for items
        item_operations = ["get", "getByBarcode", "getById", "getList", "getInventoryList", "getInventoryList2"]
        if operation not in item_operations:
            raise ValueError(f"Operation '{operation}' is not supported for item resource")
        
        if operation == "get":
            code = self.get_node_parameter("code", item_index, "")
            return self._make_request("item/get", {"code": code})
        
        elif operation == "getByBarcode":
            barcode = self.get_node_parameter("barcode", item_index, "")
            return self._make_request("item/getbybarcode", {"barcode": barcode})
        
        elif operation == "getById":
            item_id = self.get_node_parameter("id", item_index, "")
            return self._make_request("item/getbyid", {"id": item_id})
        
        elif operation == "getList":
            query_info = self._build_query_info(item_index)
            return self._make_request("item/getitems", {"queryInfo": query_info})
        
        elif operation == "getInventoryList":
            query_info = self._build_query_info(item_index)
            return self._make_request("item/getinventorylist", {"queryInfo": query_info})
        
        elif operation == "getInventoryList2":
            query_info = self._build_query_info(item_index)
            return self._make_request("item/getinventorylist2", {"queryInfo": query_info})
        
        else:
            raise ValueError(f"Unsupported item operation: {operation}")
    
    # Invoice operations
    def _handle_invoice(self, item_index: int, operation: str) -> Any:
        """Handle invoice resource operations"""
        # Validate that the operation is supported for invoices
        invoice_operations = ["get", "getById", "getList", "save", "delete", "savePayment", "getOnlineUrl", "saveWaybill", "changePaymentStatus", "changeDeliveryStatus"]
        if operation not in invoice_operations:
            raise ValueError(f"Operation '{operation}' is not supported for invoice resource")
        
        if operation == "get":
            code = self.get_node_parameter("code", item_index, "")
            return self._make_request("invoice/get", {"number": code})
        
        elif operation == "getById":
            invoice_id = self.get_node_parameter("id", item_index, "")
            return self._make_request("invoice/getbyid", {"id": invoice_id})
        
        elif operation == "getList":
            query_info = self._build_query_info(item_index)
            return self._make_request("invoice/getinvoices", {"queryInfo": query_info})
        
        elif operation == "save":
            invoice_data = self._build_invoice_data(item_index)
            return self._make_request("invoice/save", {"invoice": invoice_data})
        
        elif operation == "delete":
            invoice_id = self.get_node_parameter("id", item_index, "")
            return self._make_request("invoice/delete", {"id": invoice_id})
        
        elif operation == "savePayment":
            payment_data = self._build_payment_data(item_index)
            return self._make_request("invoice/savepayment", payment_data)
        
        elif operation == "getOnlineUrl":
            invoice_id = self.get_node_parameter("id", item_index, "")
            return self._make_request("invoice/getonlineinvoiceurl", {"id": invoice_id})
        
        elif operation == "saveWaybill":
            invoice_data = self._build_invoice_data(item_index)
            return self._make_request("invoice/savewaybill", invoice_data)
        
        elif operation == "changePaymentStatus":
            payment_data = self._build_payment_data(item_index)
            return self._make_request("invoice/changepaymentstatus", payment_data)
        
        elif operation == "changeDeliveryStatus":
            invoice_data = self._build_invoice_data(item_index)
            return self._make_request("invoice/changedeliverystatus", invoice_data)
        
        else:
            raise ValueError(f"Unsupported invoice operation: {operation}")
