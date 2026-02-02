from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import json
import logging
import base64
from datetime import datetime, timezone
import html
import uuid
import os
from config import get_settings

logger = logging.getLogger(__name__)


class OnFormSubmissionNode(BaseNode):
    """
    On Form Submission node for handling web form submissions.
    Renders an HTML form on GET requests and processes form data on POST requests.
    """

    type = "form_trigger"  
    version = 1
    is_webhook = True

    description = {
        "displayName": "Form Trigger",
        "name": "FormSubmissionTrigger",
        "icon": "file:form.svg",
        "group": ["trigger"],
        "description": "Starts the workflow when a form is submitted",
        "defaults": {"name": "Form Trigger"},
        "inputs": [],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "eventTriggerDescription": "Waiting for you to submit the form",
        "activationMessage": "You can now make calls to your production Form URL."
    }

    properties = {
        "parameters": [
            {
                "name": "test_path",
                "type": NodeParameterType.STRING, 
                "display_name": "Test Path",
                "default": "{api_base_address}/webhook/test/execute/form_trigger/${webhook_id}",
                "readonly": True,
                "description": "The POST endpoint for form submissions in test mode"
            },
            {
                "name": "path",
                "type": NodeParameterType.STRING,
                "display_name": "Path",
                "default": "{api_base_address}/webhook/${webhook_id}/form_trigger",
                "readonly": True,
                "description": "The POST endpoint for form submissions in production"
            },
            {
                "name": "authentication",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Authentication",
                "options": [
                    {"name": "Basic Auth", "value": "basicAuth"},
                    {"name": "None", "value": "none"}
                ],
                "default": "none",
                "description": "Authentication method to use for the form"
            },
            {
                "name": "formTitle",
                "type": NodeParameterType.STRING,
                "display_name": "Form Title",
                "default": "Submit Form",
                "description": "The title of the form"
            },
            {
                "name": "formDescription",
                "type": NodeParameterType.STRING,
                "display_name": "Form Description",
                "default": "",
                "description": "The description of the form"
            },
            {
                "name": "formFields",
                "type": NodeParameterType.ARRAY,
                "display_name": "Form Elements",
                "default": [],
                "description": "The fields to display in the form",
                "options": [
                    {
                        "name": "fieldName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Field Name",
                        "default": "",
                        "required": True,
                        "description": "Internal name of the field (used as variable name)"
                    },
                    {
                        "name": "fieldType",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Field Type",
                        "options": [
                            {"name": "Single Line Text", "value": "text"},
                            {"name": "Multi Line Text", "value": "textarea"},
                            {"name": "Number", "value": "number"},
                            {"name": "Email", "value": "email"},
                            {"name": "Phone", "value": "phone"},
                            {"name": "Dropdown", "value": "dropdown"},
                            {"name": "Date & Time", "value": "datetime-local"},
                            {"name": "Date", "value": "date"},
                            {"name": "Boolean", "value": "boolean"},
                            {"name": "File", "value": "file"},
                        ],
                        "default": "text",
                        "description": "The type of the field"
                    },
                                        {
                        "name": "fileFormat",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "File Format",
                        "options": [
                            {"name": "Any", "value": "*/*"},
                            {"name": "PDF", "value": "application/pdf"},
                            {"name": "Word (DOC)", "value": "application/msword"},
                            {"name": "Word (DOCX)", "value": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
                            {"name": "Excel (XLS)", "value": "application/vnd.ms-excel"},
                            {"name": "Excel (XLSX)", "value": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
                            {"name": "PowerPoint (PPT)", "value": "application/vnd.ms-powerpoint"},
                            {"name": "PowerPoint (PPTX)", "value": "application/vnd.openxmlformats-officedocument.presentationml.presentation"},
                            {"name": "Plain Text", "value": "text/plain"},
                            {"name": "CSV", "value": "text/csv"},
                            {"name": "JSON", "value": "application/json"},
                            {"name": "ZIP", "value": "application/zip"},
                            {"name": "Image (JPEG)", "value": "image/jpeg"},
                            {"name": "Image (PNG)", "value": "image/png"},
                            {"name": "Image (GIF)", "value": "image/gif"},
                            {"name": "Any Image", "value": "image/*"}
                        ],
                        "default": "*/*",
                        "description": "Allowed MIME type for this file field (frontend enforces).",
                        "displayOptions": {
                            "show": {
                                "fieldType": ["file"]
                            }
                        }
                    },
                    {
                        "name": "fieldLabel",
                        "type": NodeParameterType.STRING,
                        "display_name": "Field Label",
                        "default": "",
                        "description": "The label shown for the field"
                    },
                    {
                        "name": "placeholder",
                        "type": NodeParameterType.STRING,
                        "display_name": "Placeholder",
                        "default": "",
                        "description": "The placeholder text for the field"
                    },
                    {
                        "name": "required",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Required",
                        "default": False,
                        "description": "Whether the field is required"
                    },
                    {
                        "name": "options",
                        "type": NodeParameterType.ARRAY,
                        "display_name": "Options",
                        "default": [],
                        "description": "Options for dropdown fields",
                        "options": [
                            {
                                "name": "label",
                                "type": NodeParameterType.STRING,
                                "display_name": "Label",
                                "default": "",
                                "description": "Label for the option"
                            },
                            {
                                "name": "value",
                                "type": NodeParameterType.STRING,
                                "display_name": "Value",
                                "default": "",
                                "description": "Value for the option"
                            }
                        ],
                        "displayOptions": {
                            "show": {
                                "fieldType": ["dropdown"]
                            }
                        }
                    },
                    {
                        "name": "defaultValue",
                        "type": NodeParameterType.STRING,
                        "display_name": "Default Value",
                        "default": "",
                        "description": "Default value for the field"
                    }
                ]
            },
            {
                "name": "responseMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Respond When",
                "options": [
                    {"name": "Form Is Submitted", "value": "onReceived"},
                    {"name": "Last Node Finishes", "value": "lastNode"},
                    {"name": "Using Respond to Webhook Node", "value": "responseNode"}
                ],
                "default": "onReceived",
                "description": "When to send the response"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "appendAttribution",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Append Attribution",
                        "default": True,
                        "description": "Whether to append 'Powered by avidflow' to the form"
                    },
                    {
                        "name": "buttonLabel",
                        "type": NodeParameterType.STRING,
                        "display_name": "Button Label",
                        "default": "Submit",
                        "description": "The label of the submit button in the form"
                    },
                    {
                        "name": "path",
                        "type": NodeParameterType.STRING,
                        "display_name": "Path",
                        "default": "",
                        "description": "Override the path set in the main parameters"
                    },
                    {
                        "name": "ignoreBots",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Ignore Bots",
                        "default": False,
                        "description": "Whether to ignore requests from bots like link previewers and web crawlers"
                    },
                    {
                        "name": "useWorkflowTimezone",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Use Workflow Timezone",
                        "default": True,
                        "description": "Whether to use the workflow timezone in 'submittedAt' field or UTC"
                    },
                    {
                        "name": "customCss",
                        "type": NodeParameterType.CODE,
                        "display_name": "Custom Form Styling",
                        "default": "",
                        "description": "Override default styling of the public form interface with CSS"
                    }
                ]
            },
            {
                "name": "httpMethod",
                "type": NodeParameterType.OPTIONS,
                "display_name": "HTTP Method",
                "options": [
                    {"name": "POST", "value": "POST"}
                ],
                "default": "POST",
                "description": "HTTP method to accept (POST only)",
                "readonly": True
            }
        ],
        "credentials": [
            {
                "name": "httpBasicAuth",
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["basicAuth"]
                    }
                }
            }
        ]
    }

    icon = "form.svg"
    color = "#6B7280"

    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        Process form submission data and pass to subsequent nodes.
        Handles both traditional files and embedded JSON file data.
        """
        envelope = self.execution_data if hasattr(self, "execution_data") else {}
        if not envelope or envelope == {}:
            return [[NodeExecutionData(json_data={"warning": "no payload"}, binary_data=None)]]

        # Extract data from envelope
        body = envelope.get("webhookData") or envelope.get("body") or envelope.get("form") or {}
        headers = envelope.get("headers") or {}
        query = envelope.get("query") or {}
        files = envelope.get("files") or {}
        
        try:
            # Initialize binary handling - EXACTLY like TelegramTrigger pattern
            binary = None
            
            # Get settings for file size limits
            settings = get_settings()
            max_upload_size_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
            max_size_bytes = max_upload_size_mb * 1024 * 1024
            
            # Process traditional files parameter (if any)
            if files:
                binary = {}
                for field_name, file_info in files.items():
                    if self._process_file_data(field_name, file_info, binary, max_size_bytes):
                        logger.info(f"Successfully processed traditional file: {field_name}")
        
            # MAIN PROCESSING: Handle formFields at different levels
            form_fields = []
            
            # Try different body structures based on what we're actually receiving
            if "formFields" in body:
                # Direct formFields in body (your current case)
                form_fields = body.get("formFields", [])
                logger.info(f"Found formFields directly in body: {len(form_fields)} fields")
            elif "form" in body and isinstance(body["form"], dict):
                # Nested under form key
                form_data = body.get("form", {})
                form_fields = form_data.get("formFields", [])
                logger.info(f"Found formFields in body.form: {len(form_fields)} fields")
            else:
                # Legacy: body itself might be the form data
                form_fields = body.get("formFields", [])
                logger.info(f"Fallback: searching for formFields in body: {len(form_fields)} fields")
        
            if form_fields:
                if not binary:
                    binary = {}
                    
                # Process each form field
                for field in form_fields:
                    field_name = field.get("fieldName", "")
                    field_type = field.get("fieldType", "text")
                    default_value = field.get("defaultValue")
                    
                    # Only process file type fields with binary data
                    if field_type == "file" and isinstance(default_value, dict):
                        logger.info(f"Processing file field: {field_name}")
                        # Extract file information from defaultValue
                        file_data = default_value.get("data", "")
                        file_name = default_value.get("fileName", f"upload-{field_name}")
                        mime_type = default_value.get("mimeType", "application/octet-stream")
                        file_size = default_value.get("size", 0)
                        
                        if file_data and self._is_valid_file_field(field_name):
                            # Validate file size
                            if file_size > max_size_bytes:
                                logger.warning(f"File {field_name} exceeds size limit: {file_size} > {max_size_bytes}")
                                continue
                            
                            # Convert and store - EXACTLY like Gmail/Telegram pattern
                            try:
                                # Validate base64 data
                                raw_bytes = base64.b64decode(file_data, validate=True)
                                
                                # Store using field name as binary key - CRITICAL for n8n compatibility
                                binary[field_name] = {
                                    "data": self.compress_data(file_data),  # Use original base64
                                    "mimeType": mime_type,
                                    "fileName": file_name,
                                    "size": file_size
                                }
                                
                                logger.info(f"Successfully processed form field file: {field_name}")
                                
                            except Exception as e:
                                logger.warning(f"Invalid base64 data for file field {field_name}: {str(e)}")
                                continue
        
            # Legacy support: Handle other JSON embedded files
            self._process_legacy_json_files(body, binary, max_size_bytes)
            
            # Set binary to None if empty (n8n compatibility)
            if not binary:
                binary = None
            
            # Process form data (non-file fields) - FIXED
            validated_form_data = self._extract_form_data(form_fields)
            logger.info(f"Extracted validated form data: {validated_form_data}")
            
            # Create final payload - EXACTLY like Gmail/Telegram structure
            json_data = {
                "form": validated_form_data,
                "query": query,
                "headers": headers,
                "meta": {
                    "workflow_id": getattr(self, "workflow_id", ""),
                    "node_id": getattr(self, "node_id", ""),
                    "source": "form_trigger",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "test_mode": False
                }
            }
            
            # Return in n8n format - EXACTLY like other triggers
            return [[NodeExecutionData(json_data=json_data, binary_data=binary)]]
        
        except Exception as e:
            import traceback
            logger.exception("Error in Form Submission trigger")
            error_data = NodeExecutionData(
                json_data={
                    "error": str(e),
                    "details": traceback.format_exc(),
                    "received_data": {
                        "body": body,
                        "headers": headers,
                        "query": query
                    }
                },
                binary_data=None
            )
            return [[error_data]]

    def _process_file_data(
        self, 
        field_name: str, 
        file_info: Dict[str, Any], 
        binary: Dict[str, Any], 
        max_size_bytes: int
    ) -> bool:
        """
        Process file data in traditional format - EXACTLY like TelegramTrigger
        """
        try:
            file_data = file_info.get("data", "")
            
            # Normalize to raw bytes - EXACTLY like TelegramTrigger
            if isinstance(file_data, bytes):
                raw = file_data
            elif isinstance(file_data, str):
                try:
                    raw = base64.b64decode(file_data, validate=True)
                except Exception:
                    raw = file_data.encode()
            else:
                return False
            
            # Check file size
            if len(raw) > max_size_bytes:
                logger.warning(f"File {field_name} exceeds size limit: {len(raw)} > {max_size_bytes}")
                return False
                
            # Get file information
            file_name = file_info.get("fileName", f"upload-{field_name}")
            mime_type = file_info.get("mimeType", "application/octet-stream")
            
            # Convert to base64 and compress - EXACTLY like TelegramTrigger
            b64 = base64.b64encode(raw).decode()
            
            # Store using standard binary format - EXACTLY like TelegramTrigger
            binary[field_name] = {
                "data": self.compress_data(b64),
                "mimeType": mime_type,
                "fileName": file_name,
                "size": len(raw)
            }
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to process file {field_name}: {str(e)}")
            return False

    def _is_valid_file_field(self, field_name: str) -> bool:
        """
        Check if field_name corresponds to a configured file field
        """
        form_fields = self.get_node_parameter("formFields", 0, [])
        
        for field in form_fields:
            if (field.get("fieldName") == field_name and 
                field.get("fieldType") == "file"):
                return True
        
        return False

    def _extract_form_data(self, form_fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Extract non-file form data from formFields structure
        """
        form_data = {}
        
        for field in form_fields:
            field_name = field.get("fieldName", "")
            field_type = field.get("fieldType", "text")
            default_value = field.get("defaultValue")
            
            # Skip file fields - they're handled in binary
            if field_type == "file":
                continue
                
            # Type conversion based on field type
            if field_name and default_value is not None:
                if field_type == "number":
                    try:
                        form_data[field_name] = float(default_value)
                    except (ValueError, TypeError):
                        form_data[field_name] = default_value
                elif field_type == "boolean":
                    if isinstance(default_value, bool):
                        form_data[field_name] = default_value
                    elif default_value in (True, "true", "True", "yes", "1", "on", 1):
                        form_data[field_name] = True
                    else:
                        form_data[field_name] = False
                else:
                    form_data[field_name] = default_value
        
        return form_data

    def _process_legacy_json_files(
        self, 
        body: Dict[str, Any], 
        binary: Optional[Dict[str, Any]], 
        max_size_bytes: int
    ) -> None:
        """
        Process legacy JSON embedded files for backward compatibility
        """
        if not binary:
            return
            
        # 1) explicit "file" object in body
        file_obj = body.get("file")
        if isinstance(file_obj, dict):
            self._add_binary_from_json("file", file_obj, binary, max_size_bytes)
            
        # 2) any top-level key whose value contains dataBase64/data
        for k, v in body.items():
            if k == "file":  # already handled
                continue
            if isinstance(v, dict) and (v.get("dataBase64") or v.get("data")):
                self._add_binary_from_json(k, v, binary, max_size_bytes)
                
        # 3) files as list
        files_list = body.get("files")
        if isinstance(files_list, list):
            for idx, f in enumerate(files_list):
                if isinstance(f, dict):
                    key = f.get("fieldName") or f"file_{idx}"
                    self._add_binary_from_json(key, f, binary, max_size_bytes)

    def _add_binary_from_json(
        self, 
        key: str, 
        file_obj: Dict[str, Any], 
        binary_map: Dict[str, Any],
        max_size_bytes: int
    ) -> None:
        """
        Add binary data from JSON structure - EXACTLY like Gmail pattern
        """
        if not isinstance(file_obj, dict):
            return
            
        b64_in = file_obj.get("dataBase64") or file_obj.get("data") or ""
        if not b64_in:
            return
            
        try:
            # Handle both base64 strings and raw data
            if isinstance(b64_in, str):
                raw = base64.b64decode(b64_in, validate=True)
            elif isinstance(b64_in, bytes):
                raw = b64_in
            else:
                return
                
            # Check size
            if len(raw) > max_size_bytes:
                logger.warning(f"Legacy file {key} exceeds size limit: {len(raw)} > {max_size_bytes}")
                return
                
        except Exception:
            logger.warning(f"Invalid base64 data for legacy field {key}")
            return
            
        # Store in standard format - EXACTLY like Gmail/Telegram
        b64 = base64.b64encode(raw).decode("utf-8")
        prop = file_obj.get("fieldName") or key or "attachment"
        mime = file_obj.get("mimeType") or "application/octet-stream"
        name = file_obj.get("fileName") or f"{prop}"
        
        binary_map[prop] = {
            "data": self.compress_data(b64),
            "mimeType": mime,
            "fileName": name,
            "size": len(raw)
        }

    def render_form_html(self) -> str:
        """
        Render HTML form based on configured fields.
        """
        title = self.get_node_parameter("formTitle", 0, "Submit Form")
        description = self.get_node_parameter("formDescription", 0, "")
        fields = self.get_node_parameter("formFields", 0, [])
        options = self.get_node_parameter("options", 0, {})
        
        # Get button label from options
        button_label = options.get("buttonLabel", "Submit")
        
        # Custom CSS
        custom_css = options.get("customCss", "")
        
        # Escape HTML to prevent XSS
        title = html.escape(title)
        description = html.escape(description)
        button_label = html.escape(button_label)
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{title}</title>
            <style>
                :root {{
                    --form-font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    --form-background-color: #f9fafb;
                    --form-width: 100%;
                    --form-max-width: 600px;
                    --form-padding: 2rem;
                    --form-border-radius: 8px;
                    --form-box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                    --form-margin: 2rem auto;
                    --form-header-margin-bottom: 1.5rem;
                    --form-title-font-size: 1.5rem;
                    --form-title-font-weight: 600;
                    --form-title-line-height: 1.2;
                    --form-title-color: #111827;
                    --form-description-font-size: 0.875rem;
                    --form-description-color: #6b7280;
                    --form-description-margin-top: 0.5rem;
                    --form-group-margin-bottom: 1rem;
                    --form-label-display: block;
                    --form-label-font-weight: 500;
                    --form-label-margin-bottom: 0.5rem;
                    --form-input-width: 100%;
                    --form-input-padding: 0.75rem;
                    --form-input-border: 1px solid #d1d5db;
                    --form-input-border-radius: 4px;
                    --form-input-focus-border-color: #3b82f6;
                    --form-input-focus-ring: 0 0 0 2px rgba(59, 130, 246, 0.3);
                    --form-button-background: #3b82f6;
                    --form-button-color: white;
                    --form-button-padding: 0.75rem 1.5rem;
                    --form-button-border: none;
                    --form-button-border-radius: 4px;
                    --form-button-font-weight: 500;
                    --form-button-hover-background: #2563eb;
                    --form-button-cursor: pointer;
                    --form-error-color: #ef4444;
                    --form-required-color: #ef4444;
                    --form-footer-margin-top: 1.5rem;
                    --form-footer-text-align: center;
                    --form-footer-font-size: 0.75rem;
                    --form-footer-color: #6b7280;
                }}
                
                body {{
                    font-family: var(--form-font-family);
                    line-height: 1.6;
                    margin: 0;
                    padding: 0;
                    background-color: var(--form-background-color);
                }}
                
                .form-container {{
                    width: var(--form-width);
                    max-width: var(--form-max-width);
                    padding: var(--form-padding);
                    margin: var(--form-margin);
                    background-color: white;
                    border-radius: var(--form-border-radius);
                    box-shadow: var(--form-box-shadow);
                }}
                
                .form-header {{
                    margin-bottom: var(--form-header-margin-bottom);
                }}
                
                .form-title {{
                    font-size: var(--form-title-font-size);
                    font-weight: var(--form-title-font-weight);
                    line-height: var(--form-title-line-height);
                    color: var(--form-title-color);
                    margin: 0;
                }}
                
                .form-description {{
                    font-size: var(--form-description-font-size);
                    color: var(--form-description-color);
                    margin-top: var(--form-description-margin-top);
                }}
                
                .form-group {{
                    margin-bottom: var(--form-group-margin-bottom);
                }}
                
                .form-label {{
                    display: var(--form-label-display);
                    font-weight: var(--form-label-font-weight);
                    margin-bottom: var(--form-label-margin-bottom);
                }}
                
                .form-control {{
                    width: var(--form-input-width);
                    padding: var(--form-input-padding);
                    border: var(--form-input-border);
                    border-radius: var(--form-input-border-radius);
                    font-family: inherit;
                    font-size: 1rem;
                }}
                
                .form-control:focus {{
                    outline: none;
                    border-color: var(--form-input-focus-border-color);
                    box-shadow: var(--form-input-focus-ring);
                }}
                
                .form-button {{
                    background: var(--form-button-background);
                    color: var(--form-button-color);
                    padding: var(--form-button-padding);
                    border: var(--form-button-border);
                    border-radius: var(--form-button-border-radius);
                    font-size: 1rem;
                    font-weight: var(--form-button-font-weight);
                    cursor: var(--form-button-cursor);
                }}
                
                .form-button:hover {{
                    background: var(--form-button-hover-background);
                }}
                
                .required {{
                    color: var(--form-required-color);
                    margin-left: 0.25rem;
                }}
                
                .form-footer {{
                    margin-top: var(--form-footer-margin-top);
                    text-align: var(--form-footer-text-align);
                    font-size: var(--form-footer-font-size);
                    color: var(--form-footer-color);
                }}
                
                .checkbox-container {{
                    display: flex;
                    align-items: center;
                }}
                
                .checkbox-container input {{
                    margin-right: 0.5rem;
                }}
                
                {custom_css}
            </style>
        </head>
        <body>
            <div class="form-container">
                <div class="form-header">
                    <h1 class="form-title">{title}</h1>
                    {f'<p class="form-description">{description}</p>' if description else ''}
                </div>
                <form method="POST" enctype="multipart/form-data">
        """
        
        for field in fields:
            field_name = field.get("fieldName", "")
            field_type = field.get("fieldType", "text")
            field_label = field.get("fieldLabel", field_name)
            placeholder = field.get("placeholder", "")
            required = field.get("required", False)
            default_value = field.get("defaultValue", "")
            options = field.get("options", [])
            
            # Escape field values
            field_name = html.escape(field_name)
            field_label = html.escape(field_label)
            placeholder = html.escape(placeholder)
            default_value = html.escape(str(default_value))
            
            html_content += f"""
            <div class="form-group">
                <label for="{field_name}" class="form-label">
                    {field_label}{"<span class='required'>*</span>" if required else ""}
                </label>
            """
            
            if field_type in ["text", "email", "number", "phone", "date", "datetime-local"]:
                html_content += f"""
                <input type="{field_type}" id="{field_name}" name="{field_name}" class="form-control"
                       placeholder="{placeholder}" value="{default_value}"
                       {"required" if required else ""}>
                """
            elif field_type == "textarea":
                html_content += f"""
                <textarea id="{field_name}" name="{field_name}" class="form-control"
                          placeholder="{placeholder}" {"required" if required else ""}>{default_value}</textarea>
                """
            elif field_type == "boolean":
                checked = "checked" if default_value in ("true", "True", True, 1) else ""
                html_content += f"""
                <div class="checkbox-container">
                    <input type="checkbox" id="{field_name}" name="{field_name}" 
                           value="true" {checked} {"required" if required else ""}>
                    <span>{field_label}</span>
                </div>
                """
            elif field_type == "dropdown":
                html_content += f"""
                <select id="{field_name}" name="{field_name}" class="form-control" {"required" if required else ""}>
                    <option value="" disabled {'' if default_value else 'selected'}>Select an option</option>
                """
                for option in options:
                    option_label = option.get("label", "")
                    option_value = option.get("value", option_label)
                    selected = "selected" if option_value == default_value else ""
                    html_content += f"""
                    <option value="{html.escape(option_value)}" {selected}>{html.escape(option_label)}</option>
                    """
                html_content += """
                </select>
                """
            elif field_type == "file":
                html_content += f"""
                <input type="file" id="{field_name}" name="{field_name}" class="form-control"
                       {"required" if required else ""}>
                """
            
            html_content += """
            </div>
            """
        
        html_content += f"""
                <div class="form-group">
                    <button type="submit" class="form-button">{button_label}</button>
                </div>
                </form>
        """
        
        # Add attribution if enabled
        append_attribution = options.get("appendAttribution", True)
        if append_attribution:
            html_content += """
                <div class="form-footer">
                    <p>Powered by <a href="https://panel.avidflow.ir" target="_blank" rel="noopener noreferrer">avidflow</a></p>
                </div>
            """
        
        html_content += """
            </div>
        </body>
        </html>
        """
        
        return html_content

    def validate_form_data(self, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate form data against field definitions.
        Returns validated and type-converted data.
        """
        fields = self.get_node_parameter("formFields", 0, [])
        validated_data = {}
        errors = []
        
        for field in fields:
            field_name = field.get("fieldName", "")
            field_type = field.get("fieldType", "text")
            required = field.get("required", False)
            field_options = field.get("options", [])
            
            # Skip file fields - they'll be handled in binary data
            if field_type == "file":
                continue
                
            # Check required fields
            if required and (field_name not in form_data or not form_data.get(field_name)):
                errors.append(f"Field '{field_name}' is required")
                continue
            
            # Skip if not in form data (not required and not provided)
            if field_name not in form_data:
                continue
            
            value = form_data.get(field_name)
            
            # Type conversion
            if field_type == "number":
                try:
                    validated_data[field_name] = float(value)
                except (ValueError, TypeError):
                    errors.append(f"Field '{field_name}' must be a number")
            elif field_type == "boolean":
                # Handle various boolean representations
                if isinstance(value, bool):
                    validated_data[field_name] = value
                elif value in (True, "true", "True", "yes", "1", "on", 1):
                    validated_data[field_name] = True
                else:
                    validated_data[field_name] = False
            elif field_type == "dropdown":
                # Validate against options
                valid_option_values = [option.get("value", option.get("label", "")) for option in field_options]
                if value not in valid_option_values:
                    errors.append(f"Value '{value}' is not a valid option for field '{field_name}'")
                else:
                    validated_data[field_name] = value
            else:
                # Text, email, phone, etc. - keep as is
                validated_data[field_name] = value
        
        if errors:
            raise ValueError(", ".join(errors))
        
        return validated_data

    def is_bot_request(self, headers: Dict[str, str]) -> bool:
        """
        Check if the request is from a bot based on common bot user agents.
        """
        if "user-agent" not in headers:
            return False
            
        user_agent = headers["user-agent"].lower()
        bot_signatures = [
            "bot", "crawler", "spider", "slurp", "bingpreview", 
            "facebookexternalhit", "linkedinbot", "twitterbot"
        ]
        
        return any(sig in user_agent for sig in bot_signatures)

    def process_form_request(self, method: str, data: Dict[str, Any], files: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process form POST request and return appropriate response.
        Processes form data and returns response based on configuration.
        """
        # Get headers and query params
        headers = data.get("headers", {})
        query_params = data.get("query", {})
        
        # Check if should ignore bots
        options = self.get_node_parameter("options", 0, {})
        if options.get("ignoreBots", False) and self.is_bot_request(headers):
            return {
                "statusCode": 200,
                "body": "OK",
                "headers": {"Content-Type": "text/plain"}
            }
        
        # Check authentication if required
        auth_type = self.get_node_parameter("authentication", 0, "none")
        if auth_type == "basicAuth":
            auth_header = headers.get("authorization", "")
            if not auth_header or not auth_header.startswith("Basic "):
                return {
                    "statusCode": 401,
                    "body": {"error": "Unauthorized"},
                    "headers": {"Content-Type": "application/json", "WWW-Authenticate": "Basic"}
                }
            
            # Get credentials
            credentials = self.get_credentials("httpBasicAuth")
            if not credentials:
                return {
                    "statusCode": 500,
                    "body": {"error": "Authentication credentials not configured"},
                    "headers": {"Content-Type": "application/json"}
                }
            
            # Extract username and password from header
            try:
                auth_value = auth_header.split(" ")[1]
                decoded = base64.b64decode(auth_value).decode('utf-8')
                username, password = decoded.split(':', 1)
                
                # Compare with stored credentials
                if username != credentials.get("user") or password != credentials.get("password"):
                    return {
                        "statusCode": 401,
                        "body": {"error": "Unauthorized"},
                        "headers": {"Content-Type": "application/json", "WWW-Authenticate": "Basic"}
                    }
            except:
                return {
                    "statusCode": 401,
                    "body": {"error": "Unauthorized"},
                    "headers": {"Content-Type": "application/json", "WWW-Authenticate": "Basic"}
                }
        
        try:
            # Get form data
            form_data = data.get("body", {})
            
            # Validate form data
            validated_data = self.validate_form_data(form_data)
            
            # Process binary data (files) - using standard format and compression
            binary_data = {}
            if files:
                # Get MAX_UPLOAD_SIZE_MB from settings
                from config import get_settings
                settings = get_settings()
                max_upload_size_mb = getattr(settings, "MAX_UPLOAD_SIZE_MB", 10)
                
                for field_name, file_info in files.items():
                    # Check if this is a file field in the form
                    field_exists = False
                    for field in self.get_node_parameter("formFields", 0, []):
                        if field.get("fieldName") == field_name and field.get("fieldType") == "file":
                            field_exists = True
                            break
                        
                    if not field_exists:
                        continue
                    
                    # Check file size
                    file_data = file_info.get("data", "")
                    if isinstance(file_data, bytes):
                        file_size = len(file_data)
                    else:
                        file_size = len(file_data.encode() if isinstance(file_data, str) else b'')
                        
                    if file_size > max_upload_size_mb * 1024 * 1024:
                        return {
                            "statusCode": 413,
                            "body": {"error": f"File '{field_name}' exceeds maximum upload size of {max_upload_size_mb}MB"},
                            "headers": {"Content-Type": "application/json"}
                    }
                    
                    # Get file information
                    file_name = file_info.get("fileName", "unknown")
                    mime_type = file_info.get("mimeType", "application/octet-stream")
                    
                    # Convert file data to base64 string
                    if isinstance(file_data, bytes):
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                    elif isinstance(file_data, str):
                        # If already in base64 format
                        base64_data = file_data
                    else:
                        base64_data = ""
                    
                    # Use compress_data to properly store the binary data
                    compressed_data = self.compress_data(base64_data)
                    
                    # Store in standard binary format
                    binary_data[field_name] = {
                        "data": compressed_data,
                        "mimeType": mime_type,
                        "fileName": file_name,
                        "size": file_size
                    }
            
            # Create payload for workflow execution
            workflow_payload = {
                "form": validated_data,
                "query": query_params,
                "headers": headers,
                "meta": {
                    "workflow_id": getattr(self, "workflow_id", ""),
                    "node_id": getattr(self, "node_id", ""),
                    "source": "form_trigger",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "test_mode": False
                }
            }
            
            # Determine response based on responseMode
            response_mode = self.get_node_parameter("responseMode", 0, "onReceived")
            
            # Return execution data for trigger
            return {
                "json": workflow_payload,
                "binary": binary_data,
                "responseMode": response_mode
            }
            
        except ValueError as e:
            # Validation error
            return {
                "statusCode": 400,
                "body": {"error": str(e)},
                "headers": {"Content-Type": "application/json"}
            }
        except Exception as e:
            # Other errors
            logger.exception("Error processing form submission")
            return {
                "statusCode": 500,
                "body": {"error": f"Internal server error: {str(e)}"},
                "headers": {"Content-Type": "application/json"}
            }
    
    def get_form_response(self, success: bool = True, redirect_url: str = None) -> Dict[str, Any]:
        """
        Get response data based on configuration.
        """
        if redirect_url:
            return {
                "statusCode": 302,
                "headers": {"Location": redirect_url},
                "body": ""
            }
        
        # Default HTML success response
        html_response = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Form Submitted</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 2rem;
                    text-align: center;
                }
                .success-icon {
                    font-size: 4rem;
                    color: #4CAF50;
                    margin-bottom: 1rem;
                }
                h1 {
                    margin-bottom: 1rem;
                }
            </style>
        </head>
        <body>
            <div class="success-icon">✓</div>
            <h1>Thank you!</h1>
            <p>Your form has been submitted successfully.</p>
        </body>
        </html>
        """
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": html_response
        }
    

    def get_webhook_path(self) -> str:
        """Return the path for this webhook node"""
        return "form_trigger"
    
    def get_webhook_methods(self) -> list:
        """Return the HTTP methods the webhook accepts"""
        return ["POST"]

