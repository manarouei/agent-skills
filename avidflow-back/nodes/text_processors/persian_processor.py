"""
Persian text processor node for legal document analysis.

Normalizes Persian/Arabic text, extracts legal references (articles,
subsections, paragraphs), and parses Jalali dates.
"""
from typing import Dict, List, Any
import logging

from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
from utils.persian_text import (
    normalize_persian_text,
    convert_persian_digits,
    extract_dates,
    extract_articles,
    extract_subsections,
    extract_paragraphs
)

logger = logging.getLogger(__name__)

class PersianTextProcessorNode(BaseNode):
    """
    Persian text processor for legal document analysis.
    
    Provides comprehensive Persian text processing capabilities:
    - Character normalization (Arabic ي/ك → Persian ی/ک)
    - Digit conversion (Persian ۰-۹ → ASCII 0-9)
    - Legal reference extraction (articles, subsections, paragraphs)
    - Jalali date parsing
    
    Designed for Iranian tax law Q&A systems but applicable to any
    Persian legal document processing.
    """
    
    type = "persianTextProcessor"
    version = 1
    
    description = {
        "displayName": "Persian Text Processor",
        "name": "persianTextProcessor",
        "icon": "fa:language",
        "group": ["transform"],
        "description": "Process Persian text: normalize, extract legal references and dates",
        "defaults": {"name": "Persian Text Processor"},
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}]
    }
    
    properties = {
        "parameters": [
            {
                "name": "inputField",
                "type": NodeParameterType.STRING,
                "display_name": "Input Field",
                "default": "chatInput",
                "required": True,
                "description": "Field containing text to process",
                "placeholder": "chatInput"
            },
            {
                "name": "operations",
                "type": NodeParameterType.MULTI_OPTIONS,
                "display_name": "Operations",
                "options": [
                    {
                        "name": "Normalize Characters",
                        "value": "normalize",
                        "description": "Convert Arabic ي/ك to Persian ی/ک"
                    },
                    {
                        "name": "Convert Digits",
                        "value": "digits",
                        "description": "Convert Persian digits (۰-۹) to ASCII (0-9)"
                    },
                    {
                        "name": "Extract Dates",
                        "value": "dates",
                        "description": "Extract Jalali dates (years)"
                    },
                    {
                        "name": "Extract Articles",
                        "value": "articles",
                        "description": "Extract article numbers (ماده)"
                    },
                    {
                        "name": "Extract Subsections",
                        "value": "subsections",
                        "description": "Extract subsection numbers (تبصره)"
                    },
                    {
                        "name": "Extract Paragraphs",
                        "value": "paragraphs",
                        "description": "Extract paragraph identifiers (بند)"
                    }
                ],
                "default": ["normalize", "digits", "dates", "articles", "subsections", "paragraphs"],
                "description": "Text processing operations to perform"
            },
            {
                "name": "outputField",
                "type": NodeParameterType.STRING,
                "display_name": "Output Field",
                "default": "chatInput",
                "description": "Field name for processed text (overwrites input if same)",
                "placeholder": "chatInput"
            },
            {
                "name": "preserveOriginal",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Preserve Original Text",
                "default": False,
                "description": "Store original text in 'originalText' field"
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Persian text processing"""
        try:
            input_data = self.get_input_data()
            
            # Handle empty input data case
            if not input_data:
                return [[]]
            
            results = []
            
            for i, item in enumerate(input_data):
                try:
                    # Get parameters
                    input_field = self.get_node_parameter("inputField", i, "chatInput")
                    operations = self.get_node_parameter("operations", i, [])
                    output_field = self.get_node_parameter("outputField", i, "chatInput")
                    preserve_original = self.get_node_parameter("preserveOriginal", i, False)
                    
                    # Get input text
                    text = item.json_data.get(input_field, "")
                    if not isinstance(text, str):
                        text = str(text)
                    
                    original_text = text
                    output_data = item.json_data.copy()
                    
                    # Preserve original if requested
                    if preserve_original:
                        output_data["originalText"] = original_text
                    
                    # Apply normalization operations in order
                    if "normalize" in operations:
                        text = normalize_persian_text(text)
                        logger.debug(
                            f"[PersianProcessor] Item {i}: Normalized "
                            f"'{original_text[:30]}...' → '{text[:30]}...'"
                        )
                    
                    if "digits" in operations:
                        text = convert_persian_digits(text)
                    
                    # Store processed text
                    output_data[output_field] = text
                    
                    # Extract structured data
                    if "dates" in operations:
                        date_info = extract_dates(text)
                        output_data["target_year"] = date_info["target_year"]
                        output_data["years"] = date_info["years"]
                        if date_info["years"]:
                            logger.debug(
                                f"[PersianProcessor] Item {i}: Extracted years: {date_info['years']}"
                            )
                    
                    if "articles" in operations:
                        articles = extract_articles(text)
                        output_data["articles"] = articles
                        if articles:
                            logger.debug(
                                f"[PersianProcessor] Item {i}: Extracted articles: {articles}"
                            )
                    
                    if "subsections" in operations:
                        subsections = extract_subsections(text)
                        output_data["subsections"] = subsections
                        if subsections:
                            logger.debug(
                                f"[PersianProcessor] Item {i}: Extracted subsections: {subsections}"
                            )
                    
                    if "paragraphs" in operations:
                        paragraphs = extract_paragraphs(text)
                        output_data["paragraphs"] = paragraphs
                        if paragraphs:
                            logger.debug(
                                f"[PersianProcessor] Item {i}: Extracted paragraphs: {paragraphs}"
                            )
                    
                    results.append(NodeExecutionData(json_data=output_data))
                    
                except Exception as e:
                    logger.error(f"[PersianProcessor] Error processing item {i}: {e}", exc_info=True)
                    # Return original data on error
                    results.append(item)
            
            logger.info(f"[PersianProcessor] Processed {len(results)} items successfully")
            return [results]  # Single output
            
        except Exception as e:
            logger.error(f"[PersianProcessor] Execute error: {e}", exc_info=True)
            return [[]]
