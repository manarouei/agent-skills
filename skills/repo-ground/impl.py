"""
Repo Ground Skill Implementation

Produces repo_facts.json by reading canonical sources from the target repository.
This skill has fs_scope=artifacts so it can run without repo_facts.json existing
(avoiding the chicken-and-egg problem), and it produces repo_facts.json for
downstream code-generation skills.

Additionally produces target_repo_layout.json with conventions for where/how
nodes should be placed (consumed by apply-changes skill).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext


# Known patterns for auto-detection
BASENODE_CONTRACT_PATTERNS = [
    "BASENODE_CONTRACT.md",
    "contracts/BASENODE_CONTRACT.md",
    "contracts/basenode_contract.py",
    "docs/BASENODE_CONTRACT.md",
    "base.py",
    "nodes/base.py",
]

NODE_LOADER_PATTERNS = [
    "loader.py",
    "registry.py",
    "node_registry.py",
    "nodes/loader.py",
    "nodes/registry.py",
    "backend/loader.py",
]

# Patterns to find golden nodes (existing high-quality implementations)
# Include both PascalCase (TypeScript convention) and snake_case/lowercase (Python)
GOLDEN_NODE_PATTERNS = [
    # Python node implementations (snake_case)
    "gmail.py",
    "bale.py",
    "telegram_trigger.py",
    "ai_agent.py",
    "http_request.py",
    "slack.py",
    "mysql.py",
    "postgres.py",
    # TypeScript node implementations (PascalCase)
    "HttpRequest.py",
    "Slack.py",
    "MySQL.py",
    "Postgres.py",
    "Gmail.py",
    "Telegram.py",
    "HttpRequest.node.ts",
    "Slack.node.ts",
    # Also check common locations for node implementations
    "nodepacks/core/nodes.py",
    "nodepacks/*/nodes.py",
    "nodes/nodes.py",
    "nodes.py",
    # BaseNode contract
    "base.py",
    "nodes/base.py",
]

# Test command detection
TEST_COMMAND_SOURCES = [
    ("pyproject.toml", "pytest"),
    ("pytest.ini", "pytest"),
    ("package.json", "npm test"),
    ("Makefile", "make test"),
]

# Patterns for detecting node directories
NODE_DIR_PATTERNS = [
    "nodes",
    "src/nodes",
    "backend/nodes",
    "lib/nodes",
]

# Patterns for registry dict names
REGISTRY_DICT_PATTERNS = [
    "node_definitions",
    "NODE_DEFINITIONS",
    "nodes",
    "NODES",
    "node_registry",
    "registry",
]


def _find_file(repo_root: Path, patterns: list[str]) -> str | None:
    """Find the first matching file from patterns."""
    for pattern in patterns:
        candidate = repo_root / pattern
        if candidate.exists() and candidate.is_file():
            return str(candidate.relative_to(repo_root))
    
    # Recursive search for the filename component
    for pattern in patterns:
        filename = Path(pattern).name
        matches = list(repo_root.rglob(filename))
        if matches:
            # Prefer shorter paths (closer to root)
            matches.sort(key=lambda p: len(p.parts))
            return str(matches[0].relative_to(repo_root))
    
    return None


def _find_all_files(repo_root: Path, patterns: list[str], max_results: int = 5) -> list[str]:
    """Find all matching files from patterns, up to max_results."""
    results = []
    seen = set()
    
    for pattern in patterns:
        filename = Path(pattern).name
        matches = list(repo_root.rglob(filename))
        for match in matches:
            rel_path = str(match.relative_to(repo_root))
            if rel_path not in seen:
                seen.add(rel_path)
                results.append(rel_path)
                if len(results) >= max_results:
                    return results
    
    return results


def _detect_test_command(repo_root: Path) -> str:
    """Detect the test command for this repository."""
    for config_file, default_cmd in TEST_COMMAND_SOURCES:
        config_path = repo_root / config_file
        if config_path.exists():
            # For pyproject.toml, try to extract pytest args
            if config_file == "pyproject.toml":
                content = config_path.read_text()
                if "[tool.pytest" in content:
                    return "pytest"
            # For package.json, try to extract test script
            elif config_file == "package.json":
                try:
                    pkg = json.loads(config_path.read_text())
                    if "scripts" in pkg and "test" in pkg["scripts"]:
                        return pkg["scripts"]["test"]
                except json.JSONDecodeError:
                    pass
            return default_cmd
    
    # Default fallback
    return "pytest tests/"


def _detect_node_dir(repo_root: Path) -> str:
    """Detect where nodes live in the repository."""
    for pattern in NODE_DIR_PATTERNS:
        candidate = repo_root / pattern
        if candidate.exists() and candidate.is_dir():
            # Check if it contains Python files (nodes)
            py_files = list(candidate.glob("*.py"))
            if py_files:
                return pattern
    return "nodes"  # Default


def _detect_registry_info(repo_root: Path, node_dir: str) -> tuple[str | None, str, str]:
    """
    Detect registry file, strategy, and dict name.
    
    Returns:
        (registry_file, registry_strategy, registry_dict_name)
    """
    # Check for __init__.py in node directory
    init_path = repo_root / node_dir / "__init__.py"
    if init_path.exists():
        content = init_path.read_text()
        
        # Look for dict patterns like: node_definitions = {
        for dict_name in REGISTRY_DICT_PATTERNS:
            pattern = rf"^{dict_name}\s*=\s*\{{"
            if re.search(pattern, content, re.MULTILINE):
                return f"{node_dir}/__init__.py", "dict_import", dict_name
        
        # If has imports but no obvious registry dict, might be auto-discover
        if "from ." in content or "import " in content:
            return f"{node_dir}/__init__.py", "dict_import", "node_definitions"
    
    # Check for separate registry.py
    registry_path = repo_root / node_dir / "registry.py"
    if registry_path.exists():
        content = registry_path.read_text()
        for dict_name in REGISTRY_DICT_PATTERNS:
            pattern = rf"^{dict_name}\s*=\s*\{{"
            if re.search(pattern, content, re.MULTILINE):
                return f"{node_dir}/registry.py", "dict_import", dict_name
        return f"{node_dir}/registry.py", "explicit_register", "registry"
    
    # Default to dict_import with __init__.py
    return f"{node_dir}/__init__.py", "dict_import", "node_definitions"


def _detect_base_class(repo_root: Path, node_dir: str) -> tuple[str | None, str]:
    """
    Detect base class file and name.
    
    Returns:
        (base_class_file, base_class_name)
    """
    # Common patterns for base class file
    base_patterns = [
        f"{node_dir}/base.py",
        f"{node_dir}/base_node.py",
        "base.py",
        "core/base.py",
    ]
    
    for pattern in base_patterns:
        candidate = repo_root / pattern
        if candidate.exists():
            content = candidate.read_text()
            # Look for class definition inheriting from ABC or similar
            match = re.search(r"class\s+(\w+Node|\w+Base)\s*\(", content)
            if match:
                return pattern, match.group(1)
            # Look for any class that looks like a base node
            match = re.search(r"class\s+(Base\w+|Node)\s*\(", content)
            if match:
                return pattern, match.group(1)
    
    return f"{node_dir}/base.py", "BaseNode"


def _detect_tests_dir(repo_root: Path) -> str:
    """Detect tests directory."""
    test_patterns = ["tests", "test", "tests/unit", "tests/integration"]
    for pattern in test_patterns:
        candidate = repo_root / pattern
        if candidate.exists() and candidate.is_dir():
            return pattern
    return "tests"


def _detect_python_version(repo_root: Path) -> str | None:
    """Detect Python version from config files."""
    # Try pyproject.toml
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        content = pyproject.read_text()
        # Look for python = "^3.11" or requires-python = ">=3.10"
        match = re.search(r'python\s*=\s*["\'][\^>=]*(\d+\.\d+)', content)
        if match:
            return match.group(1)
        match = re.search(r'requires-python\s*=\s*["\'][\^>=]*(\d+\.\d+)', content)
        if match:
            return match.group(1)
    
    # Try .python-version
    pyversion = repo_root / ".python-version"
    if pyversion.exists():
        return pyversion.read_text().strip().split(".")[0:2]
    
    return None


def _detect_venv_path(repo_root: Path) -> str | None:
    """Detect virtual environment path."""
    venv_patterns = [".venv", "venv", ".virtualenv", "env"]
    for pattern in venv_patterns:
        candidate = repo_root / pattern
        if candidate.exists() and candidate.is_dir():
            # Verify it's actually a venv (has bin/python or Scripts/python.exe)
            if (candidate / "bin" / "python").exists():
                return pattern
            if (candidate / "Scripts" / "python.exe").exists():
                return pattern
    return None


def _build_target_repo_layout(repo_root: Path) -> dict[str, Any]:
    """
    Build target repo layout from auto-detection.
    
    Returns dict compatible with TargetRepoLayout model.
    """
    # Detect node directory
    node_dir = _detect_node_dir(repo_root)
    
    # Detect registry info
    registry_file, registry_strategy, registry_dict_name = _detect_registry_info(repo_root, node_dir)
    
    # Detect base class
    base_class_file, base_class_name = _detect_base_class(repo_root, node_dir)
    
    # Detect tests dir
    tests_dir = _detect_tests_dir(repo_root)
    
    # Detect Python version
    python_version = _detect_python_version(repo_root)
    
    # Detect venv path
    venv_path = _detect_venv_path(repo_root)
    
    return {
        "target_repo_root": str(repo_root),
        "node_output_base_dir": node_dir,
        "registry_file": registry_file,
        "registry_strategy": registry_strategy,
        "registry_dict_name": registry_dict_name,
        "base_class_file": base_class_file,
        "base_class_name": base_class_name,
        "tests_dir": tests_dir,
        "python_version": python_version,
        "venv_path": venv_path,
        "extra_allowlist_patterns": [],
    }


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Produce repo_facts.json and target_repo_layout.json by reading canonical sources.
    
    This skill has fs_scope=artifacts so it can run without repo_facts.json
    existing, and it produces repo_facts.json for downstream skills.
    
    Also produces target_repo_layout.json with conventions for where/how nodes
    should be placed (consumed by apply-changes skill).
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    repo_root_str = inputs.get("repo_root", ".")
    repo_root = Path(repo_root_str).resolve()
    
    ctx.log("repo_ground_start", {
        "correlation_id": correlation_id,
        "repo_root": str(repo_root),
    })
    
    if not repo_root.exists():
        ctx.log("repo_root_not_found", {"repo_root": str(repo_root)})
        return {
            "error": f"Repository root not found: {repo_root}",
            "repo_facts_path": None,
            "repo_facts": None,
            "target_repo_layout_path": None,
            "target_repo_layout": None,
        }
    
    # Auto-detect or use hints
    basenode_hint = inputs.get("basenode_contract_hint")
    golden_hints = inputs.get("golden_node_hints", [])
    
    # Find BaseNode contract
    if basenode_hint and (repo_root / basenode_hint).exists():
        basenode_contract_path = basenode_hint
    else:
        basenode_contract_path = _find_file(repo_root, BASENODE_CONTRACT_PATTERNS)
    
    # Find node loader
    node_loader_paths = []
    loader_path = _find_file(repo_root, NODE_LOADER_PATTERNS)
    if loader_path:
        node_loader_paths.append(loader_path)
    
    # Find golden nodes
    if golden_hints:
        golden_node_paths = [h for h in golden_hints if (repo_root / h).exists()]
    else:
        golden_node_paths = _find_all_files(repo_root, GOLDEN_NODE_PATTERNS, max_results=5)
    
    # Detect test command
    test_command = _detect_test_command(repo_root)
    
    # Build repo_facts
    repo_facts = {
        "basenode_contract_path": basenode_contract_path or "",
        "node_loader_paths": node_loader_paths,
        "golden_node_paths": golden_node_paths,
        "test_command": test_command,
    }
    
    # Build target repo layout
    target_repo_layout = _build_target_repo_layout(repo_root)
    
    # Write to artifacts
    artifacts_dir = ctx.artifacts_dir
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    repo_facts_path = artifacts_dir / "repo_facts.json"
    repo_facts_path.write_text(json.dumps(repo_facts, indent=2))
    
    target_repo_layout_path = artifacts_dir / "target_repo_layout.json"
    target_repo_layout_path.write_text(json.dumps(target_repo_layout, indent=2))
    
    ctx.log("repo_ground_complete", {
        "repo_facts_path": str(repo_facts_path),
        "target_repo_layout_path": str(target_repo_layout_path),
        "found_basenode": bool(basenode_contract_path),
        "found_loaders": len(node_loader_paths),
        "found_golden": len(golden_node_paths),
        "node_dir": target_repo_layout["node_output_base_dir"],
        "registry_strategy": target_repo_layout["registry_strategy"],
    })
    
    return {
        "repo_facts_path": str(repo_facts_path),
        "repo_facts": repo_facts,
        "target_repo_layout_path": str(target_repo_layout_path),
        "target_repo_layout": target_repo_layout,
    }
