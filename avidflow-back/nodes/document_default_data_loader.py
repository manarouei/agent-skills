"""
Document Default Data Loader node for converting generic input data into LangChain Document format.

This node outputs ai_document type connections that can be consumed by:
- QdrantVectorStore (typed mode)
- Other vector store nodes
- Document processing pipelines

Architecture:
- Follows BaseNode pattern from base.py
- Outputs ai_document typed connection
- Converts generic JSON input into Document format {pageContent, metadata}
- Synchronous operation (compatible with Celery)

Document Format (LangChain compatible):
{
    "pageContent": "string",  # The actual text content
    "metadata": {             # Optional metadata
        "source": "...",
        "page": 1,
        "...": "..."
    }
}
"""
from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
import json
import logging

logger = logging.getLogger(__name__)


class DocumentDefaultDataLoaderNode(BaseNode):
    """
    Document Default Data Loader node for converting input data to Document format.
    
    This node takes generic JSON input and structures it into LangChain-compatible
    Document format with pageContent and metadata fields.
    """
    
    type = "documentDefaultDataLoader"
    version = 1.0
    
    description = {
        "displayName": "Default Data Loader",
        "name": "documentDefaultDataLoader",
        "icon": "file:binary.svg",
        "group": ["ai", "transform"],
        "description": "Load data from workflow input and convert to Document format",
        "defaults": {"name": "Default Data Loader"},
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "ai_document", "type": "ai_document", "required": True}
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "dataMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Data Mode",
                "description": "How to extract document content from input",
                "options": [
                    {
                        "name": "Auto-detect from common fields",
                        "value": "auto",
                        "description": "Automatically find text in common fields (text, content, body, message, etc.)"
                    },
                    {
                        "name": "Specify Text Field",
                        "value": "field",
                        "description": "Manually specify which field contains the text"
                    },
                    {
                        "name": "Use Entire JSON as Text",
                        "value": "json",
                        "description": "Convert entire JSON object to string"
                    }
                ],
                "default": "auto"
            },
            {
                "name": "textField",
                "type": NodeParameterType.STRING,
                "display_name": "Text Field",
                "description": "The field name containing the document text",
                "default": "text",
                "placeholder": "text",
                "displayOptions": {
                    "show": {
                        "dataMode": ["field"]
                    }
                }
            },
            {
                "name": "metadataMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Metadata Mode",
                "description": "How to handle metadata",
                "options": [
                    {
                        "name": "Include All Fields",
                        "value": "all",
                        "description": "Include all input fields as metadata (except text field)"
                    },
                    {
                        "name": "Specify Metadata Fields",
                        "value": "fields",
                        "description": "Manually specify which fields to include as metadata"
                    },
                    {
                        "name": "No Metadata",
                        "value": "none",
                        "description": "Don't include any metadata"
                    }
                ],
                "default": "all"
            },
            {
                "name": "metadataFields",
                "type": NodeParameterType.STRING,
                "display_name": "Metadata Fields",
                "description": "Comma-separated list of field names to include in metadata",
                "default": "",
                "placeholder": "source,page,author",
                "displayOptions": {
                    "show": {
                        "metadataMode": ["fields"]
                    }
                }
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "description": "Additional options for document loading",
                "default": {},
                "options": [
                    {
                        "name": "addSourceMetadata",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Add Source Metadata",
                        "description": "Automatically add source information to metadata",
                        "default": True
                    },
                    {
                        "name": "sourceField",
                        "type": NodeParameterType.STRING,
                        "display_name": "Source Field Name",
                        "description": "Field name to use for source metadata",
                        "default": "source",
                        "placeholder": "source"
                    },
                    {
                        "name": "splitLongText",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Split Long Text",
                        "description": "Split text longer than max length into multiple documents",
                        "default": False
                    },
                    {
                        "name": "maxTextLength",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Text Length",
                        "description": "Maximum length for a single document (characters)",
                        "default": 10000,
                        "typeOptions": {
                            "minValue": 100,
                            "maxValue": 1000000
                        }
                    },
                    {
                        "name": "chunkOverlap",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Chunk Overlap",
                        "description": "Number of characters to overlap between chunks",
                        "default": 200,
                        "typeOptions": {
                            "minValue": 0,
                            "maxValue": 1000
                        }
                    }
                ]
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the document loader node.
        
        Converts input data into LangChain Document format:
        {
            "pageContent": "text content",
            "metadata": {"key": "value", ...}
        }
        
        Returns:
            List[List[NodeExecutionData]]: Documents in ai_document format
        """
        try:
            # Get input data
            input_data = self.get_input_data()
            
            if not input_data:
                logger.warning("[Document Loader] No input data received")
                return [[]]
            
            results: List[NodeExecutionData] = []
            
            for item_index, item in enumerate(input_data):
                # Get parameters
                data_mode = self.get_node_parameter("dataMode", item_index, "auto")
                metadata_mode = self.get_node_parameter("metadataMode", item_index, "all")
                options = self.get_node_parameter("options", item_index, {}) or {}
                
                # Extract text content based on mode
                page_content = self._extract_text_content(
                    item.json_data,
                    data_mode,
                    item_index
                )
                
                if not page_content:
                    logger.warning(f"[Document Loader] Item {item_index}: No text content found, skipping")
                    continue
                
                # Extract metadata based on mode
                metadata = self._extract_metadata(
                    item.json_data,
                    metadata_mode,
                    item_index,
                    text_field=self._get_text_field_name(data_mode, item_index)
                )
                
                # Add source metadata if enabled
                if options.get("addSourceMetadata", True):
                    source_field = options.get("sourceField", "source")
                    if source_field not in metadata:
                        # Try to find source from common fields
                        for field in ["source", "url", "file", "path", "id"]:
                            if field in item.json_data:
                                metadata[source_field] = str(item.json_data[field])
                                break
                        else:
                            # Use item index as fallback source
                            metadata[source_field] = f"item_{item_index}"
                
                # Handle text splitting if enabled
                if options.get("splitLongText", False):
                    max_length = int(options.get("maxTextLength", 10000))
                    overlap = int(options.get("chunkOverlap", 200))
                    
                    if len(page_content) > max_length:
                        # Split into chunks
                        chunks = self._split_text(page_content, max_length, overlap)
                        logger.debug(f"[Document Loader] Item {item_index}: Split into {len(chunks)} chunks")
                        
                        for chunk_index, chunk in enumerate(chunks):
                            chunk_metadata = metadata.copy()
                            chunk_metadata["chunk"] = chunk_index
                            chunk_metadata["total_chunks"] = len(chunks)
                            
                            results.append(self._create_document_item(chunk, chunk_metadata))
                        continue
                
                # Create single document
                results.append(self._create_document_item(page_content, metadata))
            
            logger.info(f"[Document Loader] Processed {len(input_data)} input items → {len(results)} documents")
            return [results]
            
        except Exception as e:
            logger.error(f"[Document Loader] Error: {e}", exc_info=True)
            return [[NodeExecutionData(
                json_data={"error": f"Document Loader error: {str(e)}"},
                binary_data=None
            )]]
    
    def _extract_text_content(
        self,
        data: Dict[str, Any],
        mode: str,
        item_index: int
    ) -> str:
        """
        Extract text content from input data based on mode.
        
        Args:
            data: Input JSON data
            mode: Extraction mode (auto, field, json)
            item_index: Current item index
            
        Returns:
            str: Extracted text content
        """
        if mode == "json":
            # Convert entire JSON to string
            return json.dumps(data, ensure_ascii=False, indent=2)
        
        elif mode == "field":
            # Use specified field
            text_field = self.get_node_parameter("textField", item_index, "text")
            return str(data.get(text_field, ""))
        
        elif mode == "auto":
            # Auto-detect from common fields
            common_text_fields = [
                "text", "content", "body", "message", "description",
                "pageContent", "page_content", "data", "value",
                "article", "paragraph", "snippet", "excerpt"
            ]
            
            for field in common_text_fields:
                if field in data and data[field]:
                    value = data[field]
                    if isinstance(value, str):
                        return value
                    elif isinstance(value, (dict, list)):
                        return json.dumps(value, ensure_ascii=False)
                    else:
                        return str(value)
            
            # Fallback: use first string field found
            for key, value in data.items():
                if isinstance(value, str) and value.strip():
                    logger.debug(f"[Document Loader] Auto-detected text field: {key}")
                    return value
            
            # Last resort: convert entire JSON
            return json.dumps(data, ensure_ascii=False)
        
        return ""
    
    def _get_text_field_name(self, mode: str, item_index: int) -> Optional[str]:
        """Get the name of the field being used for text content."""
        if mode == "field":
            return self.get_node_parameter("textField", item_index, "text")
        return None
    
    def _extract_metadata(
        self,
        data: Dict[str, Any],
        mode: str,
        item_index: int,
        text_field: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract metadata from input data based on mode.
        
        Args:
            data: Input JSON data
            mode: Metadata mode (all, fields, none)
            item_index: Current item index
            text_field: Name of field used for text (to exclude from metadata)
            
        Returns:
            Dict[str, Any]: Metadata dictionary
        """
        if mode == "none":
            return {}
        
        elif mode == "fields":
            # Use specified fields only
            metadata_fields_str = self.get_node_parameter("metadataFields", item_index, "")
            if not metadata_fields_str:
                return {}
            
            metadata = {}
            field_names = [f.strip() for f in metadata_fields_str.split(",") if f.strip()]
            
            for field in field_names:
                if field in data:
                    metadata[field] = self._serialize_metadata_value(data[field])
            
            return metadata
        
        elif mode == "all":
            # Include all fields except text field
            metadata = {}
            
            for key, value in data.items():
                # Skip the text field
                if text_field and key == text_field:
                    continue
                
                # Skip very large values (likely not useful metadata)
                if isinstance(value, str) and len(value) > 1000:
                    continue
                
                metadata[key] = self._serialize_metadata_value(value)
            
            return metadata
        
        return {}
    
    def _serialize_metadata_value(self, value: Any) -> Any:
        """
        Serialize a metadata value to ensure it's JSON-compatible.
        
        Args:
            value: The value to serialize
            
        Returns:
            Any: JSON-compatible value
        """
        # Primitives pass through
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        
        # Lists and dicts: recursively serialize
        if isinstance(value, list):
            return [self._serialize_metadata_value(item) for item in value]
        
        if isinstance(value, dict):
            return {k: self._serialize_metadata_value(v) for k, v in value.items()}
        
        # Everything else: convert to string
        return str(value)
    
    def _create_document_item(
        self,
        page_content: str,
        metadata: Dict[str, Any]
    ) -> NodeExecutionData:
        """
        Create a NodeExecutionData item in Document format.
        
        Args:
            page_content: The document text content
            metadata: The document metadata
            
        Returns:
            NodeExecutionData: Item with ai_document structure
        """
        # LangChain Document format
        document = {
            "pageContent": page_content,
            "metadata": metadata
        }
        
        # Output data for ai_document typed connection
        # Both formats for maximum compatibility
        output_data = {
            "pageContent": page_content,
            "metadata": metadata,
            "document": document  # Wrapped format
        }
        
        return NodeExecutionData(
            json_data=output_data,
            binary_data=None
        )
    
    def _split_text(
        self,
        text: str,
        max_length: int,
        overlap: int
    ) -> List[str]:
        """
        Split text into chunks with overlap.
        
        This is a simple character-based splitter.
        For more sophisticated splitting, consider:
        - Sentence boundaries
        - Paragraph boundaries
        - Token-based splitting
        
        Args:
            text: Text to split
            max_length: Maximum characters per chunk
            overlap: Number of characters to overlap
            
        Returns:
            List[str]: Text chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_length
            
            # If not at the end, try to split at a space
            if end < len(text):
                # Look for last space in the chunk
                last_space = text[start:end].rfind(' ')
                if last_space > 0:
                    end = start + last_space
            
            chunks.append(text[start:end].strip())
            
            # Move start position (with overlap)
            start = end - overlap
            
            # Prevent infinite loop
            if start <= 0:
                start = end
        
        return chunks
    
    # ============================================================================
    # Alternative Loaders (for future expansion)
    # ============================================================================
    
    def _load_from_binary(self, binary_data: Dict[str, Any]) -> Optional[str]:
        """
        Load text from binary data (for future file support).
        
        TODO: Implement file parsing for:
        - PDF files
        - Word documents
        - Text files
        - HTML files
        - CSV/JSON files
        
        Args:
            binary_data: Binary data from NodeExecutionData
            
        Returns:
            Optional[str]: Extracted text or None
        """
        # TODO: Implement binary file parsing
        logger.warning("[Document Loader] Binary file loading not yet implemented")
        return None
    
    def _extract_from_html(self, html: str) -> str:
        """
        Extract text from HTML content.
        
        TODO: Implement HTML parsing with:
        - Tag stripping
        - Link extraction
        - Table parsing
        
        Args:
            html: HTML string
            
        Returns:
            str: Plain text content
        """
        # TODO: Implement HTML parsing (could use BeautifulSoup)
        # For now, just strip basic tags
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
