import requests
import json
import logging
from typing import Dict, List, Optional, Any
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

# Create logger for this module
logger = logging.getLogger(__name__)



class ShopifyNode(BaseNode):
    """
    Shopify node for interacting with Shopify API
    """

    type = "shopify"
    version = 1.0

    description = {
        "displayName": "Shopify",
        "name": "shopify",
        "version": 1,
        "icon": "file:shopify.svg",
        "group": ["output"],
        "description": "Consume Shopify API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "parameters": [
            {
                "name": "authentication",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Authentication",
                "options": [
                            {
                            "name": "Access Token",
                            "value": "shopifyAccessTokenApi"
                            },
                            {
                            "name": "OAuth2",
                            "value": "shopifyOAuth2Api"
                            },
                            {
                            "name": "API Key",
                            "value": "shopifyApi"
                            }
                    ],
                "default": "shopifyApi",
                "description": "Authentication method to use",
            },
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Order", "value": "order"},
                    {"name": "Product", "value": "product"},
                ],
                "default": "order",
                "description": "The resource to operate on",
            },
            # ========== ORDER OPERATIONS ==========
            {
                    "name": "operation",
                    "type": NodeParameterType.OPTIONS,
                    "display_name": "Operation",
                    "options": [
                        {
                            "name": "Create",
                            "value": "create",
                            "description": "Create an order",
                        },
                        {
                            "name": "Delete",
                            "value": "delete",
                            "description": "Delete an order",
                        },
                        {
                            "name": "Get",
                            "value": "get",
                            "description": "Get an order",
                        },
                        {
                            "name": "Get Many",
                            "value": "getAll",
                            "description": "Get many orders",
                        },
                        {
                            "name": "Update",
                            "value": "update",
                            "description": "Update an order",
                        },
                    ],
                    "default": "create",
                    "display_options": {"show": {"resource": ["order"]}},
                },
                # ========== PRODUCT OPERATIONS ==========
                {
                    "name": "operation",
                    "type": NodeParameterType.OPTIONS,
                    "display_name": "Operation",
                    "options": [
                        {
                            "name": "Create",
                            "value": "create",
                            "description": "Create a product",
                        },
                        {
                            "name": "Delete",
                            "value": "delete",
                            "description": "Delete a product",
                        },
                        {
                            "name": "Get",
                            "value": "get",
                            "description": "Get a product",
                        },
                        {
                            "name": "Get Many",
                            "value": "getAll",
                            "description": "Get many products",
                        },
                        {
                            "name": "Update",
                            "value": "update",
                            "description": "Update a product",
                        },
                    ],
                    "default": "create",
                    "display_options": {"show": {"resource": ["product"]}},
                },
                # ========== ORDER:CREATE FIELDS ==========
                {
                "displayName": "Additional Fields",
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "placeholder": "Add Field",
                "displayOptions": {
                "show": {
                    "operation": ["create"],
                    "resource": ["order"]
                }
                },
                "default": {},
                "options": [
                {
                    "displayName": "Billing Address",
                    "name": "billingAddressUi",
                    "placeholder": "Add Billing Address",
                    "type": NodeParameterType.COLLECTION,
                    "default": {},
                    "typeOptions": {
                    "multipleValues": False
                    },
                    "options": [
                    {
                        "name": "billingAddressValues",
                        "displayName": "Billing Address",
                        "values": [
                        { "displayName": "First Name", "name": "firstName", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Last Name", "name": "lastName", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Company", "name": "company", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Country", "name": "country", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Address Line 1", "name": "address1", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Address Line 2", "name": "address2", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "City", "name": "city", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Province", "name": "province", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Zip Code", "name": "zip", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Phone", "name": "phone", "type": NodeParameterType.STRING, "default": "" }
                        ]
                    }
                    ]
                },
                {
                    "displayName": "Discount Codes",
                    "name": "discountCodesUi",
                    "placeholder": "Add Discount Code",
                    "type": NodeParameterType.COLLECTION,
                    "default": {},
                    "typeOptions": {
                    "multipleValues": True
                    },
                    "options": [
                    {
                        "name": "discountCodesValues",
                        "displayName": "Discount Code",
                        "values": [
                        {
                            "displayName": "Amount",
                            "name": "amount",
                            "type": NodeParameterType.STRING,
                            "default": "",
                            "description": "The amount that's deducted from the order total"
                        },
                        {
                            "displayName": "Code",
                            "name": "code",
                            "type": NodeParameterType.STRING,
                            "default": "",
                            "description": "When the associated discount application is of type code"
                        },
                        {
                            "displayName": "Type",
                            "name": "type",
                            "type": NodeParameterType.OPTIONS,
                            "options": [
                            {
                                "name": "Fixed Amount",
                                "value": "fixedAmount",
                                "description": "Applies amount as a unit of the store's currency"
                            },
                            {
                                "name": "Percentage",
                                "value": "percentage",
                                "description": "Applies a discount of amount as a percentage of the order total"
                            },
                            {
                                "name": "Shipping",
                                "value": "shipping",
                                "description": "Applies a free shipping discount on orders that have a shipping rate less than or equal to amount"
                            }
                            ],
                            "default": "fixedAmount",
                            "description": "When the associated discount application is of type code"
                        }
                        ]
                    }
                    ]
                },
                {
                    "displayName": "Email",
                    "name": "email",
                    "type": NodeParameterType.STRING,
                    "placeholder": "name@email.com",
                    "default": "",
                    "description": "The customer's email address"
                },
                {
                    "displayName": "Fulfillment Status",
                    "name": "fulfillmentStatus",
                    "type": NodeParameterType.OPTIONS,
                    "options": [
                    { "name": "Fulfilled", "value": "fulfilled", "description": "Every line item in the order has been fulfilled" },
                    { "name": "Null", "value": "null", "description": "None of the line items in the order have been fulfilled" },
                    { "name": "Partial", "value": "partial", "description": "At least one line item in the order has been fulfilled" },
                    {
                        "name": "Restocked",
                        "value": "restocked",
                        "description": "Every line item in the order has been restocked and the order canceled"
                    }
                    ],
                    "default": "",
                    "description": "The order's status in terms of fulfilled line items"
                },
                {
                    "displayName": "Inventory Behaviour",
                    "name": "inventoryBehaviour",
                    "type": NodeParameterType.OPTIONS,
                    "options": [
                    { "name": "Bypass", "value": "bypass", "description": "Do not claim inventory" },
                    {
                        "name": "Decrement Ignoring Policy",
                        "value": "decrementIgnoringPolicy",
                        "description": "Ignore the product's inventory policy and claim inventory"
                    },
                    {
                        "name": "Decrement Obeying Policy",
                        "value": "decrementObeyingPolicy",
                        "description": "Follow the product's inventory policy and claim inventory, if possible"
                    }
                    ],
                    "default": "bypass",
                    "description": "The behaviour to use when updating inventory"
                },
                {
                    "displayName": "Location Name or ID",
                    "name": "locationId",
                    "type": NodeParameterType.OPTIONS,
                    "typeOptions": {
                    "loadOptionsMethod": "getLocations"
                    },
                    "default": "",
                    "description": "The ID of the physical location where the order was processed."
                },
                {
                    "displayName": "Note",
                    "name": "note",
                    "type": NodeParameterType.STRING,
                    "default": "",
                    "description": "An optional note that a shop owner can attach to the order"
                },
                {
                    "displayName": "Send Fulfillment Receipt",
                    "name": "sendFulfillmentReceipt",
                    "type": NodeParameterType.BOOLEAN,
                    "default": False,
                    "description": "Whether to send a shipping confirmation to the customer"
                },
                {
                    "displayName": "Send Receipt",
                    "name": "sendReceipt",
                    "type": NodeParameterType.BOOLEAN,
                    "default": False,
                    "description": "Whether to send an order confirmation to the customer"
                },
                {
                    "displayName": "Shipping Address",
                    "name": "shippingAddressUi",
                    "placeholder": "Add Shipping",
                    "type": NodeParameterType.COLLECTION,
                    "default": {},
                    "typeOptions": {
                    "multipleValues": False
                    },
                    "options": [
                    {
                        "name": "shippingAddressValues",
                        "displayName": "Shipping Address",
                        "values": [
                        { "displayName": "First Name", "name": "firstName", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Last Name", "name": "lastName", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Company", "name": "company", "type":NodeParameterType.STRING, "default": "" },
                        { "displayName": "Country", "name": "country", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Address Line 1", "name": "address1", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Address Line 2", "name": "address2", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "City", "name": "city", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Province", "name": "province", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Zip Code", "name": "zip", "type": NodeParameterType.STRING, "default": "" },
                        { "displayName": "Phone", "name": "phone", "type": NodeParameterType.STRING, "default": "" }
                        ]
                    }
                    ]
                },
                {
                    "displayName": "Source Name",
                    "name": "sourceName",
                    "type": NodeParameterType.STRING,
                    "default": "",
                    "description": "Where the order originated"
                },
                {
                    "displayName": "Tags",
                    "name": "tags",
                    "type": NodeParameterType.STRING,
                    "default": "",
                    "description": "Tags attached to the order"
                },
                {
                    "displayName": "Test",
                    "name": "test",
                    "type": NodeParameterType.BOOLEAN,
                    "default": False,
                    "description": "Whether this is a test order"
                }
                ]
            },
            {
                "displayName": "Line Items",
                "name": "limeItemsUi",
                "placeholder": "Add Line Item",
                "type": NodeParameterType.COLLECTION,
                "typeOptions": {
                    "multipleValues": True
                },
                "displayOptions": {
                    "show": {
                    "resource": ["order"],
                    "operation": ["create"]
                    }
                },
                "default": {},
                "options": [
                    {
                    "displayName": "Line Item",
                    "name": "lineItemValues",
                    "values": [
                        {
                        "displayName": "Product Name or ID",
                        "name": "productId",
                        "type": NodeParameterType.OPTIONS,
                        "typeOptions": {
                            "loadOptionsMethod": "getProducts"
                        },
                        "default": "",
                        "description": "The ID of the product that the line item belongs to. Choose from the list, or specify an ID using an <a href=\"https://docs.n8n.io/code/expressions/\">expression</a>."
                        },
                        {
                        "displayName": "Variant ID",
                        "name": "variantId",
                        "type": NodeParameterType.STRING,
                        "default": "",
                        "description": "The ID of the product variant"
                        },
                        {
                        "displayName": "Title",
                        "name": "title",
                        "type": NodeParameterType.STRING,
                        "default": "",
                        "description": "The title of the product"
                        },
                        {
                        "displayName": "Grams",
                        "name": "grams",
                        "type": NodeParameterType.STRING,
                        "default": "",
                        "description": "The weight of the item in grams"
                        },
                        {
                        "displayName": "Quantity",
                        "name": "quantity",
                        "type": NodeParameterType.NUMBER,
                        "typeOptions": {
                            "minValue": 1
                        },
                        "default": 1,
                        "description": "The number of items that were purchased"
                        },
                        {
                        "displayName": "Price",
                        "name": "price",
                        "type": NodeParameterType.STRING,
                        "default": ""
                        }
                    ]
                    }
                ]
            },
            # ========== ORDER:DELETE ==========
            {
                "name": "orderId",
                "type": NodeParameterType.STRING,
                "display_name": "Order ID",
                "default": "",
                "required": True,
                "description": "ID of the order",
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["delete"],
                    }
                },
            },
            # ========== ORDER:GET ==========
            {
                "name": "orderId",
                "type": NodeParameterType.STRING,
                "display_name": "Order ID",
                "default": "",
                "required": True,
                "description": "ID of the order",
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["get"],
                    }
                },
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["get"],
                    }
                },
                "options": [
                    {
                        "name": "fields",
                        "type": NodeParameterType.STRING,
                        "display_name": "Fields",
                        "default": "",
                        "description": "Fields the order will return, formatted as a string of comma-separated values",
                    },
                ],
            },
            # ========== ORDER:GETALL ==========
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results or only up to a given limit",
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["getAll"],
                    }
                },
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 50,
                "type_options": {"minValue": 1, "maxValue": 250},
                "description": "Max number of results to return",
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["getAll"],
                        "returnAll": [False],
                    }
                },
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["getAll"],
                    }
                },
                "options": [
                    {
                        "name": "attributionAppId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Attribution App ID",
                        "default": "",
                        "description": "Show orders attributed to a certain app, specified by the app ID",
                    },
                    {
                        "name": "createdAtMin",
                        "type": NodeParameterType.STRING,
                        "display_name": "Created At Min",
                        "default": "",
                        "description": "Show orders created at or after date",
                    },
                    {
                        "name": "createdAtMax",
                        "type": NodeParameterType.STRING,
                        "display_name": "Created At Max",
                        "default": "",
                        "description": "Show orders created at or before date",
                    },
                    {
                        "name": "financialStatus",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Financial Status",
                        "options": [
                            {"name": "Any", "value": "any"},
                            {"name": "Authorized", "value": "authorized"},
                            {"name": "Paid", "value": "paid"},
                            {"name": "Partially Paid", "value": "partiallyPaid"},
                            {"name": "Partially Refunded", "value": "partiallyRefunded"},
                            {"name": "Pending", "value": "pending"},
                            {"name": "Refunded", "value": "refunded"},
                            {"name": "Unpaid", "value": "unpaid"},
                            {"name": "Voided", "value": "voided"},
                        ],
                        "default": "any",
                        "description": "Filter orders by their financial status",
                    },
                    {
                        "name": "fulfillmentStatus",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Fulfillment Status",
                        "options": [
                            {"name": "Any", "value": "any"},
                            {"name": "Partial", "value": "partial"},
                            {"name": "Shipped", "value": "shipped"},
                            {"name": "Unfulfilled", "value": "unfulfilled"},
                            {"name": "Unshipped", "value": "unshipped"},
                        ],
                        "default": "any",
                        "description": "Filter orders by their fulfillment status",
                    },
                    {
                        "name": "fields",
                        "type": NodeParameterType.STRING,
                        "display_name": "Fields",
                        "default": "",
                        "description": "Fields the orders will return, formatted as a string of comma-separated values",
                    },
                    {
                        "name": "ids",
                        "type": NodeParameterType.STRING,
                        "display_name": "IDs",
                        "default": "",
                        "description": "Retrieve only orders specified by a comma-separated list of order IDs",
                    },
                    {
                        "name": "processedAtMax",
                        "type": NodeParameterType.STRING,
                        "display_name": "Processed At Max",
                        "default": "",
                        "description": "Show orders imported at or before date",
                    },
                    {
                        "name": "processedAtMin",
                        "type": NodeParameterType.STRING,
                        "display_name": "Processed At Min",
                        "default": "",
                        "description": "Show orders imported at or after date",
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "options": [
                            {"name": "Any", "value": "any"},
                            {"name": "Cancelled", "value": "cancelled"},
                            {"name": "Closed", "value": "closed"},
                            {"name": "Open", "value": "open"},
                        ],
                        "default": "open",
                        "description": "Filter orders by their status",
                    },
                    {
                        "name": "sinceId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Since ID",
                        "default": "",
                        "description": "Show orders after the specified ID",
                    },
                    {
                        "name": "updatedAtMax",
                        "type": NodeParameterType.STRING,
                        "display_name": "Updated At Max",
                        "default": "",
                        "description": "Show orders last updated at or after date",
                    },
                    {
                        "name": "updatedAtMin",
                        "type": NodeParameterType.STRING,
                        "display_name": "Updated At Min",
                        "default": "",
                        "description": "Show orders last updated at or before date",
                    },
                ],
            },
            # ========== ORDER:UPDATE ==========
            {
                "name": "orderId",
                "type": NodeParameterType.STRING,
                "display_name": "Order ID",
                "default": "",
                "required": True,
                "description": "ID of the order",
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["update"],
                    }
                },
            },
            {
                "name": "updateFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Update Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["order"],
                        "operation": ["update"],
                    }
                },
                "options": [
                    {
                        "name": "email",
                        "type": NodeParameterType.STRING,
                        "display_name": "Email",
                        "default": "",
                        "description": "The customer's email address",
                    },
                    {
                        "name": "locationId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Location ID",
                        "default": "",
                        "description": "The ID of the physical location where the order was processed",
                    },
                    {
                        "name": "note",
                        "type": NodeParameterType.STRING,
                        "display_name": "Note",
                        "default": "",
                        "description": "An optional note that a shop owner can attach to the order",
                    },
                    {
                        "displayName": "Shipping Address",
                        "name": "shippingAddressUi",
                        "placeholder": "Add Shipping",
                        "type": NodeParameterType.COLLECTION,
                        "default": {},
                        "typeOptions": {
                            "multipleValues": False
                        },
                        "options": [
                            {
                            "name": "shippingAddressValues",
                            "displayName": "Shipping Address",
                            "values": [
                                {
                                "displayName": "First Name",
                                "name": "firstName",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Last Name",
                                "name": "lastName",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Company",
                                "name": "company",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Country",
                                "name": "country",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Address Line 1",
                                "name": "address1",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Address Line 2",
                                "name": "address2",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "City",
                                "name": "city",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Province",
                                "name": "province",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Zip Code",
                                "name": "zip",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                },
                                {
                                "displayName": "Phone",
                                "name": "phone",
                                "type": NodeParameterType.STRING,
                                "default": ""
                                }
                            ]
                            }
                        ]
                    },

                    {
                        "name": "sourceName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Source Name",
                        "default": "",
                        "description": "Where the order originated",
                    },
                    {
                        "name": "tags",
                        "type": NodeParameterType.STRING,
                        "display_name": "Tags",
                        "default": "",
                        "description": "Tags attached to the order, formatted as a string of comma-separated values",
                    },
                ],
            },
            # ========== PRODUCT:CREATE ==========
            {
                "name": "title",
                "type": NodeParameterType.STRING,
                "display_name": "Title",
                "default": "",
                "required": True,
                "description": "The name of the product",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["create"],
                    }
                },
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["create"],
                    }
                },
                "options": [
                    {
                        "name": "body_html",
                        "type": NodeParameterType.STRING,
                        "display_name": "Body HTML",
                        "default": "",
                        "description": "A description of the product. Supports HTML formatting",
                    },
                    {
                        "name": "handle",
                        "type": NodeParameterType.STRING,
                        "display_name": "Handle",
                        "default": "",
                        "description": "A unique human-friendly string for the product. Automatically generated from the product's title",
                    },
                    {
                        "name": "images",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Images",
                        "placeholder": "Add Image Field",
                        "type_options": {"multipleValues": True},
                        "default": {},
                        "description": "A list of product image objects, each one representing an image associated with the product",
                        "options": [
                            {
                                "name": "src",
                                "type": NodeParameterType.STRING,
                                "display_name": "Source",
                                "default": "",
                                "description": "Specifies the location of the product image",
                            },
                            {
                                "name": "alt",
                                "type": NodeParameterType.STRING,
                                "display_name": "Alt",
                                "default": "",
                                "description": "Alternative text for the image",
                            },
                            {
                                "name": "position",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Position",
                                "default": 1,
                                "description": "The order of the product image in the list",
                            },
                        ],
                    },
                    {
                        "name": "productOptions",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Options",
                        "placeholder": "Add option",
                        "type_options": {"multipleValues": True},
                        "default": {},
                        "description": "The custom product property names like Size, Color, and Material",
                        "options": [
                            {
                                "name": "name",
                                "type": NodeParameterType.STRING,
                                "display_name": "Name",
                                "default": "",
                                "description": "Option's name",
                            },
                            {
                                "name": "value",
                                "type": NodeParameterType.STRING,
                                "display_name": "Value",
                                "default": "",
                                "description": "Option's values",
                            },
                        ],
                    },
                    {
                        "name": "product_type",
                        "type": NodeParameterType.STRING,
                        "display_name": "Product Type",
                        "default": "",
                        "description": "A categorization for the product used for filtering and searching products",
                    },
                    {
                        "name": "published_at",
                        "type": NodeParameterType.STRING,
                        "display_name": "Published At",
                        "default": "",
                        "description": "The date and time (ISO 8601 format) when the product was published",
                    },
                    {
                        "name": "published_scope",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Published Scope",
                        "options": [
                            {"name": "Global", "value": "global"},
                            {"name": "Web", "value": "web"},
                        ],
                        "default": "global",
                        "description": "Whether the product is published to the Point of Sale channel",
                    },
                    {
                        "name": "tags",
                        "type": NodeParameterType.STRING,
                        "display_name": "Tags",
                        "default": "",
                        "description": "A string of comma-separated tags that are used for filtering and search",
                    },
                    {
                        "name": "template_suffix",
                        "type": NodeParameterType.STRING,
                        "display_name": "Template Suffix",
                        "default": "",
                        "description": "The suffix of the Liquid template used for the product page",
                    },
                    {
                        "name": "vendor",
                        "type": NodeParameterType.STRING,
                        "display_name": "Vendor",
                        "default": "",
                        "description": "The name of the product's vendor",
                    },
                ],
            },
            # ========== PRODUCT:UPDATE ==========
            {
                "name": "productId",
                "type": NodeParameterType.STRING,
                "display_name": "Product ID",
                "default": "",
                "required": True,
                "description": "ID of the product",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["update"],
                    }
                },
            },
            {
                "name": "updateFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Update Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["update"],
                    }
                },
                "options": [
                    {
                        "name": "body_html",
                        "type": NodeParameterType.STRING,
                        "display_name": "Body HTML",
                        "default": "",
                        "description": "A description of the product. Supports HTML formatting",
                    },
                    {
                        "name": "handle",
                        "type": NodeParameterType.STRING,
                        "display_name": "Handle",
                        "default": "",
                        "description": "A unique human-friendly string for the product",
                    },
                    {
                        "name": "images",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Images",
                        "placeholder": "Add Image Field",
                        "type_options": {"multipleValues": True},
                        "default": {},
                        "description": "A list of product image objects",
                        "options": [
                            {
                                "name": "src",
                                "type": NodeParameterType.STRING,
                                "display_name": "Source",
                                "default": "",
                                "description": "Specifies the location of the product image",
                            },
                            {
                                "name": "alt",
                                "type": NodeParameterType.STRING,
                                "display_name": "Alt",
                                "default": "",
                                "description": "Alternative text for the image",
                            },
                            {
                                "name": "position",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Position",
                                "default": 1,
                                "description": "The order of the product image in the list",
                            },
                        ],
                    },
                    {
                        "name": "productOptions",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Options",
                        "placeholder": "Add option",
                        "type_options": {"multipleValues": True},
                        "default": {},
                        "description": "The custom product property names like Size, Color, and Material",
                        "options": [
                            {
                                "name": "name",
                                "type": NodeParameterType.STRING,
                                "display_name": "Name",
                                "default": "",
                                "description": "Option's name",
                            },
                            {
                                "name": "value",
                                "type": NodeParameterType.STRING,
                                "display_name": "Value",
                                "default": "",
                                "description": "Option's values",
                            },
                        ],
                    },
                    {
                        "name": "product_type",
                        "type": NodeParameterType.STRING,
                        "display_name": "Product Type",
                        "default": "",
                        "description": "A categorization for the product used for filtering and searching products",
                    },
                    {
                        "name": "published_at",
                        "type": NodeParameterType.STRING,
                        "display_name": "Published At",
                        "default": "",
                        "description": "The date and time when the product was published",
                    },
                    {
                        "name": "published_scope",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Published Scope",
                        "options": [
                            {"name": "Global", "value": "global"},
                            {"name": "Web", "value": "web"},
                        ],
                        "default": "global",
                        "description": "Whether the product is published to the Point of Sale channel",
                    },
                    {
                        "name": "tags",
                        "type": NodeParameterType.STRING,
                        "display_name": "Tags",
                        "default": "",
                        "description": "A string of comma-separated tags",
                    },
                    {
                        "name": "template_suffix",
                        "type": NodeParameterType.STRING,
                        "display_name": "Template Suffix",
                        "default": "",
                        "description": "The suffix of the Liquid template used for the product page",
                    },
                    {
                        "name": "title",
                        "type": NodeParameterType.STRING,
                        "display_name": "Title",
                        "default": "",
                        "description": "The name of the product",
                    },
                    {
                        "name": "vendor",
                        "type": NodeParameterType.STRING,
                        "display_name": "Vendor",
                        "default": "",
                        "description": "The name of the product's vendor",
                    },
                ],
            },
            # ========== PRODUCT:DELETE ==========
            {
                "name": "productId",
                "type": NodeParameterType.STRING,
                "display_name": "Product ID",
                "default": "",
                "required": True,
                "description": "ID of the product",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["delete"],
                    }
                },
            },
            # ========== PRODUCT:GET ==========
            {
                "name": "productId",
                "type": NodeParameterType.STRING,
                "display_name": "Product ID",
                "default": "",
                "required": True,
                "description": "ID of the product",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["get"],
                    }
                },
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["get"],
                    }
                },
                "options": [
                    {
                        "name": "fields",
                        "type": NodeParameterType.STRING,
                        "display_name": "Fields",
                        "default": "",
                        "description": "Fields the product will return, formatted as a string of comma-separated values",
                    },
                ],
            },
            # ========== PRODUCT:GETALL ==========
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results or only up to a given limit",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["getAll"],
                    }
                },
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 50,
                "type_options": {"minValue": 1, "maxValue": 250},
                "description": "Max number of results to return",
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["getAll"],
                        "returnAll": [False],
                    }
                },
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["product"],
                        "operation": ["getAll"],
                    }
                },
                "options": [
                    {
                        "name": "collection_id",
                        "type": NodeParameterType.STRING,
                        "display_name": "Collection ID",
                        "default": "",
                        "description": "Filter results by product collection ID",
                    },
                    {
                        "name": "created_at_max",
                        "type": NodeParameterType.STRING,
                        "display_name": "Created At Max",
                        "default": "",
                        "description": "Show products created before date",
                    },
                    {
                        "name": "created_at_min",
                        "type": NodeParameterType.STRING,
                        "display_name": "Created At Min",
                        "default": "",
                        "description": "Show products created after date",
                    },
                    {
                        "name": "fields",
                        "type": NodeParameterType.STRING,
                        "display_name": "Fields",
                        "default": "",
                        "description": "Show only certain fields, specified by a comma-separated list of field names",
                    },
                    {
                        "name": "handle",
                        "type": NodeParameterType.STRING,
                        "display_name": "Handle",
                        "default": "",
                        "description": "Filter results by product handle",
                    },
                    {
                        "name": "ids",
                        "type": NodeParameterType.STRING,
                        "display_name": "IDs",
                        "default": "",
                        "description": "Return only products specified by a comma-separated list of product IDs",
                    },
                    {
                        "name": "presentment_currencies",
                        "type": NodeParameterType.STRING,
                        "display_name": "Presentment Currencies",
                        "default": "",
                        "description": "Return presentment prices in only certain currencies",
                    },
                    {
                        "name": "product_type",
                        "type": NodeParameterType.STRING,
                        "display_name": "Product Type",
                        "default": "",
                        "description": "Filter results by product type",
                    },
                    {
                        "name": "published_at_max",
                        "type": NodeParameterType.STRING,
                        "display_name": "Published At Max",
                        "default": "",
                        "description": "Show products published before date",
                    },
                    {
                        "name": "published_at_min",
                        "type": NodeParameterType.STRING,
                        "display_name": "Published At Min",
                        "default": "",
                        "description": "Show products published after date",
                    },
                    {
                        "name": "published_status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Published Status",
                        "options": [
                            {"name": "Any", "value": "any"},
                            {"name": "Published", "value": "published"},
                            {"name": "Unpublished", "value": "unpublished"},
                        ],
                        "default": "any",
                        "description": "Return products by their published status",
                    },
                    {
                        "name": "title",
                        "type": NodeParameterType.STRING,
                        "display_name": "Title",
                        "default": "",
                        "description": "Filter results by product title",
                    },
                    {
                        "name": "updated_at_max",
                        "type": NodeParameterType.STRING,
                        "display_name": "Updated At Max",
                        "default": "",
                        "description": "Show products last updated before date",
                    },
                    {
                        "name": "updated_at_min",
                        "type": NodeParameterType.STRING,
                        "display_name": "Updated At Min",
                        "default": "",
                        "description": "Show products last updated after date",
                    },
                    {
                        "name": "vendor",
                        "type": NodeParameterType.STRING,
                        "display_name": "Vendor",
                        "default": "",
                        "description": "Filter results by product vendor",
                    },
                ],
            },
        ],
        "credentials": [
            {
                "name": "shopifyApi",
                "required": True,
                "display_options": {
                    "show": {
                        "authentication": ["shopifyApi"],
                    },
                },
            },
            {
                "name": "shopifyAccessTokenApi",
                "required": True,
                "display_options": {
                    "show": {
                        "authentication": ["shopifyAccessTokenApi"],
                    },
                },
            },
            {
                "name": "shopifyOAuth2Api",
                "required": True,
                "display_options": {
                    "show": {
                        "authentication": ["shopifyOAuth2Api"],
                    },
                },
            },
        ],
    }

    icon = "shopify.svg"
    color = "#95bf47"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Shopify operation and return properly formatted data"""

        try:
            # Get input data using the new method signature
            input_data = self.get_input_data()

            result_items: List[NodeExecutionData] = []

            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Get parameters for this item using the new method
                    resource = self.get_node_parameter("resource", i, "order")
                    operation = self.get_node_parameter("operation", i, "create")

                    # Execute the appropriate operation
                    if resource == "order":
                        if operation == "create":
                            result = self._create_order(i)
                        elif operation == "delete":
                            result = self._delete_order(i)
                        elif operation == "get":
                            result = self._get_order(i)
                        elif operation == "getAll":
                            result = self._get_all_orders(i)
                        elif operation == "update":
                            result = self._update_order(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    elif resource == "product":
                        if operation == "create":
                            result = self._create_product(i)
                        elif operation == "delete":
                            result = self._delete_product(i)
                        elif operation == "get":
                            result = self._get_product(i)
                        elif operation == "getAll":
                            result = self._get_all_products(i)
                        elif operation == "update":
                            result = self._update_product(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")
                    
                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(
                                NodeExecutionData(json_data=res_item, binary_data=None)
                            )
                    else:
                        result_items.append(
                            NodeExecutionData(json_data=result, binary_data=None)
                        )
                        
                except Exception as e:
                    # Create error data following project pattern
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter(
                                "resource", i, "order"
                            ),
                            "operation": self.get_node_parameter(
                                "operation", i, "create"
                            ),
                            "item_index": i,
                        },
                        binary_data=None,
                    )

                    result_items.append(error_item)

            return [result_items]

        except Exception as e:
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in Shopify node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _get_credential_name(self) -> str:
        """Get the credential name based on authentication method"""
        auth_method = self.get_node_parameter("authentication", 0, "shopifyApi")
        print(f'auth_method (get_credential_name) : {auth_method}')
        credential_map = {
            "shopifyApi": "shopifyApi",
            "shopifyAccessTokenApi": "shopifyAccessTokenApi",
            "shopifyOAuth2Api": "shopifyOAuth2Api",
        }
        
        return credential_map.get(auth_method, "shopifyApi")

    def _get_api_url(self) -> str:
        """Get Shopify API URL with credentials"""
        try:
            print('Getting API URL')
            credential_name = self._get_credential_name()
            print(f'credential_name : {credential_name}')
            
            credentials = self.get_credentials(credential_name)
            print(f'credentials : {credentials}')
            
            if not credentials:
                raise ValueError(
                    f"Shopify credentials '{credential_name}' not found. "
                    f"Please create and connect Shopify credentials to this node. "
                    f"Go to Credentials > Create New > {credential_name} and then link it to this Shopify node."
                )

            shop_subdomain = credentials.get("shopSubdomain")
            
            if not shop_subdomain:
                raise ValueError("Shop subdomain is required for Shopify API")
            print(f"https://{shop_subdomain}.myshopify.com/admin/api/2024-07")
            # Using API version 2024-07 as per n8n implementation
            return f"https://{shop_subdomain}.myshopify.com/admin/api/2024-07"
            
        except Exception as e:
            logger.error(f"Error getting API URL: {str(e)}", exc_info=True)
            raise

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for Shopify API"""
        auth_method = self.get_node_parameter("authentication", 0, "shopifyApi")
        credential_name = self._get_credential_name()
        credentials = self.get_credentials(credential_name)
        
        if not credentials:
            raise ValueError(
                f"Shopify credentials '{credential_name}' not found. "
                f"Please create and connect Shopify credentials to this node. "
                f"Go to Credentials > Create New > {credential_name} and then link it to this Shopify node."
            )

        headers = {"Content-Type": "application/json"}

        # Support different authentication methods
        if auth_method == "shopifyAccessTokenApi":
            access_token = credentials.get("accessToken")
            if access_token:
                headers["X-Shopify-Access-Token"] = access_token
            else:
                raise ValueError("Access token not found in credentials")
        elif auth_method == "shopifyOAuth2Api":
            # OAuth2 credentials require completing the OAuth flow first
            # Debug: print what's in credentials
            print(f"OAuth2 credentials keys: {credentials.keys()}")
            print(f"OAuth2 credentials content: {credentials}")
            
            # Try different possible locations for the access token
            access_token = None
            
            # Option 1: Direct accessToken field
            if "accessToken" in credentials:
                access_token = credentials.get("accessToken")
            # Option 2: oauth_token_data['access_token']
            elif "oauth_token_data" in credentials:
                oauth_data = credentials.get("oauth_token_data", {})
                access_token = oauth_data.get("access_token")
            # Option 3: oauthTokenData['access_token'] (camelCase version)
            elif "oauthTokenData" in credentials:
                oauth_data = credentials.get("oauthTokenData", {})
                if isinstance(oauth_data, dict):
                    access_token = oauth_data.get("access_token")
            
            if access_token:
                headers["X-Shopify-Access-Token"] = access_token
            else:
                # Provide helpful guidance for OAuth2 setup
                available_fields = list(credentials.keys())
                if available_fields == ['shopSubdomain']:
                    suggestion = (
                        "\n\n💡 QUICK FIX: Since you have a Shopify Access Token (shpat_...), "
                        "switch to 'Access Token' authentication instead of OAuth2. "
                        "OAuth2 requires completing a full authorization flow. "
                        "\n\nSteps: "
                        "\n1. Change Authentication to 'Access Token'"
                        "\n2. Create shopifyAccessTokenApi credential with your shpat_ token"
                        "\n3. Link the new credential to this node"
                    )
                else:
                    suggestion = (
                        "\n\nOAuth2 requires completing the authorization flow to get an access token. "
                        "Alternatively, use 'Access Token' authentication for simpler setup."
                    )
                
                raise ValueError(
                    f"OAuth2 access token not found in credentials. "
                    f"Available fields: {available_fields}. "
                    f"OAuth2 flow needs to be completed first.{suggestion}"
                )
        # For apiKey, basic auth will be handled in _make_request

        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to Shopify API"""
        auth_method = self.get_node_parameter("authentication", 0, "shopifyApi")
        print(f'auth_method : {auth_method}')
        api_url = self._get_api_url()
        print(f'api_url : {api_url}')
        headers = self._get_headers()
        print(f'headers : {headers}')   
        credential_name = self._get_credential_name()
        credentials = self.get_credentials(credential_name)
        
        url = f"{api_url}{endpoint}"

        print(f'Making {method} request to {url} with data: {data} and params: {params}')
        
        # Prepare auth for basic authentication if needed (shopifyApi method)
        auth = None
        if auth_method == "shopifyApi":
            api_key = credentials.get("apiKey")
            password = credentials.get("password")
            if api_key and password:
                auth = (api_key, password)
            else:
                raise ValueError("API key and password are required for apiKey authentication")

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            params=params,
            auth=auth,
            timeout=30,
        )

        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 204:
            return {"success": True}
        else:
            raise ValueError(
                f"HTTP error {response.status_code}: {response.text}"
            )

    # ORDER OPERATIONS

    def _create_order(self, item_index: int) -> Dict[str, Any]:
        """Create an order"""
        try:
            # Get line items
            line_items = self.get_node_parameter("lineItems", item_index, [])
            
            if not line_items:
                raise ValueError("At least one line item is required for creating order")

            body = {"line_items": line_items}

            # Get additional fields
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            # Map additional fields to API format
            if additional_fields:
                if "billingAddress" in additional_fields:
                    body["billing_address"] = additional_fields["billingAddress"]
                
                if "discountCodes" in additional_fields:
                    body["discount_codes"] = additional_fields["discountCodes"]
                
                if "email" in additional_fields:
                    body["email"] = additional_fields["email"]
                
                if "fulfillmentStatus" in additional_fields:
                    body["fulfillment_status"] = additional_fields["fulfillmentStatus"]
                
                if "inventoryBehaviour" in additional_fields:
                    body["inventory_behaviour"] = additional_fields["inventoryBehaviour"]
                
                if "locationId" in additional_fields:
                    body["location_id"] = additional_fields["locationId"]
                
                if "note" in additional_fields:
                    body["note"] = additional_fields["note"]
                
                if "sendFulfillmentReceipt" in additional_fields:
                    body["send_fulfillment_receipt"] = additional_fields["sendFulfillmentReceipt"]
                
                if "sendReceipt" in additional_fields:
                    body["send_receipt"] = additional_fields["sendReceipt"]
                
                if "shippingAddress" in additional_fields:
                    body["shipping_address"] = additional_fields["shippingAddress"]
                
                if "sourceName" in additional_fields:
                    body["source_name"] = additional_fields["sourceName"]
                
                if "tags" in additional_fields:
                    body["tags"] = additional_fields["tags"]
                
                if "test" in additional_fields:
                    body["test"] = additional_fields["test"]

            response_data = self._make_request("POST", "/orders.json", {"order": body})
            return response_data.get("order", response_data)

        except Exception as e:
            raise ValueError(f"Error creating order: {str(e)}")

    def _delete_order(self, item_index: int) -> Dict[str, Any]:
        """Delete an order"""
        try:
            order_id = self.get_node_parameter("orderId", item_index, "")

            if not order_id:
                raise ValueError("Order ID is required for deleting order")

            self._make_request("DELETE", f"/orders/{order_id}.json")
            return {"success": True, "order_id": order_id}

        except Exception as e:
            raise ValueError(f"Error deleting order: {str(e)}")

    def _get_order(self, item_index: int) -> Dict[str, Any]:
        """Get an order by ID"""
        try:
            order_id = self.get_node_parameter("orderId", item_index, "")

            if not order_id:
                raise ValueError("Order ID is required for getting order")

            params = {}
            
            # Get options
            options = self.get_node_parameter("options", item_index, {})
            if options and "fields" in options:
                params["fields"] = options["fields"]

            response_data = self._make_request("GET", f"/orders/{order_id}.json", params=params)
            return response_data.get("order", response_data)

        except Exception as e:
            raise ValueError(f"Error getting order: {str(e)}")

    def _get_all_orders(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all orders"""
        try:
            return_all = self.get_node_parameter("returnAll", item_index, False)
            params = {}

            if not return_all:
                limit = self.get_node_parameter("limit", item_index, 50)
                params["limit"] = limit

            # Get options
            options = self.get_node_parameter("options", item_index, {})
            
            if options:
                if "attributionAppId" in options and options["attributionAppId"]:
                    params["attribution_app_id"] = options["attributionAppId"]
                
                if "createdAtMin" in options and options["createdAtMin"]:
                    params["created_at_min"] = options["createdAtMin"]
                
                if "createdAtMax" in options and options["createdAtMax"]:
                    params["created_at_max"] = options["createdAtMax"]
                
                if "financialStatus" in options and options["financialStatus"] != "any":
                    params["financial_status"] = options["financialStatus"]
                
                if "fulfillmentStatus" in options and options["fulfillmentStatus"] != "any":
                    params["fulfillment_status"] = options["fulfillmentStatus"]
                
                if "fields" in options and options["fields"]:
                    params["fields"] = options["fields"]
                
                if "ids" in options and options["ids"]:
                    params["ids"] = options["ids"]
                
                if "processedAtMax" in options and options["processedAtMax"]:
                    params["processed_at_max"] = options["processedAtMax"]
                
                if "processedAtMin" in options and options["processedAtMin"]:
                    params["processed_at_min"] = options["processedAtMin"]
                
                if "status" in options and options["status"] != "any":
                    params["status"] = options["status"]
                
                if "sinceId" in options and options["sinceId"]:
                    params["since_id"] = options["sinceId"]
                
                if "updatedAtMax" in options and options["updatedAtMax"]:
                    params["updated_at_max"] = options["updatedAtMax"]
                
                if "updatedAtMin" in options and options["updatedAtMin"]:
                    params["updated_at_min"] = options["updatedAtMin"]

            response_data = self._make_request("GET", "/orders.json", params=params)
            orders = response_data.get("orders", [])
            
            # Return as list of individual orders
            return orders

        except Exception as e:
            raise ValueError(f"Error getting all orders: {str(e)}")

    def _update_order(self, item_index: int) -> Dict[str, Any]:
        """Update an order"""
        try:
            order_id = self.get_node_parameter("orderId", item_index, "")

            if not order_id:
                raise ValueError("Order ID is required for updating order")

            # Get update fields
            update_fields = self.get_node_parameter("updateFields", item_index, {})
            
            if not update_fields:
                raise ValueError("At least one field must be provided for updating order")

            body = {}

            # Map update fields to API format
            if "email" in update_fields:
                body["email"] = update_fields["email"]
            
            if "locationId" in update_fields:
                body["location_id"] = update_fields["locationId"]
            
            if "note" in update_fields:
                body["note"] = update_fields["note"]
            
            if "shippingAddress" in update_fields:
                body["shipping_address"] = update_fields["shippingAddress"]
            
            if "sourceName" in update_fields:
                body["source_name"] = update_fields["sourceName"]
            
            if "tags" in update_fields:
                body["tags"] = update_fields["tags"]

            response_data = self._make_request(
                "PUT", f"/orders/{order_id}.json", {"order": body}
            )
            return response_data.get("order", response_data)

        except Exception as e:
            raise ValueError(f"Error updating order: {str(e)}")

    # PRODUCT OPERATIONS

    def _create_product(self, item_index: int) -> Dict[str, Any]:
        """Create a product"""
        try:
            title = self.get_node_parameter("title", item_index, "")

            if not title:
                raise ValueError("Title is required for creating product")

            body = {"title": title}

            # Get additional fields
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            if additional_fields:
                if "body_html" in additional_fields:
                    body["body_html"] = additional_fields["body_html"]
                
                if "handle" in additional_fields:
                    body["handle"] = additional_fields["handle"]
                
                if "images" in additional_fields:
                    body["images"] = additional_fields["images"]
                
                if "productOptions" in additional_fields:
                    body["options"] = additional_fields["productOptions"]
                
                if "product_type" in additional_fields:
                    body["product_type"] = additional_fields["product_type"]
                
                if "published_at" in additional_fields:
                    body["published_at"] = additional_fields["published_at"]
                
                if "published_scope" in additional_fields:
                    body["published_scope"] = additional_fields["published_scope"]
                
                if "tags" in additional_fields:
                    body["tags"] = additional_fields["tags"]
                
                if "template_suffix" in additional_fields:
                    body["template_suffix"] = additional_fields["template_suffix"]
                
                if "vendor" in additional_fields:
                    body["vendor"] = additional_fields["vendor"]

            response_data = self._make_request("POST", "/products.json", {"product": body})
            return response_data.get("product", response_data)

        except Exception as e:
            raise ValueError(f"Error creating product: {str(e)}")

    def _delete_product(self, item_index: int) -> Dict[str, Any]:
        """Delete a product"""
        try:
            product_id = self.get_node_parameter("productId", item_index, "")

            if not product_id:
                raise ValueError("Product ID is required for deleting product")

            self._make_request("DELETE", f"/products/{product_id}.json")
            return {"success": True, "product_id": product_id}

        except Exception as e:
            raise ValueError(f"Error deleting product: {str(e)}")

    def _get_product(self, item_index: int) -> Dict[str, Any]:
        """Get a product by ID"""
        try:
            product_id = self.get_node_parameter("productId", item_index, "")

            if not product_id:
                raise ValueError("Product ID is required for getting product")

            params = {}
            
            # Get additional fields
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            if additional_fields and "fields" in additional_fields:
                params["fields"] = additional_fields["fields"]

            response_data = self._make_request(
                "GET", f"/products/{product_id}.json", params=params
            )
            return response_data.get("product", response_data)

        except Exception as e:
            raise ValueError(f"Error getting product: {str(e)}")

    def _get_all_products(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all products"""
        try:
            return_all = self.get_node_parameter("returnAll", item_index, False)
            params = {}

            if not return_all:
                limit = self.get_node_parameter("limit", item_index, 50)
                params["limit"] = limit

            # # Get additional fields
            # additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            # if additional_fields:
            #     if "collection_id" in additional_fields and additional_fields["collection_id"]:
            #         params["collection_id"] = additional_fields["collection_id"]
                
            #     if "created_at_max" in additional_fields and additional_fields["created_at_max"]:
            #         params["created_at_max"] = additional_fields["created_at_max"]
                
            #     if "created_at_min" in additional_fields and additional_fields["created_at_min"]:
            #         params["created_at_min"] = additional_fields["created_at_min"]
                
            #     if "fields" in additional_fields and additional_fields["fields"]:
            #         params["fields"] = additional_fields["fields"]
                
            #     if "handle" in additional_fields and additional_fields["handle"]:
            #         params["handle"] = additional_fields["handle"]
                
            #     if "ids" in additional_fields and additional_fields["ids"]:
            #         params["ids"] = additional_fields["ids"]
                
            #     if "presentment_currencies" in additional_fields and additional_fields["presentment_currencies"]:
            #         params["presentment_currencies"] = additional_fields["presentment_currencies"]
                
            #     if "product_type" in additional_fields and additional_fields["product_type"]:
            #         params["product_type"] = additional_fields["product_type"]
                
            #     if "published_at_max" in additional_fields and additional_fields["published_at_max"]:
            #         params["published_at_max"] = additional_fields["published_at_max"]
                
            #     if "published_at_min" in additional_fields and additional_fields["published_at_min"]:
            #         params["published_at_min"] = additional_fields["published_at_min"]
                
            #     if "published_status" in additional_fields and additional_fields["published_status"] != "any":
            #         params["published_status"] = additional_fields["published_status"]
                
            #     if "title" in additional_fields and additional_fields["title"]:
            #         params["title"] = additional_fields["title"]
                
            #     if "updated_at_max" in additional_fields and additional_fields["updated_at_max"]:
            #         params["updated_at_max"] = additional_fields["updated_at_max"]
                
            #     if "updated_at_min" in additional_fields and additional_fields["updated_at_min"]:
            #         params["updated_at_min"] = additional_fields["updated_at_min"]
                
            #     if "vendor" in additional_fields and additional_fields["vendor"]:
            #         params["vendor"] = additional_fields["vendor"]

            response_data = self._make_request("GET", "/products.json", params=params)
            products = response_data.get("products", [])
            
            # Return as list of individual products
            return products

        except Exception as e:
            logger.error(f"Failed to get all products: {str(e)}", exc_info=True)
            raise ValueError(f"Error getting all products: {str(e)}")

    def _update_product(self, item_index: int) -> Dict[str, Any]:
        """Update a product"""
        try:
            product_id = self.get_node_parameter("productId", item_index, "")

            if not product_id:
                raise ValueError("Product ID is required for updating product")

            # Get update fields
            update_fields = self.get_node_parameter("updateFields", item_index, {})
            
            if not update_fields:
                raise ValueError("At least one field must be provided for updating product")

            body = {}

            # Map update fields to API format
            if "body_html" in update_fields:
                body["body_html"] = update_fields["body_html"]
            
            if "handle" in update_fields:
                body["handle"] = update_fields["handle"]
            
            if "images" in update_fields:
                body["images"] = update_fields["images"]
            
            if "productOptions" in update_fields:
                body["options"] = update_fields["productOptions"]
            
            if "product_type" in update_fields:
                body["product_type"] = update_fields["product_type"]
            
            if "published_at" in update_fields:
                body["published_at"] = update_fields["published_at"]
            
            if "published_scope" in update_fields:
                body["published_scope"] = update_fields["published_scope"]
            
            if "tags" in update_fields:
                body["tags"] = update_fields["tags"]
            
            if "template_suffix" in update_fields:
                body["template_suffix"] = update_fields["template_suffix"]
            
            if "title" in update_fields:
                body["title"] = update_fields["title"]
            
            if "vendor" in update_fields:
                body["vendor"] = update_fields["vendor"]

            response_data = self._make_request(
                "PUT", f"/products/{product_id}.json", {"product": body}
            )
            return response_data.get("product", response_data)

        except Exception as e:
            raise ValueError(f"Error updating product: {str(e)}")
