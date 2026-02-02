"""
Base credential class that all credential types should inherit from.
"""
from typing import Dict, List, Any, Optional, ClassVar


class BaseCredential:
    """Base class for all credential types"""
    
    # Class variables to be overridden by subclasses
    name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    properties: ClassVar[List[Dict[str, Any]]] = []
    
    def __init__(self, data: Dict[str, Any], client_id: str = None):
        """
        Initialize with credential data
        
        Args:
            data: Dictionary containing credential values
            client_id: Optional client identifier
        """
        self.data = data
        self.client_id = client_id

    @classmethod
    def get_definition(cls) -> Dict[str, Any]:
        """Get the credential type definition for database storage"""
        return {
            "name": cls.name,
            "display_name": cls.display_name,
            "properties": cls.properties,
        }
    
    def test(self) -> Dict[str, Any]:
        """
        Test if the credential is valid
        
        Returns:
            Dictionary with test results (success, message)
        """
        raise NotImplementedError("Test method not implemented")
    
    def validate(self) -> Dict[str, Any]:
        """
        Validate that all required properties are provided
        
        Returns:
            Dictionary with validation results
        """
        missing_fields = []
        
        for prop in self.properties:
            if prop.get("required", False) and not self.data.get(prop["name"]):
                missing_fields.append(prop["name"])
                
        if missing_fields:
            return {
                "valid": False,
                "message": f"Missing required fields: {', '.join(missing_fields)}"
            }
            
        return {"valid": True}
