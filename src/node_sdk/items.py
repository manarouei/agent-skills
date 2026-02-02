"""
Node Items - Data structures flowing through workflows.

NodeItem is the fundamental data unit in workflows.
Each item has JSON data and optional binary attachments.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class BinaryData(BaseModel):
    """
    Binary attachment for a node item.
    
    Binary data is stored separately and referenced by key.
    """
    model_config = ConfigDict(extra="forbid")
    
    data: bytes = Field(..., description="Raw binary data")
    mime_type: str = Field("application/octet-stream", description="MIME type")
    file_name: Optional[str] = Field(None, description="Original filename")
    file_extension: Optional[str] = Field(None, description="File extension")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    
    @property
    def size(self) -> int:
        """Get size of binary data."""
        return len(self.data)


class PairedItem(BaseModel):
    """
    Reference to the source item that produced this item.
    
    Used for tracking data lineage through workflows.
    """
    model_config = ConfigDict(extra="forbid")
    
    item: int = Field(..., description="Index of source item", ge=0)
    input: int = Field(0, description="Input branch index", ge=0)


class NodeItem(BaseModel):
    """
    A single data item flowing through a workflow.
    
    Each item has:
    - json_data: The main JSON data (dict)
    - binary: Optional binary attachments keyed by name
    - paired_item: Optional reference to source item
    
    Example:
        item = NodeItem(json_data={"name": "John", "email": "john@example.com"})
        item = NodeItem(
            json_data={"file": "image.png"},
            binary={"data": BinaryData(data=b"...", mime_type="image/png")}
        )
    """
    model_config = ConfigDict(extra="forbid")
    
    json_data: Dict[str, Any] = Field(default_factory=dict, description="JSON data")
    binary: Dict[str, BinaryData] = Field(
        default_factory=dict, 
        description="Binary attachments keyed by name"
    )
    paired_item: Optional[PairedItem] = Field(
        None,
        description="Reference to source item"
    )
    
    # Alias for backward compatibility
    @property
    def json(self) -> Dict[str, Any]:
        """Alias for json_data (backward compatibility)."""
        return self.json_data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeItem":
        """Create NodeItem from a simple dict."""
        return cls(json_data=data)
    
    @classmethod
    def from_list(cls, items: List[Dict[str, Any]]) -> List["NodeItem"]:
        """Create list of NodeItems from list of dicts."""
        return [cls.from_dict(item) for item in items]
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get value from JSON data."""
        return self.json_data.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get value from JSON data."""
        return self.json_data[key]
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in JSON data."""
        return key in self.json_data


class NodeItemList(BaseModel):
    """
    A list of node items, typically representing one output branch.
    
    Nodes return List[List[NodeItem]] where:
    - Outer list = output branches
    - Inner list = items in that branch
    """
    model_config = ConfigDict(extra="forbid")
    
    items: List[NodeItem] = Field(default_factory=list)
    
    def __len__(self) -> int:
        return len(self.items)
    
    def __iter__(self):
        return iter(self.items)
    
    def __getitem__(self, index: int) -> NodeItem:
        return self.items[index]
    
    def append(self, item: NodeItem) -> None:
        self.items.append(item)
    
    def extend(self, items: List[NodeItem]) -> None:
        self.items.extend(items)
