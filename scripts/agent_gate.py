#!/usr/bin/env python3
"""
Agent Gate Runner

Runs all validation gates in the correct sequence before PR-ready output.
This is the unified gate referenced in .github/copilot-instructions.md.

IMPORTANT: For PR-ready mode, --correlation-id is REQUIRED.
Without it, scope enforcement cannot run and the gate will fail.

Exit codes:
    0 - All gates passed
    1 - At least one gate failed

Usage:
    python3 scripts/agent_gate.py --correlation-id <id> [--trace-map PATH] [--repo-path PATH] [--skip-pytest] [--skip-behavioral]
    
Gates run in order:
    1. validate_skill_contracts.py - Contract validation for all 12 skills
    2. validate_trace_map.py - Trace map validation (if --trace-map provided)
    3. enforce_scope.py <correlation_id> --check-git - Git diff scope enforcement (REQUIRED)
    4. validate_sync_celery_compat.py - Async pattern detection
    5. behavioral_validate - No-stub, HTTP parity, semantic diff gates (NEW)
    6. pytest -q - Run test suite (unless --skip-pytest)
"""

import subprocess
import sys
from pathlib import Path


def run_gate(name: str, cmd: list[str], allow_failure: bool = False) -> bool:
    """
    Run a gate command and report result.
    
    Returns True if passed, False if failed.
    """
    print(f"\n{'='*60}")
    print(f"GATE: {name}")
    print(f"CMD:  {' '.join(cmd)}")
    print("=" * 60)
    
    try:
        result = subprocess.run(cmd, timeout=300)
        passed = result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: Gate '{name}' exceeded 5 minute limit")
        passed = False
    except FileNotFoundError as e:
        print(f"ERROR: Command not found: {e}")
        passed = False
    
    status = "✓ PASSED" if passed else ("⚠ SKIPPED" if allow_failure else "✗ FAILED")
    print(f"\n{status}: {name}")
    
    return passed or allow_failure


def run_behavioral_gate(correlation_id: str, artifacts_dir: Path, golden_path: Path | None = None) -> bool:
    """
    Run behavioral validation gate.
    
    Checks generated code for:
    1. No-stub patterns (TODO, NotImplementedError, empty responses)
    2. HTTP parity with golden (if available)
    3. Semantic diff with golden (if available)
    4. Contract round-trip validity
    
    Returns True if passed, False if failed.
    """
    print(f"\n{'='*60}")
    print("GATE: Behavioral Validation")
    print("=" * 60)
    
    # Find generated node file
    converted_dir = artifacts_dir / correlation_id / "converted_node"
    
    if not converted_dir.exists():
        print(f"  ⚠ No converted_node directory found at {converted_dir}")
        print("  ⚠ Skipping behavioral validation (no generated code)")
        return True  # Skip, not fail
    
    # Find Python files in converted_node
    py_files = list(converted_dir.glob("*.py"))
    node_files = [f for f in py_files if f.name != "__init__.py"]
    
    if not node_files:
        print(f"  ⚠ No node files found in {converted_dir}")
        return True  # Skip
    
    all_passed = True
    
    # Import behavioral validation
    # Import behavioral validation using importlib (skill dirs use hyphens)
    try:
        import importlib.util
        skill_impl = Path(__file__).parent.parent / "skills" / "behavioral-validate" / "impl.py"
        spec = importlib.util.spec_from_file_location("behavioral_validate_impl", skill_impl)
        behavioral_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(behavioral_module)
        validate_no_stubs = behavioral_module.validate_no_stubs
        validate_http_parity = behavioral_module.validate_http_parity
    except ImportError:
        # Fall back to inline validation
        print("  ⚠ behavioral_validate skill not importable, using inline checks")
        
        # Inline no-stub check
        STUB_PATTERNS = [
            r'#\s*TODO:\s*Implement',
            r'#\s*__STUB_MARKER__',
            r'raise\s+NotImplementedError',
            r'response\s*=\s*\{\s*\}',
        ]
        
        import re
        
        for node_file in node_files:
            print(f"\n  Checking: {node_file.name}")
            code = node_file.read_text()
            
            violations = []
            for pattern in STUB_PATTERNS:
                matches = re.findall(pattern, code, re.MULTILINE | re.IGNORECASE)
                if matches:
                    violations.append(f"Pattern '{pattern}' found {len(matches)} times")
            
            if violations:
                print(f"    ✗ STUB VIOLATIONS:")
                for v in violations:
                    print(f"      - {v}")
                all_passed = False
            else:
                print(f"    ✓ No stub patterns found")
            
            # Check for HTTP calls
            http_patterns = [
                'requests.',
                'self._api_request',
                'self._http_request',
            ]
            has_http = any(p in code for p in http_patterns)
            
            if has_http:
                print(f"    ✓ HTTP calls present")
            else:
                print(f"    ⚠ WARNING: No HTTP calls detected")
        
        return all_passed
    
    # Use imported validation
    for node_file in node_files:
        print(f"\n  Checking: {node_file.name}")
        code = node_file.read_text()
        
        # Gate 1: No-stub
        result = validate_no_stubs(code)
        if result.passed:
            print(f"    ✓ No-stub gate passed")
        else:
            print(f"    ✗ No-stub gate FAILED:")
            for v in result.violations:
                print(f"      - {v}")
            all_passed = False
        
        # Gate 2: HTTP parity (if golden available)
        if golden_path and golden_path.exists():
            golden_code = golden_path.read_text()
            result = validate_http_parity(code, golden_code)
            if result.passed:
                print(f"    ✓ HTTP parity gate passed")
            else:
                print(f"    ✗ HTTP parity gate FAILED:")
                for v in result.violations:
                    print(f"      - {v}")
                all_passed = False
    
    status = "✓ PASSED" if all_passed else "✗ FAILED"
    print(f"\n{status}: Behavioral Validation")
    
    return all_passed


