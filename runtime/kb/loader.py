#!/usr/bin/env python3
"""
Knowledge Base Loader

Provides read-only access to curated KB patterns with schema validation.
Agents MAY NOT write to KB at runtime — changes come via PR only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Optional jsonschema for validation
try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    jsonschema = None  # type: ignore


# Canonical categories (schema.json is source of truth)
CANONICAL_CATEGORIES = frozenset({"auth", "pagination", "ts_to_python", "service_quirk"})

# Legacy category aliases → canonical
CATEGORY_ALIASES: dict[str, str] = {
    "authentication": "auth",
    "type_conversion": "ts_to_python",
    "async_to_sync": "ts_to_python",
    "idiom_conversion": "ts_to_python",
}


def normalize_category(category: str) -> str:
    """Normalize category to canonical form."""
    if category in CANONICAL_CATEGORIES:
        return category
    if category in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[category]
    return category  # Return as-is, validation will catch invalid


@dataclass
class KBPattern:
    """A single KB pattern entry."""
    id: str
    name: str
    category: str
    description: str
    pattern: dict[str, Any] | str  # Structured pattern dict or legacy code string
    version: str = "1.0.0"
    examples: list[dict[str, str]] | list[str] = field(default_factory=list)
    applicability: dict[str, list[str]] = field(default_factory=dict)
    confidence: str = "medium"  # high, medium, low
    sources: list[str] = field(default_factory=list)
    created_at: Optional[str] = None
    approved_by: Optional[str] = None
    promoted_from: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "KBPattern":
        """Create pattern from dict."""
        return cls(
            id=data["id"],
            name=data["name"],
            category=data["category"],
            description=data["description"],
            pattern=data["pattern"],
            version=data.get("version", "1.0.0"),
            examples=data.get("examples", []),
            applicability=data.get("applicability", {}),
            confidence=data.get("confidence", "medium"),
            sources=data.get("sources", []),
            created_at=data.get("created_at"),
            approved_by=data.get("approved_by"),
            promoted_from=data.get("promoted_from"),
        )


@dataclass
class ValidationResult:
    """Result of KB entry validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)


class KBValidationError(Exception):
    """Raised when KB entry fails schema validation."""
    pass


