from typing import Dict, Any, List, Optional, Union
import logging
import requests
import base64
from bs4 import BeautifulSoup, Tag, NavigableString
import re
import json
import traceback

from .base import BaseNode, NodeParameterType
from models import NodeExecutionData

logger = logging.getLogger(__name__)


class HtmlExtractorNode(BaseNode):
    """
    HTML Extractor Node - Extracts data from HTML using CSS selectors and XPath
    Converts the n8n HtmlExtract functionality to Python backend
    """
    
    type = "htmlExtractor"
    version = 1
    description = {
        "displayName": "HTML Extract",
        "name": "htmlExtractor", 
        "icon": "fa:cut",
        "group": ["transform"],
        "subtitle": "={{$parameter['sourceData'] + ': ' + $parameter['dataPropertyName']}}",
        "description": "Extracts data from HTML using CSS selectors",
        "defaults": {
            "name": "HTML Extract",
            "color": "#333377"
        },
        "inputs": ["main"],
        "outputs": ["main"]
    }
    
    properties = {
        "parameters": [
            {
                "name": "sourceData",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Source Data",
                "required": True,
                "options": [
                    {"name": "Binary", "value": "binary"},
                    {"name": "JSON", "value": "json"}
                ],
                "default": "json",
                "description": "If HTML should be read from binary or JSON data"
            },
            {
                "name": "binaryPropertyName", 
                "type": NodeParameterType.STRING,
                "display_name": "Input Binary Field",
                "default": "data",
                "required": True,
                "display_options": {
                    "show": {
                        "sourceData": ["binary"]
                    }
                },
                "description": "Name of the binary property from which to read the HTML"
            },
            {
                "name": "dataPropertyName",
                "type": NodeParameterType.STRING, 
                "display_name": "JSON Property",
                "default": "data",
                "required": True,
                "display_options": {
                    "show": {
                        "sourceData": ["json"]
                    }
                },
                "description": "Name of the JSON property from which to read the HTML. Use dot notation for nested properties."
            },
            {
                "name": "extractionValues",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Extraction Values",
                "default": {},
                "placeholder": "Add Value",
                "options": [
                    {
                        "name": "key",
                        "type": NodeParameterType.STRING,
                        "display_name": "Key",
                        "default": "",
                        "description": "Key under which the extracted value should be saved"
                    },
                    {
                        "name": "cssSelector", 
                        "type": NodeParameterType.STRING,
                        "display_name": "CSS Selector",
                        "default": "",
                        "placeholder": "body > p",
                        "description": "CSS selector to use for extraction"
                    },
                    {
                        "name": "returnValue",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Return Value",
                        "options": [
                            {"name": "Attribute", "value": "attribute"},
                            {"name": "HTML", "value": "html"},
                            {"name": "Text", "value": "text"},
                            {"name": "Value", "value": "value"}
                        ],
                        "default": "text",
                        "description": "What kind of data should be returned"
                    },
                    {
                        "name": "attribute",
                        "type": NodeParameterType.STRING,
                        "display_name": "Attribute",
                        "default": "",
                        "placeholder": "class",
                        "display_options": {
                            "show": {
                                "returnValue": ["attribute"]
                            }
                        },
                        "description": "Name of the attribute to return the value off"
                    },
                    {
                        "name": "returnArray",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Return Array",
                        "default": False,
                        "description": "If multiple matches should be returned as an array"
                    }
                ],
                "typeOptions": {
                    "multipleValues": True
                }
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "placeholder": "Add Option",
                "options": [
                    {
                        "name": "trimValues",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Trim Values",
                        "default": True,
                        "description": "Whether to remove automatically all spaces and newlines from the beginning and end of the values"
                    }
                ]
            }
        ],
        "credentials": []
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.extraction_functions = {
            'attribute': self._extract_attribute,
            'html': self._extract_html,
            'text': self._extract_text,
            'value': self._extract_value
        }

    def _extract_attribute(self, element: Tag, attribute: str = None) -> Optional[str]:
        """Extract attribute value from element"""
        if not isinstance(element, Tag) or not attribute:
            return None
        return element.get(attribute)

    def _extract_html(self, element: Tag, attribute: str = None) -> Optional[str]:
        """Extract inner HTML from element"""
        if not isinstance(element, Tag):
            return None
        return str(element.decode_contents())

    def _extract_text(self, element: Tag, attribute: str = None) -> Optional[str]:
        """Extract text content from element"""
        if isinstance(element, Tag):
            return element.get_text()
        elif isinstance(element, NavigableString):
            return str(element)
        return None

    def _extract_value(self, element: Tag, attribute: str = None) -> Optional[str]:
        """Extract value attribute from element (for form elements)"""
        if not isinstance(element, Tag):
            return None
        return element.get('value')

    def _get_html_content(self, item: NodeExecutionData, item_index: int) -> List[str]:
        """
        Get HTML content from item based on sourceData parameter
        Returns list of HTML strings to process
        """
        source_data = self.get_node_parameter("sourceData", item_index, "json")
        
        if source_data == "binary":
            # Get from binary data
            binary_property = self.get_node_parameter("binaryPropertyName", item_index, "data")
            
            if not hasattr(item, 'binary_data') or not item.binary_data:
                raise ValueError(f"No binary data found in item {item_index}")
                
            if binary_property not in item.binary_data:
                raise ValueError(f"Binary property '{binary_property}' not found in item {item_index}")
                
            binary_info = item.binary_data[binary_property]
            
            # Handle different binary data formats
            if isinstance(binary_info, dict):
                if 'data' in binary_info:
                    # Base64 encoded data
                    try:
                        html_content = base64.b64decode(binary_info['data']).decode('utf-8')
                    except Exception as e:
                        raise ValueError(f"Failed to decode binary data: {str(e)}")
                elif 'buffer' in binary_info:
                    # Raw buffer data
                    html_content = binary_info['buffer'].decode('utf-8')
                else:
                    raise ValueError("Binary data format not supported")
            else:
                # Direct string data
                html_content = str(binary_info)
                
        else:  # source_data == "json"
            # Get from JSON data
            data_property = self.get_node_parameter("dataPropertyName", item_index, "data")
            
            if not hasattr(item, 'json_data') or not item.json_data:
                raise ValueError(f"No JSON data found in item {item_index}")
            
            # Support dot notation for nested properties
            html_content = self._get_nested_property(item.json_data, data_property)
            
            if html_content is None:
                raise ValueError(f"JSON property '{data_property}' not found in item {item_index}")
                
        # Convert to list if single string
        if isinstance(html_content, str):
            return [html_content]
        elif isinstance(html_content, list):
            return [str(content) for content in html_content]
        else:
            return [str(html_content)]

    def _get_nested_property(self, data: Dict[str, Any], property_path: str) -> Any:
        """
        Get nested property using dot notation
        Examples: 'data', 'response.body', 'items.0.content'
        """
        if not property_path:
            return None
            
        keys = property_path.split('.')
        current = data
        
        for key in keys:
            try:
                if key.isdigit():
                    # Array index
                    index = int(key)
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        return None
                else:
                    # Dictionary key
                    if isinstance(current, dict) and key in current:
                        current = current[key]
                    else:
                        return None
            except (ValueError, TypeError, KeyError):
                return None
                
        return current

    def _extract_values_from_html(self, html: str, item_index: int) -> Dict[str, Any]:
        """
        Extract values from HTML using configured extraction rules
        """
        try:
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Get extraction configuration
            extraction_values = self.get_node_parameter("extractionValues", item_index, {})
            options = self.get_node_parameter("options", item_index, {})
            
            # Convert extraction values to list if needed
            if isinstance(extraction_values, dict):
                if 'values' in extraction_values:
                    extraction_list = extraction_values['values']
                else:
                    # Single extraction rule
                    extraction_list = [extraction_values] if extraction_values else []
            elif isinstance(extraction_values, list):
                extraction_list = extraction_values
            else:
                extraction_list = []
                
            logger.info(f"HTML Extract - Processing {len(extraction_list)} extraction rules")
            
            extracted_data = {}
            
            for extraction_rule in extraction_list:
                if not isinstance(extraction_rule, dict):
                    continue
                    
                key = extraction_rule.get('key', '')
                css_selector = extraction_rule.get('cssSelector', '')
                return_value = extraction_rule.get('returnValue', 'text')
                attribute = extraction_rule.get('attribute', '')
                return_array = extraction_rule.get('returnArray', False)
                
                if not key or not css_selector:
                    logger.warning(f"HTML Extract - Skipping rule: missing key or cssSelector")
                    continue
                    
                logger.info(f"HTML Extract - Extracting '{key}' using selector '{css_selector}'")
                
                try:
                    # Find elements using CSS selector
                    elements = soup.select(css_selector)
                    logger.info(f"HTML Extract - Found {len(elements)} elements for selector '{css_selector}'")
                    
                    if not elements:
                        extracted_data[key] = [] if return_array else None
                        continue
                    
                    # Extract values from elements
                    extract_func = self.extraction_functions.get(return_value, self._extract_text)
                    values = []
                    
                    for element in elements:
                        value = extract_func(element, attribute)
                        
                        if value is not None:
                            # Apply trimming if enabled
                            if options.get('trimValues', True) and isinstance(value, str):
                                value = value.strip()
                            values.append(value)
                    
                    # Return array or single value based on configuration
                    if return_array:
                        extracted_data[key] = values
                    else:
                        extracted_data[key] = values[0] if values else None
                        
                    logger.info(f"HTML Extract - Extracted {len(values)} values for key '{key}'")
                    
                except Exception as e:
                    logger.error(f"HTML Extract - Error extracting '{key}': {str(e)}")
                    extracted_data[key] = [] if return_array else None
                    
            return extracted_data
            
        except Exception as e:
            logger.error(f"HTML Extract - Error parsing HTML: {str(e)}")
            raise ValueError(f"Failed to parse HTML content: {str(e)}")

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute HTML extraction
        """
        try:
            logger.info("HTML Extract - Starting execution")
            
            input_data = self.get_input_data()
            
            if not input_data:
                logger.warning("HTML Extract - No input data received")
                return [[]]
            
            output_items = []
            
            for item_index, item in enumerate(input_data):
                try:
                    logger.info(f"HTML Extract - Processing item {item_index}")
                    
                    # Get HTML content from item
                    html_list = self._get_html_content(item, item_index)
                    
                    # Process each HTML content
                    for html_content in html_list:
                        if not html_content or not html_content.strip():
                            logger.warning(f"HTML Extract - Empty HTML content in item {item_index}")
                            continue
                            
                        logger.info(f"HTML Extract - Processing HTML content ({len(html_content)} chars)")
                        
                        # Extract values from HTML
                        extracted_data = self._extract_values_from_html(html_content, item_index)
                        
                        # Create new output item
                        new_item = NodeExecutionData(
                            json_data=extracted_data,
                            binary_data={},
                            paired_item={
                                "item": item_index
                            }
                        )
                        
                        output_items.append(new_item)
                        logger.info(f"HTML Extract - Extracted {len(extracted_data)} fields from HTML")
                        
                except Exception as e:
                    logger.error(f"HTML Extract - Error processing item {item_index}: {str(e)}")
                    traceback.print_exc()
                    
                    # Create error item
                    error_item = NodeExecutionData(
                        json_data={
                            "error": f"HTML extraction failed: {str(e)}",
                            "item_index": item_index
                        },
                        binary_data={},
                        paired_item={
                            "item": item_index
                        }
                    )
                    output_items.append(error_item)
            
            logger.info(f"HTML Extract - Completed processing {len(output_items)} output items")
            return [output_items]
            
        except Exception as e:
            logger.error(f"HTML Extract - Execution failed: {str(e)}")
            traceback.print_exc()
            
            # Return error result
            error_item = NodeExecutionData(
                json_data={
                    "error": f"HTML extraction execution failed: {str(e)}",
                    "node_error": True
                },
                binary_data={}
            )
            return [[error_item]]

    def _validate_css_selector(self, selector: str) -> bool:
        """
        Validate CSS selector syntax
        """
        if not selector or not selector.strip():
            return False
            
        try:
            # Test with empty soup to validate syntax
            soup = BeautifulSoup("<html></html>", 'html.parser')
            soup.select(selector)
            return True
        except Exception:
            return False

    def _sanitize_html(self, html: str) -> str:
        """
        Basic HTML sanitization to prevent issues
        """
        if not html:
            return ""
            
        # Remove script and style tags
        soup = BeautifulSoup(html, 'html.parser')
        
        # Remove dangerous tags
        for tag in soup(["script", "style"]):
            tag.decompose()
            
        return str(soup)

    def _handle_extraction_errors(self, error: Exception, key: str, item_index: int) -> Any:
        """
        Handle extraction errors gracefully
        """
        logger.error(f"HTML Extract - Extraction error for key '{key}' in item {item_index}: {str(error)}")
        
        # Check if node should continue on fail
        if hasattr(self.node_data, 'continue_on_fail') and self.node_data.continue_on_fail:
            return None
        else:
            raise error

    def get_test_data(self) -> Dict[str, Any]:
        """
        Get test data for node testing
        """
        return {
            "input": [
                NodeExecutionData(
                    json_data={
                        "html": """
                        <html>
                            <head><title>Test Page</title></head>
                            <body>
                                <h1 class="main-title">Welcome</h1>
                                <p class="content">This is test content.</p>
                                <div class="items">
                                    <span class="item" data-id="1">Item 1</span>
                                    <span class="item" data-id="2">Item 2</span>
                                </div>
                                <input type="text" value="test input" name="test_input">
                            </body>
                        </html>
                        """
                    },
                    binary_data={}
                )
            ],
            "parameters": {
                "sourceData": "json",
                "dataPropertyName": "html",
                "extractionValues": {
                    "values": [
                        {
                            "key": "title",
                            "cssSelector": "title",
                            "returnValue": "text",
                            "returnArray": False
                        },
                        {
                            "key": "heading",
                            "cssSelector": "h1.main-title", 
                            "returnValue": "text",
                            "returnArray": False
                        },
                        {
                            "key": "items",
                            "cssSelector": ".item",
                            "returnValue": "text",
                            "returnArray": True
                        },
                        {
                            "key": "item_ids",
                            "cssSelector": ".item",
                            "returnValue": "attribute",
                            "attribute": "data-id",
                            "returnArray": True
                        }
                    ]
                },
                "options": {
                    "trimValues": True
                }
            },
            "expected_output": {
                "title": "Test Page",
                "heading": "Welcome", 
                "items": ["Item 1", "Item 2"],
                "item_ids": ["1", "2"]
            }
        }