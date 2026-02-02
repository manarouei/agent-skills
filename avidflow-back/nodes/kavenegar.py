import requests
import json
import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class KavenegarNode(BaseNode):
    """
    Kavenegar node for SMS operations
    """

    type = "kavenegar"
    version = 1.0

    description = {
        "displayName": "Kavenegar",
        "name": "kavenegar",
        "icon": "file:kavenegar.svg",
        "group": ["communication"],
        "description": "Send SMS and interact with Kavenegar API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "SMS", "value": "sms"},
                    {"name": "Verify", "value": "verify"},
                    {"name": "Call", "value": "call"},
                    {"name": "Account", "value": "account"},
                ],
                "default": "sms",
                "description": "The resource to operate on",
            },
            # =============== SMS Operations ===============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Send", "value": "send", "description": "Simple SMS send"},
                    {"name": "Send Array", "value": "sendarray", "description": "Bulk SMS send"},
                    {"name": "Status", "value": "status", "description": "Check SMS status"},
                    {"name": "Status By Local ID", "value": "statuslocalmessageid", "description": "Get status by local ID"},
                    {"name": "Status By Receptor", "value": "statusbyreceptor", "description": "List status by phone number"},
                    {"name": "Select", "value": "select", "description": "Select SMS"},
                    {"name": "Select Outbox", "value": "selectoutbox", "description": "List sent messages"},
                    {"name": "Latest Outbox", "value": "latestoutbox", "description": "Latest sent messages"},
                    {"name": "Count Outbox", "value": "countoutbox", "description": "Count sent messages"},
                    {"name": "Cancel", "value": "cancel", "description": "Cancel sending"},
                    {"name": "Receive", "value": "receive", "description": "Receive SMS"},
                    {"name": "Inbox Paged", "value": "inboxpaged", "description": "Paged inbox"},
                    {"name": "Count Inbox", "value": "countinbox", "description": "Count received messages"},
                ],
                "default": "send",
                "display_options": {"show": {"resource": ["sms"]}},
            },
            # =============== Verify Operations ===============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Lookup", "value": "lookup", "description": "Verification - Send code"},
                ],
                "default": "lookup",
                "display_options": {"show": {"resource": ["verify"]}},
            },
            # =============== Call Operations ===============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Make TTS", "value": "maketts", "description": "Voice call"},
                ],
                "default": "maketts",
                "display_options": {"show": {"resource": ["call"]}},
            },
            # =============== Account Operations ===============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Info", "value": "info", "description": "Get account info"},
                    {"name": "Config", "value": "config", "description": "Essential settings"},
                ],
                "default": "info",
                "display_options": {"show": {"resource": ["account"]}},
            },
            
            # =============== SMS Send Parameters ===============
            {
                "name": "receptor",
                "type": NodeParameterType.STRING,
                "display_name": "Receptor",
                "default": "",
                "required": True,
                "description": "Recipient phone number(s) (comma separated)",
                "display_options": {
                    "show": {
                        "resource": ["sms", "verify", "call"],
                        "operation": ["send", "statusbyreceptor", "lookup", "maketts"]
                    }
                },
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "required": True,
                "description": "Message text",
                "display_options": {
                    "show": {
                        "resource": ["sms", "call"],
                        "operation": ["send", "maketts"]
                    }
                },
            },
            {
                "name": "sender",
                "type": NodeParameterType.STRING,
                "display_name": "Sender",
                "default": "",
                "required": False,
                "description": "Sender line number",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["send", "selectoutbox", "latestoutbox"]
                    }
                },
            },
            {
                "name": "date",
                "type": NodeParameterType.NUMBER,
                "display_name": "Date (UnixTime)",
                "default": 0,
                "required": False,
                "description": "Send time in UnixTime format (0 for immediate)",
                "display_options": {
                    "show": {
                        "resource": ["sms", "call"],
                        "operation": ["send", "maketts", "sendarray"]
                    }
                },
            },
            {
                "name": "localid",
                "type": NodeParameterType.STRING,
                "display_name": "Local ID",
                "default": "",
                "required": False,
                "description": "Your local database ID(s) (comma separated)",
                "display_options": {
                    "show": {
                        "resource": ["sms", "call"],
                        "operation": ["send", "statuslocalmessageid", "maketts"]
                    }
                },
            },
            {
                "name": "hide",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Hide",
                "default": False,
                "required": False,
                "description": "Hide recipient number in list",
                "display_options": {
                    "show": {
                        "resource": ["sms", "call"],
                        "operation": ["send", "sendarray", "maketts"]
                    }
                },
            },
            {
                "name": "tag",
                "type": NodeParameterType.STRING,
                "display_name": "Tag",
                "default": "",
                "required": False,
                "description": "Tag name (English letters and numbers only)",
                "display_options": {
                    "show": {
                        "resource": ["sms", "verify", "call"],
                        "operation": ["send", "sendarray", "lookup", "maketts"]
                    }
                },
            },
            {
                "name": "policy",
                "type": NodeParameterType.STRING,
                "display_name": "Policy",
                "default": "",
                "required": False,
                "description": "Send flow name - If you have defined a send flow for your account, you can specify your selected flow in message sending with this parameter.",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["send", "sendarray"]
                    }
                },
            },
            {
                "name": "type",
                "type": NodeParameterType.STRING,
                "display_name": "Type",
                "default": "",
                "required": False,
                "description": "Message type on recipient's phone (Table No. 3) Only available for 3000 lines.",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["send"]
                    }
                },
            },
            
            # =============== SMS SendArray Parameters ===============
            {
                "name": "receptorArray",
                "type": NodeParameterType.JSON,
                "display_name": "Receptor Array",
                # "default": '["09123456789"]',
                "required": True,
                "description": "Array of recipient numbers",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["sendarray"]
                    }
                },
            },
            {
                "name": "senderArray",
                "type": NodeParameterType.JSON,
                "display_name": "Sender Array",
                # "default": '["10004346"]',
                "required": True,
                "description": "Array of sender numbers",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["sendarray"]
                    }
                },
            },
            {
                "name": "messageArray",
                "type": NodeParameterType.JSON,
                "display_name": "Message Array",
                "default": '["Test message"]',
                "required": True,
                "description": "Array of messages",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["sendarray"]
                    }
                },
            },
            {
                "name": "localmessageidsArray",
                "type": NodeParameterType.JSON,
                "display_name": "Local Message IDs Array",
                "default": '[]',
                "required": False,
                "description": "Array of local message IDs",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["sendarray"]
                    }
                },
            },
            
            # =============== Status Parameters ===============
            {
                "name": "messageid",
                "type": NodeParameterType.STRING,
                "display_name": "Message ID",
                "default": "",
                "required": True,
                "description": "SMS message ID(s) (comma separated)",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["status", "select", "cancel"]
                    }
                },
            },
            
            # =============== Date Range Parameters ===============
            {
                "name": "startdate",
                "type": NodeParameterType.NUMBER,
                "display_name": "Start Date (UnixTime)",
                "default": 0,
                "required": True,
                "description": "Start date in UnixTime format",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["statusbyreceptor", "selectoutbox", "countoutbox", "countinbox", "inboxpaged"]
                    }
                },
            },
            {
                "name": "enddate",
                "type": NodeParameterType.NUMBER,
                "display_name": "End Date (UnixTime)",
                "default": 0,
                "required": False,
                "description": "End date in UnixTime format",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["statusbyreceptor", "selectoutbox", "countoutbox", "countinbox", "inboxpaged"]
                    }
                },
            },
            
            # =============== Receive/Inbox Parameters ===============
            {
                "name": "linenumber",
                "type": NodeParameterType.STRING,
                "display_name": "Line Number",
                "default": "",
                "required": True,
                "description": "Desired line number",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["receive", "inboxpaged", "countinbox"]
                    }
                },
            },
            {
                "name": "isread",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Is Read",
                "options": [
                    {"name": "Unread", "value": "0"},
                    {"name": "Read", "value": "1"},
                ],
                "default": "0",
                "required": True,
                "description": "Read status",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["receive", "inboxpaged", "countinbox"]
                    }
                },
            },
            
            # =============== Pagination Parameters ===============
            {
                "name": "pagesize",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Size",
                "default": 200,
                "required": False,
                "description": "Number of records (max 500)",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["latestoutbox"]
                    }
                },
            },
            {
                "name": "pagenumber",
                "type": NodeParameterType.NUMBER,
                "display_name": "Page Number",
                "default": 1,
                "required": False,
                "description": "Page number",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["inboxpaged"]
                    }
                },
            },
            
            # =============== Additional Status Parameters ===============
            {
                "name": "status",
                "type": NodeParameterType.NUMBER,
                "display_name": "Status",
                "default": 0,
                "required": False,
                "description": "SMS status filter",
                "display_options": {
                    "show": {
                        "resource": ["sms"],
                        "operation": ["countoutbox"]
                    }
                },
            },
            
            # =============== Verify Lookup Parameters ===============
            {
                "name": "token",
                "type": NodeParameterType.STRING,
                "display_name": "Token",
                "default": "",
                "required": True,
                "description": "First token (verification code)",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "token2",
                "type": NodeParameterType.STRING,
                "display_name": "Token 2",
                "default": "",
                "required": False,
                "description": "Second token",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "token3",
                "type": NodeParameterType.STRING,
                "display_name": "Token 3",
                "default": "",
                "required": False,
                "description": "Third token",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "token10",
                "type": NodeParameterType.STRING,
                "display_name": "Token 10",
                "default": "",
                "required": False,
                "description": "Tenth token (can have 5 spaces)",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "token20",
                "type": NodeParameterType.STRING,
                "display_name": "Token 20",
                "default": "",
                "required": False,
                "description": "Twentieth token (can have 8 spaces)",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "template",
                "type": NodeParameterType.STRING,
                "display_name": "Template",
                "default": "",
                "required": True,
                "description": "Verification template name",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            {
                "name": "verify_type",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Type",
                "options": [
                    {"name": "SMS", "value": "sms"},
                    {"name": "Call", "value": "call"},
                ],
                "default": "sms",
                "required": False,
                "description": "Message type (SMS or voice call) - default is SMS",
                "display_options": {
                    "show": {
                        "resource": ["verify"],
                        "operation": ["lookup"]
                    }
                },
            },
            
            # =============== Account Config Parameters ===============
            {
                "name": "apilogs",
                "type": NodeParameterType.OPTIONS,
                "display_name": "API Logs",
                "options": [
                    {"name": "Disabled", "value": "disabled"},
                    {"name": "Just Faults", "value": "justfaults"},
                    {"name": "Enabled", "value": "enabled"},
                ],
                "default": "justfaults",
                "required": False,
                "description": "API request log status",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["config"]
                    }
                },
            },
            {
                "name": "debugmode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Debug Mode",
                "options": [
                    {"name": "Disabled", "value": "disabled"},
                    {"name": "Enabled", "value": "enabled"},
                ],
                "default": "disabled",
                "required": False,
                "description": "Debug mode (SMS will not be sent)",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["config"]
                    }
                },
            },
            {
                "name": "defaultsender",
                "type": NodeParameterType.STRING,
                "display_name": "Default Sender",
                "default": "",
                "required": False,
                "description": "Default sender line",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["config"]
                    }
                },
            },
            # =============== Custom Account Config Parameters ===============
            {
                "name": "mincreditalarm",
                "type": NodeParameterType.NUMBER,
                "display_name": "Minimum Credit Alarm",
                "default": 0,
                "required": False,
                "description": "This parameter sets the minimum account credit for receiving a low credit alert (in Rial).",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["config"]
                    }
                },
            },
            {
                "name": "resendfailed",
                "type": NodeParameterType.STRING,
                "display_name": "Resend Failed Messages",
                "default": "",
                "required": False,
                "description": "This parameter specifies the status of automatic resend for messages that failed to reach the recipient.",
                "display_options": {
                    "show": {
                        "resource": ["account"],
                        "operation": ["config"]
                    }
                },
            },
        ],

        "credentials": [
            {
                "name": "kavenegarApi",
                "required": True,
                "displayName": "Kavenegar API",
            }
        ],
    }

    def _get_api_url(self) -> str:
        """Get Kavenegar API URL with API key"""
        credentials = self.get_credentials("kavenegarApi")
        if not credentials:
            raise ValueError("Kavenegar API credentials not found")

        api_key = credentials.get("apiKey")
        api_url = credentials.get("apiUrl", "https://api.kavenegar.com")

        if not api_key:
            raise ValueError("API Key is required for Kavenegar API")

        return f"{api_url.rstrip('/')}/v1/{api_key}"

    def _validate_phone_number(self, phone: str) -> bool:
        """Validate Iranian phone number format"""
        if not phone:
            return False
        
        # Remove common prefixes and clean the number
        clean_phone = phone.replace('+98', '').replace('0098', '').replace(' ', '').replace('-', '')
        
        # Iranian mobile numbers: 9xxxxxxxxx (10 digits starting with 9)
        # Iranian landline numbers: various patterns
        if clean_phone.startswith('9') and len(clean_phone) == 10 and clean_phone.isdigit():
            return True
        
        # Full format: 09xxxxxxxxx (11 digits)
        if clean_phone.startswith('09') and len(clean_phone) == 11 and clean_phone.isdigit():
            return True
            
        # International format: 989xxxxxxxxx (12 digits)
        if clean_phone.startswith('989') and len(clean_phone) == 12 and clean_phone.isdigit():
            return True
        
        return False
    
    def _validate_sender_number(self, sender: str) -> bool:
        """Validate sender number format"""
        if not sender:
            return True  # Optional parameter
        
        # Sender can be a short code (4-6 digits) or a phone number
        if sender.isdigit() and 4 <= len(sender) <= 12:
            return True
            
        # Or a text sender ID (for some accounts)
        if sender.isalnum() and len(sender) <= 11:
            return True
            
        return False

    def _format_api_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Format Kavenegar API response for better readability"""
        if not response:
            return response
            
        formatted_response = dict(response)
        
        # Add human-readable status information
        if 'return' in response:
            return_data = response['return']
            if 'status' in return_data:
                status_code = return_data['status']
                formatted_response['human_readable_status'] = self._get_status_description(status_code)
        
        # Format entries data if present
        if 'entries' in response and isinstance(response['entries'], dict):
            entries = response['entries']
            
            # Format dates if present
            if 'date' in entries:
                try:
                    timestamp = int(entries['date'])
                    formatted_response['entries'] = dict(entries)
                    formatted_response['entries']['formatted_date'] = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pass
                    
            # Format status codes in entries
            if 'status' in entries:
                try:
                    status = int(entries['status'])
                    if 'entries' not in formatted_response:
                        formatted_response['entries'] = dict(entries)
                    formatted_response['entries']['status_description'] = self._get_sms_status_description(status)
                except (ValueError, TypeError):
                    pass
        
        return formatted_response
    
    def _get_status_description(self, status_code: int) -> str:
        """Get human-readable description for Kavenegar API status codes"""
        status_descriptions = {
            200: "Success",
            400: "Invalid parameters",
            401: "Invalid API key",
            402: "Insufficient credit",
            403: "Access denied",
            404: "Not found",
            405: "Method not allowed",
            406: "Invalid data format",
            407: "Invalid phone number",
            408: "Invalid sender number",
            409: "Empty message",
            411: "Invalid recipient count",
            412: "Message too long",
            413: "Invalid date format",
            414: "Account suspended",
            415: "Invalid template",
            416: "Service unavailable",
            417: "Invalid IP",
            418: "Account expired",
            422: "Invalid parameters",
            429: "Rate limit exceeded",
            500: "Server error"
        }
        return status_descriptions.get(status_code, f"Unknown status code: {status_code}")
    
    def _get_sms_status_description(self, status_code: int) -> str:
        """Get human-readable description for SMS status codes"""
        sms_status_descriptions = {
            1: "Queued",
            2: "Scheduled",
            4: "Sent to operator",
            5: "Sent to phone",
            6: "Failed",
            10: "Delivered",
            11: "Not delivered",
            13: "Canceled",
            14: "Blocked",
            100: "Received"
        }
        return sms_status_descriptions.get(status_code, f"Unknown SMS status: {status_code}")

    def _make_request(self, endpoint: str, params: Dict[str, Any] = None, method: str = "GET") -> Dict[str, Any]:
        """Make a request to Kavenegar API"""
        api_base_url = self._get_api_url()
        url = f"{api_base_url}/{endpoint}"
        
        try:
            # Make the request
            if method == "POST":
                response = requests.post(url, data=params, timeout=30)
            else:
                response = requests.get(url, params=params, timeout=30)
            
            # Parse response
            try:
                json_response = response.json()
            except json.JSONDecodeError:
                raise ValueError(f"Invalid response from Kavenegar API (HTTP {response.status_code}): {response.text[:200]}")
            
            # Check for API-level errors
            if 'return' in json_response:
                api_status = json_response['return'].get('status')
                api_message = json_response['return'].get('message', 'Unknown error')
                
                if api_status != 200:
                    # Get human-readable error description
                    error_desc = self._get_status_description(api_status)
                    
                    error_details = {
                        "kavenegar_error": True,
                        "status_code": api_status,
                        "message": api_message,
                        "description": error_desc,
                        "endpoint": endpoint,
                        "request_method": method
                    }
                    
                    # Add request parameters (mask sensitive data)
                    if params:
                        safe_params = dict(params)
                        # Mask sensitive information
                        if 'token' in safe_params:
                            safe_params['token'] = f"{safe_params['token'][:3]}***"
                        if 'message' in safe_params and len(safe_params['message']) > 50:
                            safe_params['message'] = safe_params['message'][:50] + "..."
                        error_details["request_params"] = safe_params
                    
                    raise ValueError(f"Kavenegar API Error {api_status}: {api_message} ({error_desc})")
            
            # Format successful response
            formatted_response = self._format_api_response(json_response)
            return formatted_response
            
        except requests.exceptions.Timeout:
            raise ValueError(f"Request timeout: Kavenegar API did not respond within 30 seconds for {endpoint}")
            
        except requests.exceptions.ConnectionError as e:
            raise ValueError(f"Connection failed: Unable to reach Kavenegar API at {url}")
            
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None:
                raise ValueError(f"HTTP {e.response.status_code}: {e.response.text[:200]}")
            else:
                raise ValueError(f"Request failed: {str(e)}")
        
        except ValueError:
            # Re-raise our custom ValueError messages
            raise
            
        except Exception as e:
            raise ValueError(f"Unexpected error calling {endpoint}: {str(e)}")

    def _send_sms(self, item_index: int) -> Dict[str, Any]:
        """Send simple SMS"""
        # Get parameters using the new method
        receptor = self.get_node_parameter("receptor", item_index, "")
        message = self.get_node_parameter("message", item_index, "")
        sender = self.get_node_parameter("sender", item_index, "")
        date = self.get_node_parameter("date", item_index, "")
        localid = self.get_node_parameter("localid", item_index, "")
        hide = self.get_node_parameter("hide", item_index, False)
        tag = self.get_node_parameter("tag", item_index, "")
        policy = self.get_node_parameter("policy", item_index, "")
        sms_type = self.get_node_parameter("type", item_index, "")

        # Enhanced parameter validation
        validation_errors = []
        if not receptor or receptor.strip() == "":
            validation_errors.append("Receptor (phone number) is required")
        elif not self._validate_phone_number(receptor):
            validation_errors.append(f"Invalid phone number: {receptor}")
        
        if not message or message.strip() == "":
            validation_errors.append("Message text is required")
        elif len(message) > 612:
            validation_errors.append(f"Message too long ({len(message)} chars, max 612)")
        
        if sender and not self._validate_sender_number(sender):
            validation_errors.append(f"Invalid sender number: {sender}")
        
        if date and not str(date).isdigit():
            validation_errors.append(f"Date must be Unix timestamp, got: {date}")
            
        if validation_errors:
            raise ValueError("SMS validation failed: " + "; ".join(validation_errors))

        request_params = {
            "receptor": receptor.strip(),
            "message": message,
        }
        
        # Optional parameters
        if sender:
            request_params["sender"] = sender.strip()
        if date:
            request_params["date"] = date
        if localid:
            request_params["localid"] = localid
        if hide:
            request_params["hide"] = 1
        if tag:
            request_params["tag"] = tag
        if policy:
            request_params["policy"] = policy
        if sms_type:
            request_params["type"] = sms_type
        
        return self._make_request("sms/send.json", request_params)

    def _send_array(self, item_index: int) -> Dict[str, Any]:
        """Send array SMS"""
        receptor_array_str = self.get_node_parameter("receptorArray", item_index, "[]")
        sender_array_str = self.get_node_parameter("senderArray", item_index, "[]")
        message_array_str = self.get_node_parameter("messageArray", item_index, "[]")
        localmessageids_array_str = self.get_node_parameter("localmessageidsArray", item_index, "[]")
        hide = self.get_node_parameter("hide", item_index, False)
        tag = self.get_node_parameter("tag", item_index, "")
        date = self.get_node_parameter("date", item_index, "")
        policy = self.get_node_parameter("policy", item_index, "")
        
        try:
            receptor_array = json.loads(receptor_array_str)
            sender_array = json.loads(sender_array_str)
            message_array = json.loads(message_array_str)
            
            request_params = {
                "receptor": json.dumps(receptor_array),
                "sender": json.dumps(sender_array),
                "message": json.dumps(message_array),
            }
            
            # Optional parameters
            if localmessageids_array_str and localmessageids_array_str != "[]":
                localmessageids_array = json.loads(localmessageids_array_str)
                request_params["localmessageids"] = json.dumps(localmessageids_array)
            if hide:
                request_params["hide"] = 1
            if tag:
                request_params["tag"] = tag
            if date:
                request_params["date"] = date
            if policy:
                request_params["policy"] = policy
            
            return self._make_request("sms/sendarray.json", request_params, "POST")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in array parameters: {str(e)}")

    def _get_status(self, item_index: int) -> Dict[str, Any]:
        """Get SMS status"""
        messageid = self.get_node_parameter("messageid", item_index, "")
        if not messageid:
            raise ValueError("Message ID is required for status check")
        request_params = {
            "messageid": messageid,
        }
        return self._make_request("sms/status.json", request_params)

    def _get_status_local_id(self, item_index: int) -> Dict[str, Any]:
        """Get SMS status by local ID"""
        localid = self.get_node_parameter("localid", item_index, "")
        if not localid:
            raise ValueError("Local ID is required for status check")
        request_params = {
            "localid": localid,
        }
        return self._make_request("sms/statuslocalmessageid.json", request_params)

    def _get_status_by_receptor(self, item_index: int) -> Dict[str, Any]:
        """Get SMS status by receptor"""
        receptor = self.get_node_parameter("receptor", item_index, "")
        startdate = self.get_node_parameter("startdate", item_index, "")
        enddate = self.get_node_parameter("enddate", item_index, "")
        
        if not receptor:
            raise ValueError("Receptor is required for status check by receptor")
        
        request_params = {
            "receptor": receptor,
            "startdate": startdate,
        }
        if enddate:
            request_params["enddate"] = enddate
        
        return self._make_request("sms/statusbyreceptor.json", request_params)

    def _select_sms(self, item_index: int) -> Dict[str, Any]:
        """Select SMS"""
        messageid = self.get_node_parameter("messageid", item_index, "")
        if not messageid:
            raise ValueError("Message ID is required for SMS selection")
        request_params = {
            "messageid": messageid,
        }
        return self._make_request("sms/select.json", request_params)

    def _select_outbox(self, item_index: int) -> Dict[str, Any]:
        """Select outbox"""
        startdate = self.get_node_parameter("startdate", item_index, "")
        enddate = self.get_node_parameter("enddate", item_index, "")
        sender = self.get_node_parameter("sender", item_index, "")
        
        if not startdate:
            raise ValueError("Start date is required for outbox selection")
        
        request_params = {
            "startdate": startdate,
        }
        if enddate:
            request_params["enddate"] = enddate
        if sender:
            request_params["sender"] = sender
        
        return self._make_request("sms/selectoutbox.json", request_params)

    def _latest_outbox(self, item_index: int) -> Dict[str, Any]:
        """Get latest outbox"""
        pagesize = self.get_node_parameter("pagesize", item_index, "")
        sender = self.get_node_parameter("sender", item_index, "")
        
        request_params = {}
        if pagesize:
            request_params["pagesize"] = pagesize
        if sender:
            request_params["sender"] = sender
        
        return self._make_request("sms/latestoutbox.json", request_params)

    def _count_outbox(self, item_index: int) -> Dict[str, Any]:
        """Count outbox"""
        startdate = self.get_node_parameter("startdate", item_index, "")
        enddate = self.get_node_parameter("enddate", item_index, "")
        status = self.get_node_parameter("status", item_index, "")
        
        if not startdate:
            raise ValueError("Start date is required for outbox count")
        
        request_params = {
            "startdate": startdate,
        }
        if enddate:
            request_params["enddate"] = enddate
        if status:
            request_params["status"] = status
        
        return self._make_request("sms/countoutbox.json", request_params)

    def _cancel_sms(self, item_index: int) -> Dict[str, Any]:
        """Cancel SMS"""
        messageid = self.get_node_parameter("messageid", item_index, "")
        if not messageid:
            raise ValueError("Message ID is required to cancel SMS")
        request_params = {
            "messageid": messageid,
        }
        return self._make_request("sms/cancel.json", request_params)

    def _receive_sms(self, item_index: int) -> Dict[str, Any]:
        """Receive SMS"""
        linenumber = self.get_node_parameter("linenumber", item_index, "")
        isread = self.get_node_parameter("isread", item_index, "")
        
        if not linenumber:
            raise ValueError("Line number is required to receive SMS")
        
        request_params = {
            "linenumber": linenumber,
        }
        if isread:
            request_params["isread"] = isread
        
        return self._make_request("sms/receive.json", request_params)

    def _inbox_paged(self, item_index: int) -> Dict[str, Any]:
        """Get inbox paged"""
        linenumber = self.get_node_parameter("linenumber", item_index, "")
        isread = self.get_node_parameter("isread", item_index, "")
        startdate = self.get_node_parameter("startdate", item_index, "")
        enddate = self.get_node_parameter("enddate", item_index, "")
        pagenumber = self.get_node_parameter("pagenumber", item_index, "")
        
        request_params = {}
        if linenumber:
            request_params["linenumber"] = linenumber
        if isread:
            request_params["isread"] = isread
        if startdate:
            request_params["startdate"] = startdate
        if enddate:
            request_params["enddate"] = enddate
        if pagenumber:
            request_params["pagenumber"] = pagenumber
        
        return self._make_request("sms/inboxpaged.json", request_params)

    def _count_inbox(self, item_index: int) -> Dict[str, Any]:
        """Count inbox"""
        startdate = self.get_node_parameter("startdate", item_index, "")
        enddate = self.get_node_parameter("enddate", item_index, "")
        linenumber = self.get_node_parameter("linenumber", item_index, "")
        isread = self.get_node_parameter("isread", item_index, "")
        
        request_params = {}
        if startdate:
            request_params["startdate"] = startdate
        if enddate:
            request_params["enddate"] = enddate
        if linenumber:
            request_params["linenumber"] = linenumber
        if isread:
            request_params["isread"] = isread
        
        return self._make_request("sms/countinbox.json", request_params)

    def _verify_lookup(self, item_index: int) -> Dict[str, Any]:
        """Send verification code"""
        receptor = self.get_node_parameter("receptor", item_index, "")
        token = self.get_node_parameter("token", item_index, "")
        template = self.get_node_parameter("template", item_index, "")
        
        # Enhanced validation
        validation_errors = []
        if not receptor or receptor.strip() == "":
            validation_errors.append("Receptor (phone number) is required")
        elif not self._validate_phone_number(receptor):
            validation_errors.append(f"Invalid phone number: {receptor}")
            
        if not template or template.strip() == "":
            validation_errors.append("Template name is required")
        
        if not token or token.strip() == "":
            validation_errors.append("Verification token is required")
            
        if validation_errors:
            raise ValueError("Verification validation failed: " + "; ".join(validation_errors))
        
        request_params = {
            "receptor": receptor.strip(),
            "token": token,
            "template": template.strip(),
        }
        
        # Optional tokens
        token2 = self.get_node_parameter("token2", item_index, "")
        token3 = self.get_node_parameter("token3", item_index, "")
        token10 = self.get_node_parameter("token10", item_index, "")
        token20 = self.get_node_parameter("token20", item_index, "")
        verify_type = self.get_node_parameter("verify_type", item_index, "")
        tag = self.get_node_parameter("tag", item_index, "")
        
        if token2:
            request_params["token2"] = token2
        if token3:
            request_params["token3"] = token3
        if token10:
            request_params["token10"] = token10
        if token20:
            request_params["token20"] = token20
        if verify_type:
            request_params["type"] = verify_type
        if tag:
            request_params["tag"] = tag
        
        return self._make_request("verify/lookup.json", request_params)

    def _make_tts(self, item_index: int) -> Dict[str, Any]:
        """Make text-to-speech call"""
        receptor = self.get_node_parameter("receptor", item_index, "")
        message = self.get_node_parameter("message", item_index, "")
        
        if not receptor or not message:
            raise ValueError("Receptor and message are required for TTS call")
        
        request_params = {
            "receptor": receptor,
            "message": message,
        }
        
        # Optional parameters
        date = self.get_node_parameter("date", item_index, "")
        localid = self.get_node_parameter("localid", item_index, "")
        hide = self.get_node_parameter("hide", item_index, False)
        tag = self.get_node_parameter("tag", item_index, "")
        
        if date:
            request_params["date"] = date
        if localid:
            request_params["localid"] = localid
        if hide:
            request_params["hide"] = 1
        if tag:
            request_params["tag"] = tag
        
        return self._make_request("call/maketts.json", request_params)

    def _account_info(self, item_index: int) -> Dict[str, Any]:
        """Get account info"""
        return self._make_request("account/info.json")

    def _account_config(self, item_index: int) -> Dict[str, Any]:
        """Get or set account config"""
        apilogs = self.get_node_parameter("apilogs", item_index, "")
        debugmode = self.get_node_parameter("debugmode", item_index, "")
        defaultsender = self.get_node_parameter("defaultsender", item_index, "")
        mincreditalarm = self.get_node_parameter("mincreditalarm", item_index, "")
        resendfailed = self.get_node_parameter("resendfailed", item_index, "")
        
        request_params = {}
        
        if apilogs:
            request_params["apilogs"] = apilogs
        if debugmode:
            request_params["debugmode"] = debugmode
        if defaultsender:
            request_params["defaultsender"] = defaultsender
        if mincreditalarm:
            request_params["mincreditalarm"] = mincreditalarm
        if resendfailed:
            request_params["resendfailed"] = resendfailed
        
        # If no params, just get config
        if not request_params:
            return self._make_request("account/config.json")
        
        return self._make_request("account/config.json", request_params)

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Kavenegar operation and return properly formatted data"""

        try:
            # Get input data using the new method signature
            input_data = self.get_input_data()

            result_items: List[NodeExecutionData] = []

            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Get parameters for this item using the new method
                    resource = self.get_node_parameter("resource", i, "sms")
                    operation = self.get_node_parameter("operation", i, "send")

                    # Execute the appropriate operation
                    result = None
                    
                    if resource == "sms":
                        if operation == "send":
                            result = self._send_sms(i)
                        elif operation == "sendarray":
                            result = self._send_array(i)
                        elif operation == "status":
                            result = self._get_status(i)
                        elif operation == "statuslocalmessageid":
                            result = self._get_status_local_id(i)
                        elif operation == "statusbyreceptor":
                            result = self._get_status_by_receptor(i)
                        elif operation == "select":
                            result = self._select_sms(i)
                        elif operation == "selectoutbox":
                            result = self._select_outbox(i)
                        elif operation == "latestoutbox":
                            result = self._latest_outbox(i)
                        elif operation == "countoutbox":
                            result = self._count_outbox(i)
                        elif operation == "cancel":
                            result = self._cancel_sms(i)
                        elif operation == "receive":
                            result = self._receive_sms(i)
                        elif operation == "inboxpaged":
                            result = self._inbox_paged(i)
                        elif operation == "countinbox":
                            result = self._count_inbox(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    elif resource == "verify":
                        if operation == "lookup":
                            result = self._verify_lookup(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    elif resource == "call":
                        if operation == "maketts":
                            result = self._make_tts(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    elif resource == "account":
                        if operation == "info":
                            result = self._account_info(i)
                        elif operation == "config":
                            result = self._account_config(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

                    # Process successful result
                    if isinstance(result, list):
                        for res_item in result:
                            success_result = {
                                "success": True,
                                "operation": operation,
                                "resource": resource,
                                **res_item  # Merge API response data directly
                            }
                            result_items.append(
                                NodeExecutionData(json_data=success_result, binary_data=None)
                            )
                    else:
                        success_result = {
                            "success": True,
                            "operation": operation,
                            "resource": resource,
                            **result  # Merge API response data directly
                        }
                        result_items.append(
                            NodeExecutionData(json_data=success_result, binary_data=None)
                        )

                except Exception as e:
                    # Create clear error information
                    error_info = {
                        "success": False,
                        "error": str(e),
                        "operation": self.get_node_parameter("operation", i, "send"),
                        "resource": self.get_node_parameter("resource", i, "sms"),
                        "item_index": i
                    }
                    
                    # Add request status if it's a Kavenegar API error
                    if "Kavenegar API Error" in str(e):
                        error_info["error_type"] = "kavenegar_api_error"
                        # Extract status code from error message if present
                        import re
                        status_match = re.search(r'Error (\d+):', str(e))
                        if status_match:
                            error_info["kavenegar_status_code"] = int(status_match.group(1))
                    elif "timeout" in str(e).lower():
                        error_info["error_type"] = "timeout_error"
                    elif "connection" in str(e).lower():
                        error_info["error_type"] = "connection_error"
                    elif "validation failed" in str(e):
                        error_info["error_type"] = "validation_error"
                    else:
                        error_info["error_type"] = "general_error"
                    
                    result_items.append(
                        NodeExecutionData(json_data=error_info, binary_data=None)
                    )

            return [result_items]

        except Exception as e:
            # Handle critical execution errors
            error_data = [
                NodeExecutionData(
                    json_data={
                        "success": False,
                        "error": f"Execution failed: {str(e)}",
                        "error_type": "execution_error"
                    },
                    binary_data=None,
                )
            ]
            return [error_data]
