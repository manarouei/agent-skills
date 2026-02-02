import requests
import json
import logging
from typing import Dict, List, Optional, Any
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class WallexNode(BaseNode):
    """
    Wallex node for cryptocurrency exchange operations
    """

    type = "wallex"
    version = 1.0

    description = {
        "displayName": "Wallex",
        "name": "wallex",
        "icon": "file:wallex.svg",
        "group": ["transform"],
        "description": "Interact with Wallex cryptocurrency exchange API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "credentials": [
            {
                "name": "wallexApi",
                "display_name": "Wallex API",
                "required": True,
            }
        ],
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Markets", "value": "markets"},
                    {"name": "Account", "value": "account"},
                    {"name": "Orders", "value": "orders"},
                    {"name": "Trades", "value": "trades"},
                    {"name": "OTC", "value": "otc"},
                    {"name": "Wallgate", "value": "wallgate"},
                ],
                "default": "markets",
                "description": "The resource to operate on",
            },
            
            # Markets Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get Markets", "value": "getMarkets"},
                    {"name": "Get Currencies Stats", "value": "getCurrenciesStats"},
                    {"name": "Get Order Book", "value": "getDepth"},
                    {"name": "Get All Order Books", "value": "getAllDepth"},
                    {"name": "Get Latest Trades", "value": "getTrades"},
                    {"name": "Get Candles (OHLC)", "value": "getCandles"},
                ],
                "default": "getMarkets",
                "display_options": {"show": {"resource": ["markets"]}},
            },
            
            # Account Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get Profile", "value": "getProfile"},
                    {"name": "Get Fee", "value": "getFee"},
                    {"name": "Get Card Numbers", "value": "getCardNumbers"},
                    {"name": "Get IBANs", "value": "getIbans"},
                    {"name": "Get Balances", "value": "getBalances"},
                    {"name": "Withdraw Money", "value": "withdrawMoney"},
                    {"name": "Get Crypto Deposits", "value": "getCryptoDeposits"},
                    {"name": "Get Crypto Withdrawals", "value": "getCryptoWithdrawals"},
                    {"name": "Withdraw Crypto", "value": "withdrawCrypto"},
                ],
                "default": "getProfile",
                "display_options": {"show": {"resource": ["account"]}},
            },
            
            # Orders Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create Order", "value": "createOrder"},
                    {"name": "Get Order", "value": "getOrder"},
                    {"name": "Cancel Order", "value": "cancelOrder"},
                    {"name": "Get Open Orders", "value": "getOpenOrders"},
                ],
                "default": "createOrder",
                "display_options": {"show": {"resource": ["orders"]}},
            },
            
            # Trades Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get User Trades", "value": "getUserTrades"},
                ],
                "default": "getUserTrades",
                "display_options": {"show": {"resource": ["trades"]}},
            },
            
            # OTC Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get OTC Markets", "value": "getOtcMarkets"},
                    {"name": "Get Price", "value": "getOtcPrice"},
                    {"name": "Create OTC Order", "value": "createOtcOrder"},
                ],
                "default": "getOtcMarkets",
                "display_options": {"show": {"resource": ["otc"]}},
            },
            
            # Wallgate Operations
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Authentication", "value": "wallgateAuth"},
                    {"name": "Get Categories", "value": "wallgateCategories"},
                    {"name": "Get Products", "value": "wallgateProducts"},
                    {"name": "Create Order", "value": "wallgateCreateOrder"},
                    {"name": "Get Order", "value": "wallgateGetOrder"},
                ],
                "default": "wallgateCategories",
                "display_options": {"show": {"resource": ["wallgate"]}},
            },
            
            # Markets Parameters
            {
                "name": "symbol",
                "type": NodeParameterType.STRING,
                "display_name": "Market Symbol",
                "default": "",
                "placeholder": "BTCUSDT",
                "description": "Market symbol (e.g., BTCUSDT)",
                "display_options": {
                    "show": {
                        "resource": ["markets"],
                        "operation": ["getDepth", "getTrades", "getCandles"]
                    }
                },
            },
            {
                "name": "resolution",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Time Resolution",
                "options": [
                    {"name": "1 Minute", "value": "1"},
                    {"name": "5 Minutes", "value": "5"},
                    {"name": "15 Minutes", "value": "15"},
                    {"name": "30 Minutes", "value": "30"},
                    {"name": "1 Hour", "value": "60"},
                    {"name": "4 Hours", "value": "240"},
                    {"name": "1 Day", "value": "1D"},
                    {"name": "1 Week", "value": "1W"},
                ],
                "default": "60",
                "description": "Time resolution for candles",
                "display_options": {
                    "show": {
                        "resource": ["markets"],
                        "operation": ["getCandles"]
                    }
                },
            },
            {
                "name": "from",
                "type": NodeParameterType.NUMBER,
                "display_name": "From (Timestamp)",
                "default": 0,
                "description": "Start time (Unix timestamp)",
                "display_options": {
                    "show": {
                        "resource": ["markets"],
                        "operation": ["getCandles"]
                    }
                },
            },
            {
                "name": "to",
                "type": NodeParameterType.NUMBER,
                "display_name": "To (Timestamp)",
                "default": 0,
                "description": "End time (Unix timestamp)",
                "display_options": {
                    "show": {
                        "resource": ["markets"],
                        "operation": ["getCandles"]
                    }
                },
            },
            
            # Account Parameters - Money Withdrawal
            {
                "name": "iban",
                "type": NodeParameterType.NUMBER,
                "display_name": "IBAN ID",
                "default": 0,
                "required": True,
                "description": "Bank IBAN ID",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawMoney"]
                    }
                },
            },
            {
                "name": "moneyValue",
                "type": NodeParameterType.NUMBER,
                "display_name": "Withdrawal Amount",
                "default": 0,
                "required": True,
                "description": "Withdrawal amount in Toman",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawMoney"]
                    }
                },
            },
            
            # Account Parameters - Crypto Withdrawal
            {
                "name": "coin",
                "type": NodeParameterType.STRING,
                "display_name": "Coin Symbol",
                "default": "",
                "placeholder": "USDT",
                "required": True,
                "description": "Cryptocurrency symbol",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawCrypto"]
                    }
                },
            },
            {
                "name": "network",
                "type": NodeParameterType.STRING,
                "display_name": "Network",
                "default": "",
                "placeholder": "TRC20",
                "required": True,
                "description": "Network type for crypto transfer",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawCrypto"]
                    }
                },
            },
            {
                "name": "cryptoValue",
                "type": NodeParameterType.NUMBER,
                "display_name": "Withdrawal Amount",
                "default": 0,
                "required": True,
                "description": "Cryptocurrency withdrawal amount",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawCrypto"]
                    }
                },
            },
            {
                "name": "walletAddress",
                "type": NodeParameterType.STRING,
                "display_name": "Wallet Address",
                "default": "",
                "required": True,
                "description": "Destination wallet address",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawCrypto"]
                    }
                },
            },
            {
                "name": "memo",
                "type": NodeParameterType.STRING,
                "display_name": "Memo",
                "default": "",
                "description": "Address memo (if required by network)",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["withdrawCrypto"]
                    }
                },
            },
            
            # Account Parameters - Pagination
            {
                "name": "page",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page",
                "default": 1,
                "description": "Page number",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["getCryptoDeposits", "getCryptoWithdrawals"]
                    }
                },
            },
            {
                "name": "perPage",
                "type": NodeParameterType.NUMBER,
                "display_name": "Per Page",
                "default": 10,
                "description": "Number of items per page",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["getCryptoDeposits", "getCryptoWithdrawals"]
                    }
                },
            },
            
            # Orders Parameters
            {
                "name": "orderSymbol",
                "type": NodeParameterType.STRING,
                "display_name": "Market Symbol",
                "default": "",
                "placeholder": "BTCUSDT",
                "required": True,
                "description": "Market symbol",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder"]
                    }
                },
            },
            {
                "name": "orderType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Order Type",
                "options": [
                    {"name": "Limit", "value": "LIMIT"},
                    {"name": "Market", "value": "MARKET"},
                    {"name": "Stop Limit", "value": "STOP_LIMIT"},
                ],
                "default": "LIMIT",
                "required": True,
                "description": "Order type",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder"]
                    }
                },
            },
            {
                "name": "side",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Side",
                "options": [
                    {"name": "Buy", "value": "BUY"},
                    {"name": "Sell", "value": "SELL"},
                ],
                "default": "BUY",
                "required": True,
                "description": "Buy or sell side",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder"]
                    }
                },
            },
            {
                "name": "price",
                "type": NodeParameterType.STRING,
                "display_name": "Price",
                "default": "",
                "required": True,
                "description": "Unit price",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder"],
                        "orderType": ["LIMIT", "STOP_LIMIT"]
                    }
                },
            },
            {
                "name": "quantity",
                "type": NodeParameterType.STRING,
                "display_name": "Quantity",
                "default": "",
                "required": True,
                "description": "Order quantity",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder"]
                    }
                },
            },
            {
                "name": "clientOrderId",
                "type": NodeParameterType.STRING,
                "display_name": "Order ID",
                "default": "",
                "description": "Unique order ID (optional)",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["createOrder", "getOrder", "cancelOrder"]
                    }
                },
            },
            {
                "name": "filterSymbol",
                "type": NodeParameterType.STRING,
                "display_name": "Filter Symbol",
                "default": "",
                "placeholder": "BTCUSDT",
                "description": "Filter by market symbol",
                "display_options": {
                    "show": {
                        "resource": ["orders"],
                        "operation": ["getOpenOrders"]
                    }
                },
            },
            
            # Trades Parameters
            {
                "name": "tradeSymbol",
                "type": NodeParameterType.STRING,
                "display_name": "Market Symbol",
                "default": "",
                "placeholder": "BTCUSDT",
                "description": "Filter by market symbol",
                "display_options": {
                    "show": {
                        "resource": ["trades"],
                        "operation": ["getUserTrades"]
                    }
                },
            },
            {
                "name": "tradeSide",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Trade Side",
                "options": [
                    {"name": "All", "value": ""},
                    {"name": "Buy", "value": "BUY"},
                    {"name": "Sell", "value": "SELL"},
                ],
                "default": "",
                "description": "Filter by trade side",
                "display_options": {
                    "show": {
                        "resource": ["trades"],
                        "operation": ["getUserTrades"]
                    }
                },
            },
            
            # OTC Parameters
            {
                "name": "otcSymbol",
                "type": NodeParameterType.STRING,
                "display_name": "Market Symbol",
                "default": "",
                "placeholder": "BTCUSDT",
                "required": True,
                "description": "Market symbol",
                "display_options": {
                    "show": {
                        "resource": ["otc"],
                        "operation": ["getOtcPrice", "createOtcOrder"]
                    }
                },
            },
            {
                "name": "otcSide",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Side",
                "options": [
                    {"name": "Buy", "value": "BUY"},
                    {"name": "Sell", "value": "SELL"},
                ],
                "default": "BUY",
                "required": True,
                "description": "Buy or sell side",
                "display_options": {
                    "show": {
                        "resource": ["otc"],
                        "operation": ["getOtcPrice", "createOtcOrder"]
                    }
                },
            },
            {
                "name": "otcAmount",
                "type": NodeParameterType.NUMBER,
                "display_name": "Amount",
                "default": 0,
                "required": True,
                "description": "Buy or sell amount",
                "display_options": {
                    "show": {
                        "resource": ["otc"],
                        "operation": ["createOtcOrder"]
                    }
                },
            },
            
            # Wallgate Parameters
            {
                "name": "wallgateUsername",
                "type": NodeParameterType.STRING,
                "display_name": "Username",
                "default": "",
                "required": True,
                "description": "Wallgate mobile number",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateAuth"]
                    }
                },
            },
            {
                "name": "wallgatePassword",
                "type": NodeParameterType.STRING,
                "display_name": "Password",
                "default": "",
                "required": True,
                "description": "Wallgate password",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateAuth"]
                    }
                },
            },
            {
                "name": "wallgatePageSize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Size",
                "default": 20,
                "description": "Number of products per page",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateProducts"]
                    }
                },
            },
            {
                "name": "wallgatePage",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Number",
                "default": 1,
                "description": "Page number",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateProducts"]
                    }
                },
            },
            {
                "name": "wallgateCategory",
                "type": NodeParameterType.NUMBER,
                "display_name": "Category",
                "default": 0,
                "description": "Category ID to filter products",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateProducts"]
                    }
                },
            },
            {
                "name": "wallgateVariantId",
                "type": NodeParameterType.NUMBER,
                "display_name": "Variant ID",
                "default": 0,
                "required": True,
                "description": "Product variant ID",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateCreateOrder"]
                    }
                },
            },
            {
                "name": "wallgateQty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Quantity",
                "default": 1,
                "required": True,
                "description": "Product quantity",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateCreateOrder"]
                    }
                },
            },
            {
                "name": "wallgateAccount",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Account Type",
                "options": [
                    {"name": "USDT", "value": "USDT"},
                    {"name": "TMN", "value": "TMN"},
                ],
                "default": "USDT",
                "required": True,
                "description": "Account type for payment",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateCreateOrder"]
                    }
                },
            },
            {
                "name": "wallgateUniqueId",
                "type": NodeParameterType.STRING,
                "display_name": "Unique ID",
                "default": "",
                "required": True,
                "description": "Unique tracking ID (UUID)",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateCreateOrder", "wallgateGetOrder"]
                    }
                },
            },
            {
                "name": "wallgateWebhookUrl",
                "type": NodeParameterType.STRING,
                "display_name": "Webhook URL",
                "default": "",
                "description": "Webhook URL to receive order result",
                "display_options": {
                    "show": {
                        "resource": ["wallgate"],
                        "operation": ["wallgateCreateOrder"]
                    }
                },
            },
        ],
    }

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Wallex node operations"""
        
        # Get input data
        input_data = self.get_input_data()
        
        if not input_data:
            input_data = [[]]
        
        outputs: List[NodeExecutionData] = []
        
        # Get credentials
        credentials = self.get_credentials("wallexApi")
        api_url = credentials.get("apiUrl", "https://api.wallex.ir").rstrip('/')
        api_key = credentials.get("apiKey", "")
        
        # Get parameters
        resource = self.get_node_parameter("resource", 0)
        operation = self.get_node_parameter("operation", 0)
        
        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json"
        }
        
        try:
            for item_index, item in enumerate(input_data):
                result = None
                
                # Markets Resource
                if resource == "markets":
                    result = self._handle_markets_operations(
                        operation, api_url, headers, item_index
                    )
                
                # Account Resource
                elif resource == "account":
                    result = self._handle_account_operations(
                        operation, api_url, headers, item_index
                    )
                
                # Orders Resource
                elif resource == "orders":
                    result = self._handle_orders_operations(
                        operation, api_url, headers, item_index
                    )
                
                # Trades Resource
                elif resource == "trades":
                    result = self._handle_trades_operations(
                        operation, api_url, headers, item_index
                    )
                
                # OTC Resource
                elif resource == "otc":
                    result = self._handle_otc_operations(
                        operation, api_url, headers, item_index
                    )
                
                # Wallgate Resource
                elif resource == "wallgate":
                    result = self._handle_wallgate_operations(
                        operation, api_url, item_index
                    )
                
                if result:
                    outputs.append(
                        NodeExecutionData(
                            json_data=result,
                            binary_data=None
                        )
                    )
        
        except Exception as e:
            logger.error(f"Error executing Wallex node: {str(e)}")
            raise
        
        return [outputs] if outputs else [input_data]

    def _handle_markets_operations(
        self, operation: str, api_url: str, headers: Dict, item_index: int
    ) -> Dict:
        """Handle markets resource operations"""
        
        if operation == "getMarkets":
            response = requests.get(f"{api_url}/v1/markets")
            return response.json()
        
        elif operation == "getCurrenciesStats":
            response = requests.get(f"{api_url}/v1/currencies/stats")
            return response.json()
        
        elif operation == "getDepth":
            symbol = self.get_node_parameter("symbol", item_index)
            response = requests.get(f"{api_url}/v1/depth", params={"symbol": symbol})
            return response.json()
        
        elif operation == "getAllDepth":
            response = requests.get(f"{api_url}/v2/depth/all")
            return response.json()
        
        elif operation == "getTrades":
            symbol = self.get_node_parameter("symbol", item_index)
            response = requests.get(f"{api_url}/v1/trades", params={"symbol": symbol})
            return response.json()
        
        elif operation == "getCandles":
            symbol = self.get_node_parameter("symbol", item_index)
            resolution = self.get_node_parameter("resolution", item_index)
            from_ts = self.get_node_parameter("from", item_index)
            to_ts = self.get_node_parameter("to", item_index)
            
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "from": from_ts,
                "to": to_ts
            }
            response = requests.get(f"{api_url}/v1/udf/history", params=params)
            return response.json()

    def _handle_account_operations(
        self, operation: str, api_url: str, headers: Dict, item_index: int
    ) -> Dict:
        """Handle account resource operations"""
        
        if operation == "getProfile":
            response = requests.get(f"{api_url}/v1/account/profile", headers=headers)
            return response.json()
        
        elif operation == "getFee":
            response = requests.get(f"{api_url}/v1/account/fee", headers=headers)
            return response.json()
        
        elif operation == "getCardNumbers":
            response = requests.get(f"{api_url}/v1/account/card-numbers", headers=headers)
            return response.json()
        
        elif operation == "getIbans":
            response = requests.get(f"{api_url}/v1/account/ibans", headers=headers)
            return response.json()
        
        elif operation == "getBalances":
            response = requests.get(f"{api_url}/v1/account/balances", headers=headers)
            return response.json()
        
        elif operation == "withdrawMoney":
            iban = self.get_node_parameter("iban", item_index)
            value = self.get_node_parameter("moneyValue", item_index)
            
            payload = {
                "iban": iban,
                "value": value
            }
            response = requests.post(
                f"{api_url}/v1/account/money-withdrawal",
                headers=headers,
                json=payload
            )
            return response.json()
        
        elif operation == "getCryptoDeposits":
            page = self.get_node_parameter("page", item_index, 1)
            per_page = self.get_node_parameter("perPage", item_index, 10)
            
            params = {
                "page": page,
                "per_page": per_page
            }
            response = requests.get(
                f"{api_url}/v1/account/crypto-deposit",
                headers=headers,
                params=params
            )
            return response.json()
        
        elif operation == "getCryptoWithdrawals":
            page = self.get_node_parameter("page", item_index, 1)
            per_page = self.get_node_parameter("perPage", item_index, 10)
            
            params = {
                "page": page,
                "per_page": per_page
            }
            response = requests.get(
                f"{api_url}/v1/account/crypto-withdrawal",
                headers=headers,
                params=params
            )
            return response.json()
        
        elif operation == "withdrawCrypto":
            coin = self.get_node_parameter("coin", item_index)
            network = self.get_node_parameter("network", item_index)
            value = self.get_node_parameter("cryptoValue", item_index)
            wallet_address = self.get_node_parameter("walletAddress", item_index)
            memo = self.get_node_parameter("memo", item_index, "")
            
            payload = {
                "coin": coin,
                "network": network,
                "value": value,
                "wallet_address": wallet_address
            }
            if memo:
                payload["memo"] = memo
            
            response = requests.post(
                f"{api_url}/v1/account/crypto-withdrawal",
                headers=headers,
                json=payload
            )
            return response.json()

    def _handle_orders_operations(
        self, operation: str, api_url: str, headers: Dict, item_index: int
    ) -> Dict:
        """Handle orders resource operations"""
        
        if operation == "createOrder":
            symbol = self.get_node_parameter("orderSymbol", item_index)
            order_type = self.get_node_parameter("orderType", item_index)
            side = self.get_node_parameter("side", item_index)
            quantity = self.get_node_parameter("quantity", item_index)
            client_order_id = self.get_node_parameter("clientOrderId", item_index, "")
            
            payload = {
                "symbol": symbol,
                "type": order_type,
                "side": side,
                "quantity": quantity
            }
            
            if order_type in ["LIMIT", "STOP_LIMIT"]:
                price = self.get_node_parameter("price", item_index)
                payload["price"] = price
            
            if client_order_id:
                payload["client_id"] = client_order_id
            
            response = requests.post(
                f"{api_url}/v1/account/orders",
                headers=headers,
                json=payload
            )
            return response.json()
        
        elif operation == "getOrder":
            client_order_id = self.get_node_parameter("clientOrderId", item_index)
            response = requests.get(
                f"{api_url}/v1/account/orders/{client_order_id}",
                headers=headers
            )
            return response.json()
        
        elif operation == "cancelOrder":
            client_order_id = self.get_node_parameter("clientOrderId", item_index)
            response = requests.delete(
                f"{api_url}/v1/account/orders",
                headers=headers,
                params={"clientOrderId": client_order_id}
            )
            return response.json()
        
        elif operation == "getOpenOrders":
            filter_symbol = self.get_node_parameter("filterSymbol", item_index, "")
            params = {}
            if filter_symbol:
                params["symbol"] = filter_symbol
            
            response = requests.get(
                f"{api_url}/v1/account/openOrders",
                headers=headers,
                params=params
            )
            return response.json()

    def _handle_trades_operations(
        self, operation: str, api_url: str, headers: Dict, item_index: int
    ) -> Dict:
        """Handle trades resource operations"""
        
        if operation == "getUserTrades":
            trade_symbol = self.get_node_parameter("tradeSymbol", item_index, "")
            trade_side = self.get_node_parameter("tradeSide", item_index, "")
            
            params = {}
            if trade_symbol:
                params["symbol"] = trade_symbol
            if trade_side:
                params["side"] = trade_side
            
            response = requests.get(
                f"{api_url}/v1/account/trades",
                headers=headers,
                params=params
            )
            return response.json()

    def _handle_otc_operations(
        self, operation: str, api_url: str, headers: Dict, item_index: int
    ) -> Dict:
        """Handle OTC resource operations"""
        
        if operation == "getOtcMarkets":
            response = requests.get(f"{api_url}/v1/otc/markets")
            return response.json()
        
        elif operation == "getOtcPrice":
            symbol = self.get_node_parameter("otcSymbol", item_index)
            side = self.get_node_parameter("otcSide", item_index)
            
            payload = {
                "symbol": symbol,
                "side": side
            }
            response = requests.get(
                f"{api_url}/v1/account/otc/price",
                headers=headers,
                json=payload
            )
            return response.json()
        
        elif operation == "createOtcOrder":
            symbol = self.get_node_parameter("otcSymbol", item_index)
            side = self.get_node_parameter("otcSide", item_index)
            amount = self.get_node_parameter("otcAmount", item_index)
            
            payload = {
                "symbol": symbol,
                "side": side,
                "amount": amount
            }
            response = requests.post(
                f"{api_url}/v1/account/otc/orders",
                headers=headers,
                json=payload
            )
            return response.json()

    def _handle_wallgate_operations(
        self, operation: str, api_url: str, item_index: int
    ) -> Dict:
        """Handle Wallgate resource operations"""
        
        wallgate_base = "https://api.wallgate.io/v1/store"
        
        if operation == "wallgateAuth":
            username = self.get_node_parameter("wallgateUsername", item_index)
            password = self.get_node_parameter("wallgatePassword", item_index)
            
            payload = {
                "username": username,
                "password": password
            }
            response = requests.post(
                f"{wallgate_base}/oauth/token",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        
        elif operation == "wallgateCategories":
            response = requests.get(
                f"{wallgate_base}/api/categories",
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        
        elif operation == "wallgateProducts":
            page_size = self.get_node_parameter("wallgatePageSize", item_index, 20)
            page = self.get_node_parameter("wallgatePage", item_index, 1)
            category = self.get_node_parameter("wallgateCategory", item_index, 0)
            
            params = {
                "page_size": page_size,
                "page": page
            }
            if category:
                params["category"] = category
            
            response = requests.get(
                f"{wallgate_base}/api/products",
                params=params,
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        
        elif operation == "wallgateCreateOrder":
            # Note: This requires authentication token from wallgateAuth
            variant_id = self.get_node_parameter("wallgateVariantId", item_index)
            qty = self.get_node_parameter("wallgateQty", item_index)
            account = self.get_node_parameter("wallgateAccount", item_index)
            unique_id = self.get_node_parameter("wallgateUniqueId", item_index)
            webhook_url = self.get_node_parameter("wallgateWebhookUrl", item_index, "")
            
            payload = {
                "variant_id": variant_id,
                "qty": qty,
                "account": account,
                "unique_id": unique_id
            }
            if webhook_url:
                payload["webhook_url"] = webhook_url
            
            # Note: Bearer token should be obtained from wallgateAuth operation
            response = requests.post(
                f"{wallgate_base}/api/order",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    # "Authorization": f"Bearer {token}"  # Token from previous auth
                }
            )
            return response.json()
        
        elif operation == "wallgateGetOrder":
            unique_id = self.get_node_parameter("wallgateUniqueId", item_index)
            
            # Note: Bearer token should be obtained from wallgateAuth operation
            response = requests.get(
                f"{wallgate_base}/api/order/{unique_id}",
                headers={
                    "Content-Type": "application/json",
                    # "Authorization": f"Bearer {token}"  # Token from previous auth
                }
            )
            return response.json()