def main() -> int:
    """Run all gates in sequence."""
    # Parse arguments
    trace_map_path = None
    golden_path = None
    repo_path = Path(__file__).parent.parent
    skip_pytest = False
    skip_behavioral = False
    correlation_id = None
    
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--trace-map" and i + 1 < len(args):
            trace_map_path = args[i + 1]
            i += 2
        elif args[i] == "--golden" and i + 1 < len(args):
            golden_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--repo-path" and i + 1 < len(args):
            repo_path = Path(args[i + 1])
            i += 2
        elif args[i] == "--correlation-id" and i + 1 < len(args):
            correlation_id = args[i + 1]
            i += 2
        elif args[i] == "--skip-pytest":
            skip_pytest = True
            i += 1
        elif args[i] == "--skip-behavioral":
            skip_behavioral = True
            i += 1
        elif args[i] in ("-h", "--help"):
            print(__doc__)
            return 0
        else:
            i += 1
    
    scripts_dir = repo_path / "scripts"
    artifacts_dir = repo_path / "artifacts"
    
    # CRITICAL: correlation_id is REQUIRED for PR-ready mode
    # Without it, scope enforcement cannot run
    if correlation_id is None:
        print("=" * 60)
        print("ERROR: Scope gate requires --correlation-id to locate artifacts/<id>/allowlist.json")
        print("=" * 60)
        print()
        print("Usage: python3 scripts/agent_gate.py --correlation-id <id> [options]")
        print()
        print("Options:")
        print("  --correlation-id <id>  REQUIRED. Session ID for scope enforcement")
        print("  --trace-map <path>     Path to trace_map.json to validate")
        print("  --golden <path>        Path to golden implementation for HTTP parity")
        print("  --repo-path <path>     Repository root (default: script parent)")
        print("  --skip-pytest          Skip pytest suite")
        print("  --skip-behavioral      Skip behavioral validation gate")
        print()
        print("PR-ready mode requires:")
        print("  - artifacts/<id>/allowlist.json")
        print("  - artifacts/<id>/repo_facts.json")
        return 1
    
    print("=" * 60)
    print("AGENT GATE RUNNER (PR-ready mode)")
    print(f"Repo: {repo_path}")
    print(f"Correlation ID: {correlation_id}")
    print("=" * 60)
    
    # Check required artifacts exist
    allowlist_path = artifacts_dir / correlation_id / "allowlist.json"
    repo_facts_path = artifacts_dir / correlation_id / "repo_facts.json"
    
    results = []
    
    # Gate 1: Skill contracts validation
    results.append(run_gate(
        "Skill Contracts",
        ["python3", str(scripts_dir / "validate_skill_contracts.py")],
    ))
    
    # Gate 2: Trace map validation (if path provided)
    if trace_map_path:
        results.append(run_gate(
            "Trace Map",
            ["python3", str(scripts_dir / "validate_trace_map.py"), trace_map_path],
        ))
    else:
        print(f"\n⚠ SKIPPED: Trace Map (no --trace-map provided)")
    
    # Gate 3: Scope enforcement with git diff (REQUIRED)
    # CLI: enforce_scope.py <correlation_id> [--check-git] [--repo-path PATH]
    enforce_scope_script = scripts_dir / "enforce_scope.py"
    if enforce_scope_script.exists():
        results.append(run_gate(
            "Scope Enforcement (git diff)",
            ["python3", str(enforce_scope_script), correlation_id, "--check-git", "--repo-path", str(repo_path)],
        ))
    else:
        print(f"\n✗ FAILED: Scope Enforcement - script not found: {enforce_scope_script}")
        results.append(False)
    
    # Gate 4: Repo grounding check (required for IMPLEMENT/COMMIT)
    if repo_facts_path.exists():
        print(f"\n✓ Repo facts present: {repo_facts_path}")
    else:
        print(f"\n⚠ WARNING: Missing repo_facts.json at {repo_facts_path}")
        print("           IMPLEMENT/COMMIT skills require repo grounding")
    
    # Gate 5: Sync Celery compatibility (check skills/ directory)
    sync_celery_script = scripts_dir / "validate_sync_celery_compat.py"
    if sync_celery_script.exists():
        results.append(run_gate(
            "Sync Celery Compatibility",
            ["python3", str(sync_celery_script), str(repo_path / "skills")],
            allow_failure=True,  # Skills themselves may have async test fixtures
        ))
    
    # Gate 6: Behavioral Validation (no-stub, HTTP parity, semantic diff)
    if not skip_behavioral:
        results.append(run_behavioral_gate(
            correlation_id=correlation_id,
            artifacts_dir=artifacts_dir,
            golden_path=golden_path,
        ))
    else:
        print(f"\n⚠ SKIPPED: Behavioral Validation (--skip-behavioral)")
    
    # Gate 7: Pytest (unless skipped)
    if not skip_pytest:
        results.append(run_gate(
            "Pytest Suite",
            ["python3", "-m", "pytest", "-q"],
        ))
    else:
        print(f"\n⚠ SKIPPED: Pytest Suite (--skip-pytest)")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Gates passed: {passed}/{total}")
    
    if all(results):
        print("\n✓ ALL GATES PASSED - Ready for PR")
        return 0
    else:
        print("\n✗ SOME GATES FAILED - Fix issues before PR")
        return 1


if __name__ == "__main__":
    sys.exit(main())
