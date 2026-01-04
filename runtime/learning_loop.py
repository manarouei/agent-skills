"""Learning Loop Support - Golden Artifacts and Promotion Candidates.

This module implements the controlled learning loop infrastructure:

1. Golden Artifact Emission: After successful node generation (code-implement/code-convert),
   emit a structured artifact package that can be curated into the knowledge base.

2. Promotion Candidates: After successful fix-loop completion (code-fix → code-validate),
   emit the correction pattern as a promotion candidate for review.

IMPORTANT: All artifacts are READ-ONLY at runtime. Promotion to the knowledge base
requires human review and explicit curation via scripts/promote_artifact.py.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class GoldenArtifactPackage:
    """A structured package of artifacts from successful node generation.
    
    Golden artifacts are emitted after code-implement or code-convert succeeds.
    They contain the generated code, schema, trace map, and metadata needed
    for future pattern extraction and knowledge base updates.
    """
    
    correlation_id: str
    node_type: str
    skill_name: str  # code-implement or code-convert
    created_at: str
    
    # Generated artifacts
    generated_code: dict[str, str]  # filename -> content
    node_schema: Optional[dict[str, Any]] = None
    trace_map: Optional[dict[str, Any]] = None
    
    # Quality signals
    tests_passed: bool = False
    validation_passed: bool = False
    fix_iterations: int = 0
    
    # Provenance
    source_files: list[str] = field(default_factory=list)
    source_hash: Optional[str] = None  # SHA256 of source bundle
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "correlation_id": self.correlation_id,
            "node_type": self.node_type,
            "skill_name": self.skill_name,
            "created_at": self.created_at,
            "generated_code": self.generated_code,
            "node_schema": self.node_schema,
            "trace_map": self.trace_map,
            "tests_passed": self.tests_passed,
            "validation_passed": self.validation_passed,
            "fix_iterations": self.fix_iterations,
            "source_files": self.source_files,
            "source_hash": self.source_hash,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GoldenArtifactPackage:
        """Deserialize from dictionary."""
        return cls(
            correlation_id=data["correlation_id"],
            node_type=data["node_type"],
            skill_name=data["skill_name"],
            created_at=data["created_at"],
            generated_code=data.get("generated_code", {}),
            node_schema=data.get("node_schema"),
            trace_map=data.get("trace_map"),
            tests_passed=data.get("tests_passed", False),
            validation_passed=data.get("validation_passed", False),
            fix_iterations=data.get("fix_iterations", 0),
            source_files=data.get("source_files", []),
            source_hash=data.get("source_hash"),
        )


@dataclass
class PromotionCandidate:
    """A candidate correction pattern for knowledge base promotion.
    
    Promotion candidates are emitted after successful fix-loop completion.
    They capture the error pattern, the fix applied, and metadata for
    human review before promotion to the knowledge base.
    """
    
    # Required fields (no defaults) - must come first
    correlation_id: str
    created_at: str
    error_category: str  # e.g., "async_violation", "missing_timeout", "type_error"
    error_message: str
    original_code: str
    fixed_code: str
    fix_description: str
    
    # Optional fields (with defaults) - must come after required fields
    error_location: Optional[str] = None  # file:line if available
    fix_iteration: int = 1  # Which iteration fixed it (1-3)
    validation_passed: bool = False
    suggested_category: Optional[str] = None
    suggested_pattern_id: Optional[str] = None
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "correlation_id": self.correlation_id,
            "created_at": self.created_at,
            "error_category": self.error_category,
            "error_message": self.error_message,
            "error_location": self.error_location,
            "original_code": self.original_code,
            "fixed_code": self.fixed_code,
            "fix_description": self.fix_description,
            "fix_iteration": self.fix_iteration,
            "validation_passed": self.validation_passed,
            "suggested_category": self.suggested_category,
            "suggested_pattern_id": self.suggested_pattern_id,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromotionCandidate:
        """Deserialize from dictionary."""
        return cls(
            correlation_id=data["correlation_id"],
            created_at=data["created_at"],
            error_category=data["error_category"],
            error_message=data["error_message"],
            error_location=data.get("error_location"),
            original_code=data["original_code"],
            fixed_code=data["fixed_code"],
            fix_description=data["fix_description"],
            fix_iteration=data.get("fix_iteration", 1),
            validation_passed=data.get("validation_passed", False),
            suggested_category=data.get("suggested_category"),
            suggested_pattern_id=data.get("suggested_pattern_id"),
        )


class LearningLoopEmitter:
    """Emitter for golden artifacts and promotion candidates.
    
    This class handles the emission of learning artifacts to the artifacts
    directory. All emitted artifacts are structured for human review and
    potential promotion to the knowledge base.
    
    Directory structure:
        artifacts/
            golden/<correlation_id>/
                manifest.json      # GoldenArtifactPackage metadata
                code/              # Generated code files
                schema.json        # Node schema (if available)
                trace_map.json     # Trace map (if available)
            promotion_candidates/<correlation_id>_<timestamp>.json
    """
    
    def __init__(self, artifacts_dir: Path):
        """Initialize the emitter.
        
        Args:
            artifacts_dir: Root artifacts directory (e.g., /path/to/artifacts)
        """
        self.artifacts_dir = artifacts_dir
        self.golden_dir = artifacts_dir / "golden"
        self.promotion_dir = artifacts_dir / "promotion_candidates"
    
    def emit_golden_artifact(
        self,
        package: GoldenArtifactPackage,
    ) -> Path:
        """Emit a golden artifact package.
        
        Creates a structured directory with the artifact contents:
            golden/<correlation_id>/
                manifest.json
                code/<filename>...
                schema.json (optional)
                trace_map.json (optional)
        
        Args:
            package: The golden artifact package to emit
            
        Returns:
            Path to the emitted artifact directory
        """
        # Create directory structure
        artifact_dir = self.golden_dir / package.correlation_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        
        code_dir = artifact_dir / "code"
        code_dir.mkdir(exist_ok=True)
        
        # Write generated code files
        for filename, content in package.generated_code.items():
            code_file = code_dir / filename
            code_file.parent.mkdir(parents=True, exist_ok=True)
            code_file.write_text(content)
        
        # Write schema if available
        if package.node_schema:
            schema_path = artifact_dir / "schema.json"
            schema_path.write_text(json.dumps(package.node_schema, indent=2))
        
        # Write trace map if available
        if package.trace_map:
            trace_path = artifact_dir / "trace_map.json"
            trace_path.write_text(json.dumps(package.trace_map, indent=2))
        
        # Write manifest (metadata)
        manifest_path = artifact_dir / "manifest.json"
        manifest_path.write_text(json.dumps(package.to_dict(), indent=2))
        
        return artifact_dir
    
    def emit_promotion_candidate(
        self,
        candidate: PromotionCandidate,
    ) -> Path:
        """Emit a promotion candidate.
        
        Creates a JSON file in the promotion_candidates directory:
            promotion_candidates/<correlation_id>_<timestamp>.json
        
        Args:
            candidate: The promotion candidate to emit
            
        Returns:
            Path to the emitted candidate file
        """
        self.promotion_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp for uniqueness
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{candidate.correlation_id}_{timestamp}.json"
        
        candidate_path = self.promotion_dir / filename
        candidate_path.write_text(json.dumps(candidate.to_dict(), indent=2))
        
        return candidate_path
    
    def list_golden_artifacts(self) -> list[Path]:
        """List all golden artifact directories."""
        if not self.golden_dir.exists():
            return []
        return [p for p in self.golden_dir.iterdir() if p.is_dir()]
    
    def list_promotion_candidates(self) -> list[Path]:
        """List all promotion candidate files."""
        if not self.promotion_dir.exists():
            return []
        return [p for p in self.promotion_dir.glob("*.json")]
    
    def load_golden_artifact(self, correlation_id: str) -> Optional[GoldenArtifactPackage]:
        """Load a golden artifact package by correlation ID."""
        manifest_path = self.golden_dir / correlation_id / "manifest.json"
        if not manifest_path.exists():
            return None
        
        data = json.loads(manifest_path.read_text())
        return GoldenArtifactPackage.from_dict(data)
    
    def load_promotion_candidate(self, path: Path) -> Optional[PromotionCandidate]:
        """Load a promotion candidate from file."""
        if not path.exists():
            return None
        
        data = json.loads(path.read_text())
        return PromotionCandidate.from_dict(data)


def compute_source_hash(source_files: list[Path]) -> str:
    """Compute a deterministic hash of source files.
    
    This provides provenance tracking for golden artifacts,
    allowing verification that the source hasn't changed.
    """
    hasher = hashlib.sha256()
    
    # Sort for deterministic ordering
    for path in sorted(source_files):
        if path.exists():
            content = path.read_bytes()
            hasher.update(str(path).encode())
            hasher.update(content)
    
    return f"sha256:{hasher.hexdigest()}"


def categorize_error(error_message: str) -> str:
    """Categorize an error message for promotion candidate tagging.
    
    Returns a category string like "async_violation", "missing_timeout", etc.
    Used to suggest KB category placement for promotion candidates.
    """
    error_lower = error_message.lower()
    
    # Async violations (critical for Celery)
    if any(kw in error_lower for kw in ["async", "await", "asyncio", "aiohttp"]):
        return "async_violation"
    
    # Timeout issues
    if any(kw in error_lower for kw in ["timeout", "deadline"]):
        return "missing_timeout"
    
    # Type errors
    if any(kw in error_lower for kw in ["type", "typeerror", "annotation"]):
        return "type_error"
    
    # Import issues
    if any(kw in error_lower for kw in ["import", "module", "package"]):
        return "import_error"
    
    # Syntax errors
    if any(kw in error_lower for kw in ["syntax", "parse", "indentation"]):
        return "syntax_error"
    
    # Default category
    return "general_error"
