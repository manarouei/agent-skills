"""
Agent Skills CLI - Main entry point.

Provides commands for:
- Running conversion pipelines
- Executing workflows
- Validating gates
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent_skills")


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output")
@click.option("-q", "--quiet", is_flag=True, help="Suppress output")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, quiet: bool):
    """Agent Skills - Pipeline and workflow execution system."""
    ctx.ensure_object(dict)
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet


# ==============================================================================
# Pipeline Commands
# ==============================================================================

@cli.group()
def pipeline():
    """Run conversion pipelines."""
    pass


@pipeline.command("run")
@click.argument("pipeline_name")
@click.option(
    "--correlation-id", "-c",
    required=True,
    help="Unique ID for this pipeline run"
)
@click.option(
    "--source", "-s",
    required=True,
    type=click.Path(exists=True),
    help="Path to source file or directory"
)
@click.option(
    "--config", "-f",
    type=click.Path(exists=True),
    help="Path to pipeline config YAML"
)
@click.option(
    "--dry-run", is_flag=True,
    help="Validate without executing"
)
@click.pass_context
def pipeline_run(
    ctx: click.Context,
    pipeline_name: str,
    correlation_id: str,
    source: str,
    config: Optional[str],
    dry_run: bool,
):
    """
    Run a conversion pipeline.
    
    PIPELINE_NAME: Name of the pipeline (e.g., 'type1-convert')
    
    Examples:
        
        # Convert a TypeScript node
        agent-skills pipeline run type1-convert -c my-run-001 -s ./node.ts
        
        # Dry run with custom config
        agent-skills pipeline run type1-convert -c test-001 -s ./node.ts --dry-run
    """
    from src.agent_skills.pipelines.loader import load_pipeline
    from src.agent_skills.pipelines.runner import PipelineRunner
    from runtime.executor import create_executor
    
    # Determine workspace root
    workspace_root = Path.cwd()
    skills_dir = workspace_root / "skills"
    scripts_dir = workspace_root / "scripts"
    artifacts_dir = workspace_root / "artifacts"
    
    # Ensure artifacts directory exists
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # Load pipeline definition
    config_path = Path(config) if config else Path("configs/pipelines.yaml")
    if not config_path.exists():
        click.echo(f"Error: Config file not found: {config_path}", err=True)
        sys.exit(1)
    
    try:
        pipeline_def = load_pipeline(config_path, pipeline_name)
    except Exception as e:
        click.echo(f"Error loading pipeline: {e}", err=True)
        sys.exit(1)
    
    click.echo(f"Pipeline: {pipeline_def.name}")
    click.echo(f"Steps: {len(pipeline_def.steps)}")
    click.echo(f"Correlation ID: {correlation_id}")
    click.echo(f"Source: {source}")
    
    if dry_run:
        click.echo("\n[DRY RUN] Would execute steps:")
        for step in pipeline_def.get_execution_order():
            click.echo(f"  - {step}")
        return
    
    # Create executor and runner (with skill implementations registered)
    executor = create_executor(
        skills_dir=skills_dir,
        scripts_dir=scripts_dir,
        artifacts_dir=artifacts_dir,
        register_implementations=True,
    )
    
    runner = PipelineRunner(
        executor=executor,
        artifacts_dir=artifacts_dir,
    )
    
    # Prepare inputs for source-ingest skill
    # The skill needs: correlation_id, source_type, evidence (array with path_or_url)
    source_path = Path(source).resolve()
    
    # Extract normalized_name from source path
    # e.g., input_sources/github/ -> github
    normalized_name = source_path.name
    if not normalized_name or normalized_name in (".", ""):
        # Try parent for paths like input_sources/github/
        normalized_name = source_path.parent.name if source_path.parent.name != "input_sources" else source_path.name
    
    # Auto-detect golden nodes from well-known locations
    golden_node_hints = []
    for golden_candidate in [
        "nodepacks/core/nodes.py",
        "src/node_sdk/basenode.py",
    ]:
        if (workspace_root / golden_candidate).exists():
            golden_node_hints.append(golden_candidate)
    
    initial_inputs = {
        "source_path": str(source_path),
        "normalized_name": normalized_name,
        "repo_root": str(workspace_root),
        "golden_node_hints": golden_node_hints,
        "evidence": [
            {"path_or_url": f"input_sources/{normalized_name}", "type": "local_dir"}
        ],
    }
    
    result = runner.run(
        pipeline=pipeline_def,
        correlation_id=correlation_id,
        initial_inputs=initial_inputs,
    )
    
    # Report results
    click.echo(f"\nResult: {result.status.value}")
    click.echo(f"Duration: {result.duration_ms:.2f}ms")
    
    if result.errors:
        click.echo("\nErrors:")
        for err in result.errors:
            click.echo(f"  - {err}")
        sys.exit(1)


@pipeline.command("list")
@click.option(
    "--config", "-f",
    type=click.Path(exists=True),
    default="configs/pipelines.yaml",
    help="Path to pipeline config YAML"
)
def pipeline_list(config: str):
    """List available pipelines."""
    from src.agent_skills.pipelines.loader import load_pipelines
    
    config_path = Path(config)
    if not config_path.exists():
        click.echo(f"No config found at: {config_path}")
        return
    
    pipelines = load_pipelines(config_path)
    
    click.echo("Available pipelines:")
    for p in pipelines:
        click.echo(f"  {p.name}: {len(p.steps)} steps")


# ==============================================================================
# Workflow Commands
# ==============================================================================

@cli.group()
def workflow():
    """Execute workflows."""
    pass


@workflow.command("run")
@click.argument("workflow_file", type=click.Path(exists=True))
@click.option(
    "--input", "-i",
    type=click.Path(exists=True),
    help="Path to input JSON file"
)
@click.option(
    "--output", "-o",
    type=click.Path(),
    help="Path to output JSON file"
)
@click.pass_context
def workflow_run(
    ctx: click.Context,
    workflow_file: str,
    input: Optional[str],
    output: Optional[str],
):
    """
    Execute a workflow from a JSON file.
    
    WORKFLOW_FILE: Path to workflow JSON
    
    Examples:
        
        # Run a workflow
        agent-skills workflow run ./my-workflow.json
        
        # With input and output
        agent-skills workflow run ./workflow.json -i input.json -o output.json
    """
    from src.workflow_runtime import WorkflowDefinition, WorkflowExecutor
    from src.workflow_runtime.executor import DefaultNodeExecutor
    from src.node_registry import NodeRegistry
    
    # Load workflow
    workflow_path = Path(workflow_file)
    with open(workflow_path) as f:
        workflow_data = json.load(f)
    
    workflow = WorkflowDefinition.model_validate(workflow_data)
    
    # Load input data
    input_data = None
    if input:
        with open(input) as f:
            input_data = json.load(f)
            if not isinstance(input_data, list):
                input_data = [input_data]
    
    # Set up executor with registered nodes
    registry = NodeRegistry()
    registry.discover_entry_points()
    
    # Create executor
    node_executor = DefaultNodeExecutor()
    for node_type in registry.list_node_types():
        node_class = registry.get_node_class(node_type)
        if node_class:
            node_executor.register_node(node_type, node_class)
    
    executor = WorkflowExecutor(node_executor=node_executor)
    
    click.echo(f"Executing workflow: {workflow.name}")
    click.echo(f"Nodes: {len(workflow.nodes)}")
    
    # Execute
    result = executor.execute(workflow, input_data)
    
    # Report
    click.echo(f"\nStatus: {result.status.value}")
    click.echo(f"Duration: {result.duration_ms:.2f}ms")
    
    for name, node_result in result.node_results.items():
        status_icon = "✓" if node_result.is_success else "✗"
        click.echo(f"  {status_icon} {name}: {node_result.status.value}")
    
    # Output
    if output:
        with open(output, "w") as f:
            json.dump(result.output_data, f, indent=2)
        click.echo(f"\nOutput saved to: {output}")
    elif result.output_data:
        click.echo("\nOutput:")
        click.echo(json.dumps(result.output_data, indent=2))
    
    if result.is_error:
        sys.exit(1)


# ==============================================================================
# Validate Commands
# ==============================================================================

@cli.group()
def validate():
    """Run validation gates."""
    pass


@validate.command("gate")
@click.option(
    "--correlation-id", "-c",
    required=True,
    help="Correlation ID to validate"
)
@click.option(
    "--skip-pytest", is_flag=True,
    help="Skip pytest gate"
)
@click.pass_context
def validate_gate(ctx: click.Context, correlation_id: str, skip_pytest: bool):
    """
    Run the agent gate for a correlation ID.
    
    Checks:
    - Scope gate (allowlist)
    - Trace map gate
    - Pytest (unless --skip-pytest)
    """
    import subprocess
    
    cmd = ["python", "scripts/agent_gate.py", "--correlation-id", correlation_id]
    if skip_pytest:
        cmd.append("--skip-pytest")
    
    result = subprocess.run(cmd, capture_output=False)
    sys.exit(result.returncode)


@validate.command("trace-map")
@click.argument("trace_map_file", type=click.Path(exists=True))
def validate_trace_map(trace_map_file: str):
    """
    Validate a trace map file.
    
    TRACE_MAP_FILE: Path to trace_map.json
    """
    import subprocess
    
    result = subprocess.run(
        ["python", "scripts/validate_trace_map.py", trace_map_file],
        capture_output=False,
    )
    sys.exit(result.returncode)


@validate.command("sync-celery")
@click.argument("path", type=click.Path(exists=True))
def validate_sync_celery(path: str):
    """
    Check for async/await violations.
    
    PATH: File or directory to check
    """
    import subprocess
    
    result = subprocess.run(
        ["python", "scripts/validate_sync_celery_compat.py", path],
        capture_output=False,
    )
    sys.exit(result.returncode)


# ==============================================================================
# Skill Commands (Executor-First)
# ==============================================================================

@cli.group()
def skill():
    """Run skills through the executor (with all gates enforced)."""
    pass


def _discover_and_register_skills(executor) -> int:
    """Auto-discover all skill implementations and register them."""
    import importlib
    
    skills_dir = Path(__file__).parents[3] / "skills"
    registered = 0
    
    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
        
        skill_name = skill_path.name
        impl_file = skill_path / "impl.py"
        
        if not impl_file.exists():
            continue
        
        try:
            module = importlib.import_module(f"skills.{skill_name}.impl")
            if hasattr(module, "run"):
                executor.register_implementation(skill_name, module.run)
                registered += 1
        except ImportError as e:
            click.echo(f"Warning: Failed to import skills.{skill_name}.impl: {e}", err=True)
        except Exception as e:
            click.echo(f"Warning: Error loading skill {skill_name}: {e}", err=True)
    
    return registered


@skill.command("run")
@click.argument("skill_name")
@click.option(
    "--correlation-id", "-c",
    help="Correlation ID (default: auto-generated)"
)
@click.option(
    "--inputs", "-i",
    default="{}",
    help="JSON string of inputs"
)
@click.option(
    "--artifacts-dir", "-a",
    default="./artifacts",
    help="Artifacts directory"
)
@click.option(
    "--repo-root", "-r",
    default=".",
    help="Repository root for scope checks"
)
@click.pass_context
def skill_run(
    ctx: click.Context,
    skill_name: str,
    correlation_id: Optional[str],
    inputs: str,
    artifacts_dir: str,
    repo_root: str,
):
    """
    Run a skill through the executor.
    
    SKILL_NAME: Name of the skill to run
    
    Examples:
        
        # Run repo-ground skill
        agent-skills skill run repo-ground -i '{"repo_root": "/path/to/repo"}'
        
        # Run with explicit correlation ID
        agent-skills skill run node-scaffold -c my-session -i '{"node_schema": {...}}'
    """
    import uuid
    from runtime.executor import create_executor
    from contracts import ExecutionStatus
    
    # Create executor
    skills_dir = Path(__file__).parents[3] / "skills"
    executor = create_executor(
        skills_dir=skills_dir,
        artifacts_dir=Path(artifacts_dir).resolve(),
        repo_root=Path(repo_root).resolve(),
    )
    
    # Auto-discover and register
    registered = _discover_and_register_skills(executor)
    click.echo(f"Registered {registered} skills", err=True)
    
    # Parse inputs
    try:
        inputs_dict = json.loads(inputs)
    except json.JSONDecodeError as e:
        click.echo(f"Error: Invalid JSON in --inputs: {e}", err=True)
        sys.exit(1)
    
    # Generate correlation ID if not provided
    cid = correlation_id or f"cli-{uuid.uuid4().hex[:8]}"
    inputs_dict["correlation_id"] = cid
    
    click.echo(f"Running skill: {skill_name}")
    click.echo(f"Correlation ID: {cid}")
    
    # Execute through executor (with all gates)
    result = executor.execute(skill_name, inputs_dict, cid)
    
    # Report
    click.echo(f"\nStatus: {result.status.value}")
    click.echo(f"Duration: {result.duration_ms}ms")
    
    if result.errors:
        click.echo("\nErrors:")
        for err in result.errors:
            click.echo(f"  - {err}")
    
    if result.outputs:
        click.echo("\nOutputs:")
        click.echo(json.dumps(result.outputs, indent=2, default=str))
    
    sys.exit(0 if result.status == ExecutionStatus.SUCCESS else 1)


@skill.command("list")
@click.option(
    "--artifacts-dir", "-a",
    default="./artifacts",
    help="Artifacts directory"
)
def skill_list(artifacts_dir: str):
    """List all registered skills with contract info."""
    from runtime.executor import create_executor
    from contracts import FSScope
    
    skills_dir = Path(__file__).parents[3] / "skills"
    executor = create_executor(
        skills_dir=skills_dir,
        artifacts_dir=Path(artifacts_dir).resolve(),
    )
    
    # Auto-discover
    _discover_and_register_skills(executor)
    
    click.echo("\n=== Registered Skills ===\n")
    
    for skill_name in sorted(executor.get_registered_skills()):
        try:
            contract = executor.registry.get(skill_name)
            fs_scope = getattr(contract, "fs_scope", FSScope.TARGET_REPO)
            click.echo(f"  {skill_name}")
            click.echo(f"    version: {contract.version}")
            click.echo(f"    autonomy: {contract.autonomy_level.value}")
            click.echo(f"    fs_scope: {fs_scope.value}")
            click.echo(f"    timeout: {contract.timeout_seconds}s")
            click.echo()
        except Exception as e:
            click.echo(f"  {skill_name} (contract error: {e})")
            click.echo()


# ==============================================================================
# Node Commands
# ==============================================================================

@cli.group()
def node():
    """Node management commands."""
    pass


@node.command("list")
def node_list():
    """List registered nodes."""
    from src.node_registry import NodeRegistry
    from nodepacks.core.manifest import register_nodes
    
    registry = NodeRegistry()
    
    # Register core pack
    manifest, node_classes = register_nodes()
    registry.register_pack(manifest, node_classes)
    
    # Try to discover others
    registry.discover_entry_points()
    
    click.echo("Registered nodes:")
    for node_def in registry.list_nodes():
        click.echo(f"  {node_def.node_type}: {node_def.display_name}")


@node.command("convert")
@click.argument("node_id")
@click.option(
    "--target-repo", "-t",
    default="/home/toni/n8n/back",
    help="Target repository root (default: /home/toni/n8n/back)"
)
@click.option(
    "--artifacts-dir", "-a",
    default="./artifacts",
    help="Artifacts directory (default: ./artifacts)"
)
@click.option(
    "--pipeline", "-p",
    default="convert_node_v1",
    help="Pipeline to run (default: convert_node_v1)"
)
@click.option(
    "--correlation-id", "-c",
    help="Correlation ID (default: auto-generated)"
)
@click.option(
    "--dry-run", is_flag=True,
    help="Validate pipeline without executing"
)
@click.option(
    "--keep-going", is_flag=True,
    help="Continue on step failures"
)
@click.option(
    "--json-summary", is_flag=True,
    help="Output JSON summary to artifacts/{cid}/reports/pipeline_summary.json"
)
@click.option(
    "--apply", "apply_changes", is_flag=True,
    help="Apply changes to target repository (default: dry-run stops at validation)"
)
@click.option(
    "--run-tests", is_flag=True,
    help="Run smoke tests after applying changes (requires --apply)"
)
@click.pass_context
def node_convert(
    ctx: click.Context,
    node_id: str,
    target_repo: str,
    artifacts_dir: str,
    pipeline: str,
    correlation_id: Optional[str],
    dry_run: bool,
    keep_going: bool,
    json_summary: bool,
    apply_changes: bool,
    run_tests: bool,
):
    """
    Convert an n8n node to Python using a pipeline.
    
    NODE_ID: The node identifier (e.g., 'bitly', 'slack', 'github')
    
    This command runs the conversion pipeline through SkillExecutor with
    all gates enforced.
    
    Pipeline stages:
      Steps 1-7: Core conversion (always runs)
      Steps 8-9: Package and validate (always runs)
      Step 10:   Apply to target repo (only with --apply)
      Step 11:   Smoke test (only with --apply --run-tests)
    
    Examples:
        
        # Basic conversion (dry-run by default - no repo changes)
        python main.py node convert bitly
        
        # With JSON output
        python main.py node convert bitly --json-summary
        
        # Apply changes to target repository
        python main.py node convert bitly --apply
        
        # Apply and run smoke tests
        python main.py node convert bitly --apply --run-tests
        
        # Validate pipeline without executing anything
        python main.py node convert bitly --dry-run
    """
    import uuid
    from pathlib import Path
    from runtime.executor import create_executor
    from src.agent_skills.pipelines import (
        get_builtin_pipelines,
        PipelineRunner,
        CANONICAL_ARTIFACT_DIRS,
    )
    
    # Generate correlation ID if not provided
    cid = correlation_id or f"node-{node_id}-{uuid.uuid4().hex[:8]}"
    
    # Resolve paths
    artifacts_path = Path(artifacts_dir).resolve()
    target_repo_path = Path(target_repo).resolve()
    skills_dir = Path(__file__).parents[3] / "skills"
    scripts_dir = Path(__file__).parents[3] / "scripts"
    
    # Get pipeline definition
    builtin_pipelines = get_builtin_pipelines()
    if pipeline not in builtin_pipelines:
        click.echo(f"Error: Unknown pipeline '{pipeline}'", err=True)
        click.echo(f"Available: {list(builtin_pipelines.keys())}", err=True)
        sys.exit(1)
    
    pipeline_def = builtin_pipelines[pipeline]
    
    click.echo(f"=== Node Conversion ===")
    click.echo(f"Node ID:        {node_id}")
    click.echo(f"Pipeline:       {pipeline_def.name}")
    click.echo(f"Correlation ID: {cid}")
    click.echo(f"Target Repo:    {target_repo_path}")
    click.echo(f"Artifacts:      {artifacts_path / cid}")
    click.echo(f"Steps:          {len(pipeline_def.steps)}")
    
    if dry_run:
        click.echo(f"\n[DRY RUN MODE]")
    
    # Create executor with target_repo_root for NoTargetRepoMutationGuard
    executor = create_executor(
        skills_dir=skills_dir,
        scripts_dir=scripts_dir,
        artifacts_dir=artifacts_path,
        target_repo_root=target_repo_path,
        register_implementations=True,
    )
    
    # Create pipeline runner
    runner = PipelineRunner(
        executor=executor,
        artifacts_dir=artifacts_path,
        dry_run=dry_run,
        keep_going=keep_going,
    )
    
    # Set up progress callbacks
    def on_step_start(step_name: str, skill_name: str):
        click.echo(f"\n▶ Running: {step_name} ({skill_name})")
    
    def on_step_complete(step_name: str, result):
        status_icon = "✓" if result.status.value in ("completed", "success") else "✗"
        click.echo(f"  {status_icon} {step_name}: {result.status.value}")
        if result.errors:
            for err in result.errors[:3]:  # Limit error output
                click.echo(f"    Error: {err}")
    
    runner.on_step_start(on_step_start)
    runner.on_step_complete(on_step_complete)
    
    # Warn if --run-tests without --apply
    if run_tests and not apply_changes:
        click.echo("\nWarning: --run-tests requires --apply to have any effect")
    
    # Prepare initial inputs
    initial_inputs = {
        "raw_node_name": node_id,
        "node_id": node_id,
        "repo_root": str(target_repo_path),
        "target_repo_root": str(target_repo_path),
        "artifacts_dir": str(artifacts_path),
        # Gate flags for apply pipeline (steps 10-11)
        "apply": apply_changes,
        "run_tests": run_tests and apply_changes,  # Only run tests if applying
    }
    
    click.echo(f"\n=== Execution ===")
    if apply_changes:
        click.echo(f"Mode: APPLY (will modify target repository)")
        if run_tests:
            click.echo(f"      + Smoke tests enabled")
    else:
        click.echo(f"Mode: DRY-RUN (package and validate only, no repo changes)")
    
    # Run pipeline
    result = runner.run(
        pipeline=pipeline_def,
        correlation_id=cid,
        initial_inputs=initial_inputs,
    )
    
    # Report results
    click.echo(f"\n=== Results ===")
    click.echo(f"Status:   {result.status.value}")
    click.echo(f"Duration: {result.duration_ms}ms")
    click.echo(f"Steps:    {len([s for s in result.steps if s.status.value in ('completed', 'success')])} completed, "
               f"{len([s for s in result.steps if s.status.value == 'failed'])} failed, "
               f"{len([s for s in result.steps if s.status.value == 'skipped'])} skipped")
    
    if result.errors:
        click.echo(f"\nPipeline errors:")
        for err in result.errors:
            click.echo(f"  - {err}")
    
    # Save JSON summary if requested
    if json_summary:
        summary_path = artifacts_path / cid / "reports" / "pipeline_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Build detailed summary
        summary = {
            "pipeline_name": result.pipeline_name,
            "correlation_id": result.correlation_id,
            "status": result.status.value,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_ms": result.duration_ms,
            "node_id": node_id,
            "target_repo": str(target_repo_path),
            "artifacts_dir": str(artifacts_path / cid),
            "steps": [
                {
                    "name": s.step_name,
                    "skill": s.skill_name,
                    "status": s.status.value,
                    "duration_ms": s.duration_ms,
                    "errors": s.errors,
                    "artifacts_produced": s.artifacts_produced,
                }
                for s in result.steps
            ],
            "errors": result.errors,
        }
        
        summary_path.write_text(json.dumps(summary, indent=2))
        click.echo(f"\nJSON summary: {summary_path}")
    
    # Exit with appropriate code
    sys.exit(0 if result.status.value in ("completed", "success") else 1)


# ==============================================================================
# Entry Point
# ==============================================================================

# Alias for compatibility
app = cli


def main():
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