class KnowledgeBase:
    """
    Read-only Knowledge Base for agent patterns.
    
    The KB contains curated patterns for:
    - Authentication (OAuth2, API keys, database connections)
    - Node implementation (BaseNode, resource/operation, execute/trigger)
    - Pagination and rate limiting
    - TypeScript → Python idioms
    - Service-specific quirks
    
    IMPORTANT: This class is READ-ONLY. Agents may propose KB updates
    as artifacts, but actual KB changes must come via PR.
    
    Directory structure:
        kb/
            patterns/
                auth_patterns.json      # Credential and auth patterns
                node_patterns.json      # Node implementation patterns  
                pagination_patterns.json # Pagination patterns
                ts_python_idioms.json   # TS→Python conversion patterns
            schema.json                 # JSON Schema for pattern entries
    """

    def __init__(self, kb_dir: Path | None = None):
        """
        Initialize KB with optional custom directory.
        
        Args:
            kb_dir: Path to KB directory. Defaults to runtime/kb/
        """
        if kb_dir is None:
            kb_dir = Path(__file__).parent
        self.kb_dir = kb_dir
        self.patterns_dir = kb_dir / "patterns"
        self._schema: dict[str, Any] | None = None
        self._patterns_cache: list[KBPattern] | None = None
        self._by_id_cache: dict[str, KBPattern] | None = None
        self._by_category_cache: dict[str, list[KBPattern]] | None = None

    @property
    def schema(self) -> dict[str, Any]:
        """Load and cache JSON schema."""
        if self._schema is None:
            schema_path = self.kb_dir / "schema.json"
            if schema_path.exists():
                self._schema = json.loads(schema_path.read_text())
            else:
                self._schema = {}
        return self._schema

    def _validate_entry_against_schema(self, data: dict[str, Any], source_path: Path) -> None:
        """Validate entry against JSON schema."""
        if not HAS_JSONSCHEMA or not self.schema:
            return  # Skip validation if jsonschema not available
        
        try:
            jsonschema.validate(data, self.schema)
        except jsonschema.ValidationError as e:
            raise KBValidationError(
                f"KB entry in {source_path} failed validation: {e.message}"
            )

    def validate_entry(self, data: dict[str, Any]) -> ValidationResult:
        """
        Validate a KB pattern entry.
        
        Args:
            data: Pattern data dict
            
        Returns:
            ValidationResult with valid flag and any errors
        """
        errors: list[str] = []
        
        # Check required fields (updated for new schema)
        required_fields = ["id", "name", "category", "description", "pattern"]
        for field_name in required_fields:
            if field_name not in data:
                errors.append(f"Missing required field: {field_name}")
        
        # Validate confidence value if present
        if "confidence" in data and data["confidence"] not in ("high", "medium", "low"):
            errors.append(f"Invalid confidence value: {data['confidence']} (must be high/medium/low)")
        
        # Validate category (normalize first, then check)
        if "category" in data:
            normalized = normalize_category(data["category"])
            if normalized not in CANONICAL_CATEGORIES:
                errors.append(f"Invalid category: {data['category']} (valid: {sorted(CANONICAL_CATEGORIES)})")
        
        # Validate pattern structure
        if "pattern" in data:
            pattern = data["pattern"]
            if isinstance(pattern, dict):
                if "type" not in pattern:
                    errors.append("Pattern dict must have 'type' field")
            # Legacy string patterns are still allowed for backward compat
        
        # Validate examples structure if present
        if "examples" in data:
            examples = data["examples"]
            if isinstance(examples, list):
                for i, ex in enumerate(examples):
                    if isinstance(ex, dict):
                        if "input" not in ex or "output" not in ex:
                            errors.append(f"Example {i} must have 'input' and 'output' fields")
                    # Legacy string examples are allowed
        
        # Use JSON schema if available (additional validation)
        if HAS_JSONSCHEMA and self.schema:
            try:
                jsonschema.validate(data, self.schema)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation error: {e.message}")
        
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    def _load_patterns(self) -> list[KBPattern]:
        """
        Load all patterns from patterns/ directory.
        
        Raises:
            KBValidationError: If any pattern fails validation (fail-fast)
        """
        patterns: list[KBPattern] = []
        validation_errors: list[str] = []
        
        if not self.patterns_dir.exists():
            return patterns
        
        # Scan all JSON files in patterns directory (flat structure)
        for pattern_file in sorted(self.patterns_dir.glob("*.json")):
            try:
                file_data = json.loads(pattern_file.read_text())
                
                # Handle both single pattern and array of patterns
                entries = file_data if isinstance(file_data, list) else [file_data]
                
                for i, entry in enumerate(entries):
                    # Validate entry before loading
                    result = self.validate_entry(entry)
                    if not result.valid:
                        entry_id = entry.get("id", f"index-{i}")
                        for err in result.errors:
                            validation_errors.append(f"{pattern_file.name}[{entry_id}]: {err}")
                        continue  # Skip invalid entries but collect all errors
                    
                    # Normalize category before creating pattern
                    if "category" in entry:
                        entry["category"] = normalize_category(entry["category"])
                    
                    pattern = KBPattern.from_dict(entry)
                    patterns.append(pattern)
                    
            except json.JSONDecodeError as e:
                validation_errors.append(f"{pattern_file.name}: JSON parse error: {e}")
            except KeyError as e:
                validation_errors.append(f"{pattern_file.name}: Missing required field: {e}")
        
        # Fail fast if any validation errors
        if validation_errors:
            raise KBValidationError(
                f"KB validation failed with {len(validation_errors)} error(s):\n" +
                "\n".join(f"  - {err}" for err in validation_errors)
            )
        
        return patterns

    def _ensure_loaded(self) -> list[KBPattern]:
        """Ensure patterns are loaded and caches built."""
        if self._patterns_cache is None:
            self._patterns_cache = self._load_patterns()
            
            # Build index caches
            self._by_id_cache = {}
            self._by_category_cache = {}
            
            for pattern in self._patterns_cache:
                self._by_id_cache[pattern.id] = pattern
                
                if pattern.category not in self._by_category_cache:
                    self._by_category_cache[pattern.category] = []
                self._by_category_cache[pattern.category].append(pattern)
        
        return self._patterns_cache

    def load_all(self) -> list[KBPattern]:
        """Load all patterns from KB."""
        return self._ensure_loaded()

    def get_by_id(self, pattern_id: str) -> KBPattern | None:
        """Get pattern by ID."""
        self._ensure_loaded()
        return self._by_id_cache.get(pattern_id)

    def get_by_category(self, category: str) -> list[KBPattern]:
        """
        Get all patterns in a category.
        
        Args:
            category: Category name (e.g., "authentication", "pagination")
            
        Returns:
            List of patterns in that category
        """
        self._ensure_loaded()
        return self._by_category_cache.get(category, [])

    def get_categories(self) -> list[str]:
        """Get list of all categories with patterns."""
        self._ensure_loaded()
        return list(self._by_category_cache.keys())

    def has_pattern(self, pattern_id: str) -> bool:
        """Check if pattern exists by ID."""
        return self.get_by_id(pattern_id) is not None

    def reload(self) -> None:
        """Force reload of patterns from disk."""
        self._patterns_cache = None
        self._by_id_cache = None
        self._by_category_cache = None
        self._schema = None

    def retrieve_patterns(
        self,
        categories: list[str] | None = None,
        service: str | None = None,
        node_type: str | None = None,
        max_patterns: int = 10,
    ) -> list[KBPattern]:
        """
        Retrieve relevant patterns for advisor context injection.
        
        This is the primary interface for skills to get relevant KB patterns.
        Patterns are filtered by applicability and limited to prevent token bloat.
        
        Args:
            categories: Categories to include (None = all). Normalized automatically.
            service: Filter by service applicability (e.g., "slack", "github")
            node_type: Filter by node type (e.g., "credential", "regular", "trigger")
            max_patterns: Maximum patterns to return (default 10)
            
        Returns:
            List of matching KBPattern objects, most relevant first
        """
        self._ensure_loaded()
        
        # Start with all patterns or category-filtered
        if categories:
            candidates: list[KBPattern] = []
            for cat in categories:
                normalized_cat = normalize_category(cat)
                candidates.extend(self._by_category_cache.get(normalized_cat, []))
        else:
            candidates = list(self._patterns_cache or [])
        
        # Filter by applicability
        filtered: list[KBPattern] = []
        for pattern in candidates:
            # Check service applicability
            if service:
                applicable_services = pattern.applicability.get("services", [])
                # Empty list = applies to all
                if applicable_services and service.lower() not in [s.lower() for s in applicable_services]:
                    continue
            
            # Check node_type applicability
            if node_type:
                applicable_types = pattern.applicability.get("node_types", [])
                # Empty list = applies to all
                if applicable_types and node_type.lower() not in [t.lower() for t in applicable_types]:
                    continue
            
            filtered.append(pattern)
        
        # Sort by confidence (high > medium > low) then by ID for stability
        confidence_order = {"high": 0, "medium": 1, "low": 2}
        filtered.sort(key=lambda p: (confidence_order.get(p.confidence, 2), p.id))
        
        return filtered[:max_patterns]

    def format_patterns_for_prompt(
        self,
        patterns: list[KBPattern],
        include_examples: bool = True,
        max_example_chars: int = 500,
    ) -> str:
        """
        Format patterns into a string suitable for injection into advisor prompts.
        
        Args:
            patterns: Patterns to format
            include_examples: Whether to include examples
            max_example_chars: Max chars per example to include
            
        Returns:
            Formatted string for prompt injection
        """
        if not patterns:
            return ""
        
        lines = ["## Relevant KB Patterns\n"]
        
        for pattern in patterns:
            lines.append(f"### {pattern.name} ({pattern.id})")
            lines.append(f"Category: {pattern.category}")
            lines.append(f"{pattern.description}\n")
            
            # Add pattern details
            if isinstance(pattern.pattern, dict):
                impl_notes = pattern.pattern.get("implementation_notes", "")
                if impl_notes:
                    lines.append(f"**Implementation notes:** {impl_notes}\n")
            
            # Add examples if requested
            if include_examples and pattern.examples:
                lines.append("**Examples:**")
                for ex in pattern.examples[:2]:  # Max 2 examples per pattern
                    if isinstance(ex, dict):
                        inp = ex.get("input", "")[:max_example_chars]
                        out = ex.get("output", "")[:max_example_chars]
                        lines.append(f"- Input: `{inp}`")
                        lines.append(f"  Output: `{out}`")
                        if ex.get("notes"):
                            lines.append(f"  Note: {ex['notes']}")
                    else:
                        lines.append(f"- {str(ex)[:max_example_chars]}")
                lines.append("")
        
        return "\n".join(lines)
