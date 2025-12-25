#!/usr/bin/env python3
"""
BaseNode Contract - Pydantic Models

Defines the schema for n8n BaseNode implementations.
All generated node schemas MUST conform to these models.

Source contract: BASENODE_CONTRACT.md
"""

from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


# NodeParameterType from base.py
NodeParameterType = Literal[
    "string", "number", "boolean", "options", "multiOptions",
    "color", "json", "collection", "dateTime", "node",
    "resourceLocator", "notice", "array", "code",
]


class ParameterOption(BaseModel):
    """Option for options/multiOptions parameter types."""
    name: str = Field(..., description="Display name for the option")
    value: str = Field(..., description="Value when option is selected")
    description: str | None = Field(None, description="Optional help text")


class DisplayOptions(BaseModel):
    """Conditional visibility for parameters."""
    show: dict[str, list[str]] | None = Field(None, description="Show when conditions met")
    hide: dict[str, list[str]] | None = Field(None, description="Hide when conditions met")


class NodeParameter(BaseModel):
    """
    A single parameter in the node's properties.
    
    Maps to properties["parameters"][n] in BaseNode.
    """
    name: str = Field(..., description="Parameter key (internal name)")
    displayName: str | None = Field(None, description="Human-readable label")
    type: NodeParameterType = Field(..., description="Parameter type")
    default: Any = Field(None, description="Default value")
    required: bool = Field(False, description="Is parameter required?")
    description: str | None = Field(None, description="Help text")
    displayOptions: DisplayOptions | None = Field(None, description="Conditional visibility")
    options: list[ParameterOption] | None = Field(None, description="Options for options/multiOptions type")
    
    @field_validator("options")
    @classmethod
    def validate_options(cls, v: list | None, info):
        """Options must be present for options/multiOptions types."""
        if info.data.get("type") in ("options", "multiOptions") and not v:
            # Allow None for now - might be dynamically loaded
            pass
        return v


class CredentialDefinition(BaseModel):
    """Credential requirement definition."""
    name: str = Field(..., description="Credential type name")
    required: bool = Field(True, description="Is credential required?")
    displayName: str | None = Field(None, description="Human-readable name")


class NodeInput(BaseModel):
    """Node input definition."""
    name: str = Field("main", description="Input name")
    type: str = Field("main", description="Input type")
    required: bool = Field(True, description="Is input required?")


class NodeOutput(BaseModel):
    """Node output definition."""
    name: str = Field("main", description="Output name")
    type: str = Field("main", description="Output type")


class NodeDefaults(BaseModel):
    """Default values for node instances."""
    name: str = Field(..., description="Default node instance name")
    color: str | None = Field(None, description="Hex color for UI")


class NodeDescription(BaseModel):
    """
    Node metadata - the description attribute of BaseNode.
    
    Contains display information and I/O definitions.
    """
    displayName: str = Field(..., description="Human-readable node name")
    name: str = Field(..., description="Internal name (lowercase, no spaces)")
    description: str | None = Field(None, description="Brief description")
    icon: str | None = Field(None, description="Icon: 'file:icon.png' or 'fa:icon-name'")
    group: list[str] = Field(default_factory=list, description="Categories: input, output, transform")
    version: int = Field(..., description="Node version (same as class version)")
    defaults: NodeDefaults | None = Field(None, description="Default values")
    inputs: list[str] | list[NodeInput] = Field(default_factory=lambda: ["main"])
    outputs: list[str] | list[NodeOutput] = Field(default_factory=lambda: ["main"])
    credentials: list[CredentialDefinition] | None = Field(None, description="Credential definitions")
    usableAsTool: bool = Field(False, description="Can be used as AI tool")


class NodeProperties(BaseModel):
    """
    Node configuration - the properties attribute of BaseNode.
    
    Contains parameters and credential definitions.
    """
    parameters: list[NodeParameter] = Field(default_factory=list, description="Node parameters")
    credentials: list[CredentialDefinition] | None = Field(None, description="Alternative credential location")


class BaseNodeSchema(BaseModel):
    """
    Complete BaseNode schema.
    
    This is what schema-build skill must produce.
    """
    type: str = Field(..., description="Unique node type identifier (e.g., 'n8n-nodes-base.telegram')")
    version: int = Field(..., description="Node version number (start at 1)", ge=1)
    description: NodeDescription = Field(..., description="Node metadata")
    properties: NodeProperties = Field(..., description="Node configuration")
    
    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """Type should follow n8n naming convention."""
        # Allow flexible naming but warn if not standard
        if "." not in v:
            # Just the node name - that's fine for our purposes
            pass
        return v
    
    def validate_contract_compliance(self) -> list[str]:
        """
        Check for contract violations.
        
        Returns list of error messages (empty if valid).
        """
        errors = []
        
        # Check required attributes
        if not self.type:
            errors.append("Missing required attribute: type")
        if self.version < 1:
            errors.append("Version must be >= 1")
        
        # Check description
        if not self.description.displayName:
            errors.append("description.displayName is required")
        if not self.description.name:
            errors.append("description.name is required")
        
        # Check parameters have names
        for i, param in enumerate(self.properties.parameters):
            if not param.name:
                errors.append(f"Parameter {i} missing name")
            if not param.type:
                errors.append(f"Parameter '{param.name}' missing type")
        
        # Check options parameters have options
        for param in self.properties.parameters:
            if param.type in ("options", "multiOptions"):
                if not param.options:
                    errors.append(f"Parameter '{param.name}' is type '{param.type}' but has no options")
        
        return errors


class SchemaValidationResult(BaseModel):
    """Result of BaseNode schema validation."""
    valid: bool = Field(..., description="Whether schema is valid")
    errors: list[str] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking warnings")
    schema_summary: dict[str, Any] = Field(default_factory=dict, description="Summary of validated schema")


def validate_basenode_schema(data: dict) -> SchemaValidationResult:
    """
    Validate a dictionary against the BaseNode schema.
    
    Args:
        data: Dictionary to validate
        
    Returns:
        SchemaValidationResult with validation outcome
    """
    errors = []
    warnings = []
    
    try:
        schema = BaseNodeSchema.model_validate(data)
        contract_errors = schema.validate_contract_compliance()
        errors.extend(contract_errors)
        
        summary = {
            "type": schema.type,
            "version": schema.version,
            "displayName": schema.description.displayName,
            "parameter_count": len(schema.properties.parameters),
            "has_credentials": bool(schema.description.credentials or schema.properties.credentials),
        }
        
    except Exception as e:
        errors.append(f"Schema validation failed: {e}")
        summary = {}
    
    return SchemaValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        schema_summary=summary,
    )
