"""
Credential Convert Skill Implementation

Converts n8n TypeScript credential definitions to Python credential types.
HYBRID EXECUTION: Deterministic TS parsing + KB pattern matching.
SYNC-CELERY SAFE: No async patterns.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

from runtime.protocol import AgentResponse, TaskState


# =============================================================================
# CREDENTIAL TEMPLATES (Based on Golden Patterns)
# =============================================================================

BASE_CREDENTIAL_TEMPLATE = Template('''"""
${display_name} credential for ${description}.
"""
from typing import Dict, Any
from .base import BaseCredential


class ${class_name}(BaseCredential):
    """${display_name} credential implementation"""
    
    name = "${credential_name}"
    display_name = "${display_name}"
    properties = ${properties_array}
    
    def test(self) -> Dict[str, Any]:
        """
        Test the ${display_name} credential
        
        Returns:
            Dictionary with test results
        """
        # Validate required fields first
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
${test_body}
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing ${display_name} credential: {str(e)}"
            }
''')


API_KEY_TEST_BODY = Template('''            # Test API key by making a simple API call
            import requests
            
            api_key = self.data.get("${key_field}", "")
            headers = {
                "${header_name}": "${header_prefix}${key_format}"
            }
            
            url = "${test_url}"
            
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return {
                        "success": True,
                        "message": "Successfully connected to ${display_name} API"
                    }
                elif response.status_code == 401:
                    return {
                        "success": False,
                        "message": "Authentication failed. Please check your API key."
                    }
                else:
                    return {
                        "success": False,
                        "message": f"API error (status {response.status_code}): {response.text}"
                    }
            except requests.exceptions.Timeout:
                return {
                    "success": False,
                    "message": "Request timeout - API may be unavailable"
                }
            except requests.exceptions.RequestException as e:
                return {
                    "success": False,
                    "message": f"Request error: {str(e)}"
                }
''')


OAUTH2_EXTENDS_TEMPLATE = Template('''"""
${display_name} OAuth2 credential - extends base OAuth2
"""
from typing import Dict, Any, List, ClassVar
from .oAuth2Api import OAuth2ApiCredential


class ${class_name}(OAuth2ApiCredential):
    """${display_name} OAuth2 credential that extends OAuth2"""
    
    name = "${credential_name}"
    display_name = "${display_name}"
    
    # Service-specific scopes
    ${scope_constants}

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        modified_props = []

        for prop in parent_props:
            prop_copy = prop.copy()
            
            # Override scope to be hidden with default value
            if prop_copy["name"] == "scope":
                prop_copy.update({
                    "type": "hidden",
                    "default": "${default_scope}"
                })
            
            ${property_modifications}
            
            modified_props.append(prop_copy)
        
        return modified_props

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
''')


# =============================================================================
# TS CREDENTIAL PARSER
# =============================================================================

class TSCredentialParser:
    """Parse TypeScript credential definitions."""
    
    def __init__(self, ts_content: str, credential_name: str):
        self.ts_content = ts_content
        self.credential_name = credential_name
        self.class_name = None
        self.display_name = None
        self.properties = []
        self.extends = None
        self.doc_url = None
        
    def parse(self) -> Dict[str, Any]:
        """Parse TS credential file and extract metadata."""
        # Extract class name
        class_match = re.search(r'export\s+class\s+(\w+)\s+implements\s+ICredentialType', self.ts_content)
        if class_match:
            self.class_name = class_match.group(1)
        
        # Extract name property
        name_match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", self.ts_content)
        if name_match:
            parsed_name = name_match.group(1)
            # Validate it matches expected name
            if parsed_name != self.credential_name:
                # Log warning but continue
                pass
        
        # Extract displayName
        display_match = re.search(r"displayName\s*=\s*['\"]([^'\"]+)['\"]", self.ts_content)
        if display_match:
            self.display_name = display_match.group(1)
        
        # Extract extends (for OAuth2 credentials)
        extends_match = re.search(r"extends\s*=\s*\[['\"]([^'\"]+)['\"]\]", self.ts_content)
        if extends_match:
            self.extends = extends_match.group(1)
        
        # Extract documentationUrl
        doc_match = re.search(r"documentationUrl\s*=\s*['\"]([^'\"]+)['\"]", self.ts_content)
        if doc_match:
            self.doc_url = doc_match.group(1)
        
        # Extract properties array
        self._parse_properties()
        
        return {
            "class_name": self.class_name,
            "display_name": self.display_name or self.credential_name,
            "properties": self.properties,
            "extends": self.extends,
            "doc_url": self.doc_url,
        }
    
    def _parse_properties(self):
        """Extract properties array from TS."""
        # Find properties: INodeProperties[] = [...]
        prop_pattern = r"properties:\s*INodeProperties\[\]\s*=\s*\[(.*?)\];"
        match = re.search(prop_pattern, self.ts_content, re.DOTALL)
        
        if not match:
            return
        
        props_content = match.group(1)
        
        # Split by object boundaries (simple heuristic)
        # Look for patterns like: { displayName: ..., name: ..., type: ... },
        prop_objects = re.finditer(r'\{([^}]+)\}', props_content)
        
        for prop_match in prop_objects:
            prop_text = prop_match.group(1)
            prop_data = self._parse_property_object(prop_text)
            if prop_data:
                self.properties.append(prop_data)
    
    def _parse_property_object(self, prop_text: str) -> Dict[str, Any] | None:
        """Parse a single property object."""
        # Extract key fields
        name_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", prop_text)
        display_match = re.search(r"displayName:\s*['\"]([^'\"]+)['\"]", prop_text)
        type_match = re.search(r"type:\s*['\"]([^'\"]+)['\"]", prop_text)
        default_match = re.search(r"default:\s*([^,\n]+)", prop_text)
        required_match = re.search(r"required:\s*(true|false)", prop_text)
        desc_match = re.search(r"description:\s*['\"]([^'\"]+)['\"]", prop_text)
        
        if not name_match:
            return None
        
        prop_name = name_match.group(1)
        
        # Map TS types to Python types
        ts_type = type_match.group(1) if type_match else "string"
        py_type = self._map_type(ts_type)
        
        prop_data = {
            "name": prop_name,
            "displayName": display_match.group(1) if display_match else prop_name,
            "type": py_type,
            "required": required_match.group(1) == "true" if required_match else False,
        }
        
        if default_match:
            default_val = default_match.group(1).strip().rstrip(',')
            # Clean up default value
            if default_val.startswith("'") or default_val.startswith('"'):
                default_val = default_val[1:-1]
            prop_data["default"] = default_val
        
        if desc_match:
            prop_data["description"] = desc_match.group(1)
        
        return prop_data
    
    def _map_type(self, ts_type: str) -> str:
        """Map TypeScript type to Python type."""
        type_map = {
            "string": "string",
            "number": "number",
            "boolean": "boolean",
            "options": "options",
            "hidden": "hidden",
        }
        return type_map.get(ts_type, "string")


# =============================================================================
# CREDENTIAL GENERATOR
# =============================================================================

class CredentialGenerator:
    """Generate Python credential from parsed metadata."""
    
    def __init__(self, metadata: Dict[str, Any], kb_patterns: Dict[str, Any]):
        self.metadata = metadata
        self.kb_patterns = kb_patterns
        self.auth_type = self._infer_auth_type()
    
    def _infer_auth_type(self) -> str:
        """Infer authentication type from metadata."""
        extends = self.metadata.get("extends")
        if extends == "oAuth2Api":
            return "oauth2"
        
        # Check property names
        prop_names = [p["name"] for p in self.metadata.get("properties", [])]
        
        if "accessToken" in prop_names or "apiKey" in prop_names:
            return "api_key"
        
        if "host" in prop_names and "database" in prop_names:
            return "database"
        
        return "generic"
    
    def generate(self) -> str:
        """Generate Python credential code."""
        if self.auth_type == "oauth2":
            return self._generate_oauth2()
        elif self.auth_type == "api_key":
            return self._generate_api_key()
        elif self.auth_type == "database":
            return self._generate_database()
        else:
            return self._generate_generic()
    
    def _generate_oauth2(self) -> str:
        """Generate OAuth2 credential that extends base."""
        credential_name = self.metadata["class_name"].replace("Credential", "").replace("Api", "Api")
        # Convert to camelCase name
        name_parts = re.findall(r'[A-Z][a-z]*', credential_name)
        credential_key = ''.join([name_parts[0].lower()] + name_parts[1:]) if name_parts else credential_name
        
        class_name = f"{credential_name}Credential"
        display_name = self.metadata.get("display_name", credential_name)
        
        # Extract scope if present
        scope_props = [p for p in self.metadata.get("properties", []) if p["name"] == "scope"]
        default_scope = scope_props[0].get("default", "") if scope_props else ""
        
        # Build scope constants
        scope_constants = ""
        if default_scope:
            scopes = [s.strip() for s in default_scope.split()]
            scope_list_str = ",\n        ".join([f"'{s}'" for s in scopes])
            scope_constants = f"SCOPES = [\n        {scope_list_str}\n    ]"
        
        return OAUTH2_EXTENDS_TEMPLATE.substitute(
            class_name=class_name,
            credential_name=credential_key,
            display_name=display_name,
            scope_constants=scope_constants,
            default_scope=default_scope,
            property_modifications="",
        )
    
    def _generate_api_key(self) -> str:
        """Generate API key credential."""
        return self._generate_generic()  # Use generic for now
    
    def _generate_database(self) -> str:
        """Generate database credential."""
        return self._generate_generic()
    
    def _generate_generic(self) -> str:
        """Generate generic credential from properties."""
        credential_name = self.metadata["class_name"].replace("Credential", "").replace("Api", "Api")
        # Convert to camelCase name
        name_parts = re.findall(r'[A-Z][a-z]*', credential_name)
        credential_key = ''.join([name_parts[0].lower()] + name_parts[1:]) if name_parts else credential_name
        
        class_name = f"{credential_name}Credential"
        display_name = self.metadata.get("display_name", credential_name)
        description = f"authentication for {display_name}"
        
        # Build properties array
        properties_array = self._build_properties_array()
        
        # Build test body
        test_body = self._build_test_body()
        
        return BASE_CREDENTIAL_TEMPLATE.substitute(
            class_name=class_name,
            credential_name=credential_key,
            display_name=display_name,
            description=description,
            properties_array=properties_array,
            test_body=test_body,
        )
    
    def _build_properties_array(self) -> str:
        """Build Python list of property dicts."""
        if not self.metadata.get("properties"):
            return "[]"
        
        props_lines = ["["]
        for prop in self.metadata["properties"]:
            props_lines.append("        {")
            props_lines.append(f'            "name": "{prop["name"]}",')
            props_lines.append(f'            "displayName": "{prop.get("displayName", prop["name"])}",')
            props_lines.append(f'            "type": "{prop["type"]}",')
            props_lines.append(f'            "required": {str(prop.get("required", False))},')
            
            if "default" in prop:
                default_repr = json.dumps(prop["default"])
                props_lines.append(f'            "default": {default_repr},')
            
            if "description" in prop:
                props_lines.append(f'            "description": "{prop["description"]}"')
            
            props_lines.append("        },")
        
        props_lines.append("    ]")
        return "\n".join(props_lines)
    
    def _build_test_body(self) -> str:
        """Build test method body."""
        # Simple placeholder test
        return '''            # TODO: Implement actual test logic
            # This is a placeholder that should be customized
            return {
                "success": True,
                "message": "Credential validation placeholder - implement actual test"
            }
'''


# =============================================================================
# MAIN SKILL EXECUTION
# =============================================================================

def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Convert n8n credentials to Python credential types.
    
    Reads from:
    - artifacts/{correlation_id}/source_bundle/ (TS credential files)
    - artifacts/{correlation_id}/inferred_schema.json (fallback)
    
    Writes to:
    - artifacts/{correlation_id}/credentials/*.py
    - artifacts/{correlation_id}/credential_conversion_log.json
    - artifacts/{correlation_id}/credential_registry_entries.json
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    credential_types = inputs["credential_types"]
    source_bundle_path = Path(inputs["source_bundle_path"])
    
    ctx.log("credential_convert_start", {
        "correlation_id": correlation_id,
        "credential_types": credential_types,
    })
    
    # Setup output paths
    artifact_base = ctx.artifact_root / correlation_id
    output_dir = artifact_base / "credentials"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load KB patterns
    kb_patterns = _load_kb_patterns(ctx)
    
    converted = []
    skipped = []
    registry_entries = []
    conversion_log = {
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "conversions": [],
    }
    
    for cred_type in credential_types:
        try:
            ctx.log("convert_credential", {"type": cred_type})
            
            # Try to find TS credential file
            ts_file = _find_credential_file(source_bundle_path, cred_type)
            
            if ts_file:
                # Parse TS file
                ts_content = ts_file.read_text()
                parser = TSCredentialParser(ts_content, cred_type)
                metadata = parser.parse()
            else:
                # Fallback: infer from schema (not implemented yet)
                ctx.log("credential_source_missing", {
                    "type": cred_type,
                    "reason": "TS file not found, skipping for now"
                })
                skipped.append({
                    "name": cred_type,
                    "reason": "Source TS file not found"
                })
                continue
            
            # Generate Python credential
            generator = CredentialGenerator(metadata, kb_patterns)
            python_code = generator.generate()
            
            # Write output file
            output_file = output_dir / f"{cred_type}.py"
            output_file.write_text(python_code)
            
            # Record conversion
            converted.append({
                "name": cred_type,
                "output_file": str(output_file),
                "fields": [p["name"] for p in metadata.get("properties", [])],
                "auth_type": generator.auth_type,
            })
            
            conversion_log["conversions"].append({
                "credential_type": cred_type,
                "class_name": metadata.get("class_name"),
                "display_name": metadata.get("display_name"),
                "auth_type": generator.auth_type,
                "extends": metadata.get("extends"),
                "properties": metadata.get("properties", []),
            })
            
            # Prepare registry entry
            class_name = metadata.get("class_name", cred_type) + "Credential"
            import_stmt = f"from .{cred_type} import {class_name}"
            registry_entries.append({
                "credential_type": cred_type,
                "import_statement": import_stmt,
                "class_name": class_name,
            })
            
        except Exception as e:
            ctx.log("credential_convert_error", {
                "type": cred_type,
                "error": str(e),
            })
            skipped.append({
                "name": cred_type,
                "reason": f"Conversion error: {str(e)}"
            })
    
    # Write conversion log
    log_file = artifact_base / "credential_conversion_log.json"
    log_file.write_text(json.dumps(conversion_log, indent=2))
    
    # Write registry entries
    registry_file = artifact_base / "credential_registry_entries.json"
    registry_file.write_text(json.dumps({
        "entries": registry_entries
    }, indent=2))
    
    ctx.log("credential_convert_complete", {
        "converted": len(converted),
        "skipped": len(skipped),
    })
    
    return {
        "credentials_converted": converted,
        "credentials_skipped": skipped,
        "registry_entries": registry_entries,
    }


def _find_credential_file(source_bundle: Path, cred_type: str) -> Path | None:
    """Find TS credential file in source bundle."""
    # Try common patterns
    patterns = [
        f"{cred_type}.credentials.ts",
        f"{cred_type}.credential.ts",
        f"*{cred_type}*.credentials.ts",
    ]
    
    for pattern in patterns:
        matches = list(source_bundle.glob(f"**/{pattern}"))
        if matches:
            return matches[0]
    
    return None


def _load_kb_patterns(ctx: "ExecutionContext") -> Dict[str, Any]:
    """Load KB auth patterns for reference."""
    try:
        # Try to load from runtime/kb/patterns/auth_patterns.json
        kb_file = ctx.repo_root / "runtime" / "kb" / "patterns" / "auth_patterns.json"
        if kb_file.exists():
            return json.loads(kb_file.read_text())
    except Exception:
        pass
    
    return {}
