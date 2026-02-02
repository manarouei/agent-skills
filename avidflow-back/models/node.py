from typing import Any, Dict, List, Optional, Union, Literal, Tuple
from pydantic import BaseModel, Field, RootModel, field_validator
from enum import Enum
import os


class NodeType(str, Enum):
    """Supported node types in workflow"""
    TRIGGER = "trigger"
    REGULAR = "regular"

# Base value types
NodeParameterValue = Union[str, int, float, bool, None]

# ResourceLocatorModes
ResourceLocatorModes = Union[Literal['id'], Literal['url'], Literal['list'], str]

class INodeParameterResourceLocator(BaseModel):
    __rl: Literal[True]
    mode: ResourceLocatorModes
    value: NodeParameterValue
    cachedResultName: Optional[str] = None
    cachedResultUrl: Optional[str] = None
    __regex: Optional[str] = None

class ResourceMapperField(BaseModel):
    id: str
    displayName: str
    defaultMatch: bool
    canBeUsedToMatch: Optional[bool] = None
    required: bool
    display: bool
    type: Optional[str] = None  # You can define a FieldType Enum later
    removed: Optional[bool] = None
    options: Optional[List[Dict[str, Any]]] = None  # Replace with proper INodePropertyOptions if defined
    readOnly: Optional[bool] = None

class ResourceMapperValue(BaseModel):
    mappingMode: str
    value: Optional[Dict[str, Union[str, int, float, bool, None]]]
    matchingColumns: List[str]
    schema: List[ResourceMapperField]
    attemptToConvertTypes: bool
    convertFieldsToString: bool

class FormFieldsParameterItem(BaseModel):
    fieldLabel: str
    elementName: Optional[str] = None
    fieldType: Optional[str] = None
    requiredField: Optional[bool] = None
    fieldOptions: Optional[Dict[str, List[Dict[str, str]]]] = None
    multiselect: Optional[bool] = None
    multipleFiles: Optional[bool] = None
    acceptFileTypes: Optional[str] = None
    formatDate: Optional[str] = None
    html: Optional[str] = None
    placeholder: Optional[str] = None
    fieldName: Optional[str] = None
    fieldValue: Optional[str] = None

FormFieldsParameter = List[FormFieldsParameterItem]

# Placeholder FieldTypeMap handling
FieldType = str  # Could be Literal[...list of field type keys...]

# Filter types
FilterOperatorType = str  # You can define more strict types if needed

class FilterOperatorValue(BaseModel):
    type: FilterOperatorType
    operation: str
    rightType: Optional[FilterOperatorType] = None
    singleValue: Optional[bool] = False

class FilterConditionValue(BaseModel):
    id: str
    leftValue: Union[NodeParameterValue, List[NodeParameterValue]]
    operator: FilterOperatorValue
    rightValue: Union[NodeParameterValue, List[NodeParameterValue]]

class FilterOptionsValue(BaseModel):
    caseSensitive: bool
    leftValue: str
    typeValidation: Literal['strict', 'loose']
    version: Literal[1, 2]

FilterTypeCombinator = Literal['and', 'or']

class FilterValue(BaseModel):
    options: FilterOptionsValue
    conditions: List[FilterConditionValue]
    combinator: FilterTypeCombinator

class AssignmentValue(BaseModel):
    id: str
    name: str
    value: NodeParameterValue
    type: Optional[str] = None

class AssignmentCollectionValue(BaseModel):
    assignments: List[AssignmentValue]

# NodeParameterValueType union
NodeParameterValueType = Union[
    NodeParameterValue,
    "NodeParameters",
    INodeParameterResourceLocator,
    ResourceMapperValue,
    FilterValue,
    AssignmentCollectionValue,
    List[NodeParameterValue],
    List["NodeParameters"],
    List[INodeParameterResourceLocator],
    List[ResourceMapperValue]
]

class NodeParameters(RootModel):
    root: Dict[str, NodeParameterValueType]


class NodeCredential(BaseModel):
    id: Optional[str] = None
    name: str


class Node(BaseModel):
    id: str = Field(..., description="Unique node identifier")
    name: str
    type: str
    position: Tuple[float, float]
    parameters: NodeParameters
    credentials: Optional[Dict[str, NodeCredential]] = None
    is_start: bool = False
    is_end: bool = False
    is_webhook: bool = False
    is_schedule: bool = False
    webhook_id: Optional[str] = Field(None, description="Webhook identifier")


class NodeExecutionData(BaseModel):
    json_data: Dict[str, Any]
    binary_data: Optional[Dict[str, Any]] = None


class DynamicNodeResponse(BaseModel):
    """Response model for dynamic nodes"""
    id: int
    type: str
    version: int
    name: str
    description: Dict[str, Any]
    properties: Dict[str, Any]
    is_active: bool
    category: Optional[str] = None  # Allow NULL from database
    icon: Optional[str] = None      # Allow NULL from database
    is_start: bool
    is_end: bool
    is_webhook: bool
    is_schedule: bool

    @field_validator('icon')
    def fix_icon_path(cls, v):
        """Convert absolute file paths to relative paths or handle Font Awesome icons"""
        if not v:
            return v
            
        # If it's a Font Awesome icon (fa:xxx)
        if isinstance(v, str) and v.startswith('fa:'):
            return v
            
        # Extract just the filename from the full path
        filename = os.path.basename(v) if v else ''
        return filename
    
    class Config:
        from_attributes = True

class DynamicNodeMetadataResponse(DynamicNodeResponse):
    """Extended response model for metadata queries with AI-specific fields"""
    ai_tool: bool = False
    ai_memory: bool = False  
    ai_model: bool = False

    class Config:
        # Ensure this model is only used for metadata, not serialization to workflows
        extra = "forbid"
