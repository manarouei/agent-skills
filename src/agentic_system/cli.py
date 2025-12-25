"""
CLI tool for bounded autonomy features.

Provides terminal access to:
- Context gating
- Code review
- Compliance checking
- Prompt template generation
- Agent execution
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Any

from agentic_system.runtime import ExecutionContext, get_skill_registry, get_agent_registry
from agentic_system.skills.context_gate import ContextGateSkill
from agentic_system.skills.code_review import CodeReviewSkill
from agentic_system.agents.bounded_autonomy import BoundedAutonomyAgent
from agentic_system.observability import setup_logging


def load_template(template_name: str) -> str:
    """Load a prompt template from LLM_TASK_TEMPLATES.md."""
    templates_path = Path(__file__).parent.parent.parent / "docs" / "LLM_TASK_TEMPLATES.md"
    
    if not templates_path.exists():
        return f"Template file not found: {templates_path}"
    
    content = templates_path.read_text()
    
    # Extract template by name
    template_markers = {
        "A0": "## Template A0: Planning + Questions",
        "A1": "## Template A1: Patch + Tests",
        "A1-reliability": "## Template A1: Reliability, Security, or DB",
        "bugfix": "## Template: Quick Bugfix",
        "new-skill": "## Template: New Skill",
        "new-agent": "## Template: New Agent",
        "refactor": "## Template: Refactor",
        "docs": "## Template: Documentation Update"
    }
    
    marker = template_markers.get(template_name)
    if not marker:
        return f"Unknown template: {template_name}. Available: {', '.join(template_markers.keys())}"
    
    # Find template section
    start_idx = content.find(marker)
    if start_idx == -1:
        return f"Template {template_name} not found in file"
    
    # Find next template or end
    end_idx = content.find("\n## Template", start_idx + len(marker))
    if end_idx == -1:
        end_idx = len(content)
    
    template_section = content[start_idx:end_idx]
    
    # Extract just the template code block
    code_start = template_section.find("```")
    if code_start == -1:
        return template_section
    
    code_start += 3
    code_end = template_section.find("```", code_start)
    if code_end == -1:
        return template_section[code_start:]
    
    return template_section[code_start:code_end].strip()


def cmd_prompt(args: argparse.Namespace) -> int:
    """Generate a prompt template."""
    template = load_template(args.template)
    
    # Fill in placeholders if provided
    replacements = {
        "{Describe what you want to accomplish}": args.task or "{Describe what you want to accomplish}",
        "{Describe your request here}": args.task or "{Describe your request here}",
        "{Paste the plan from A0 pass here}": args.plan or "{Paste the plan from A0 pass here}",
        "{List allowed files": f"{{Only these files: {args.files}}}" if args.files else "{List allowed files",
        "{Describe the bug}": args.bug or "{Describe the bug}",
        "{Paste error stacktrace or logs}": args.error or "{Paste error stacktrace or logs}",
        "{Describe the skill's purpose and behavior}": args.purpose or "{Describe the skill's purpose and behavior}",
        "{skill_name and description}": args.name or "{skill_name}",
        "{read-only / idempotent / stateful}": args.side_effects or "{read-only / idempotent / stateful}",
        "{timeout_s}": str(args.timeout) if args.timeout else "{timeout_s}",
        "{Describe the agent's workflow and purpose}": args.purpose or "{Describe the agent's workflow and purpose}",
        "{agent_id}": args.name or "{agent_id}",
        "{list steps the agent will execute}": args.steps or "{list steps}",
    }
    
    for old, new in replacements.items():
        template = template.replace(old, new)
    
    print(template)
    return 0


def cmd_check_compliance(args: argparse.Namespace) -> int:
    """Check P0/P1/P2 compliance on code changes."""
    setup_logging()
    
    # Initialize registries
    skill_registry = get_skill_registry()
    skill_registry.register(CodeReviewSkill())
    
    # Parse file list
    modified_files = args.pr_files.split(',') if args.pr_files else []
    
    if not modified_files:
        print("Error: No files specified. Use --pr-files 'file1.py,file2.py'")
        return 1
    
    # Read diffs
    file_diffs = {}
    for file_path in modified_files:
        path = Path(file_path)
        if path.exists():
            # For simplicity, just read current content
            # In production, would use git diff
            file_diffs[file_path] = path.read_text()
        else:
            print(f"Warning: File not found: {file_path}")
    
    # Create execution context
    context = ExecutionContext(
        trace_id=f"compliance-check-{args.pr_files[:20]}",
        job_id="cli-compliance-check",
        agent_id="cli"
    )
    
    # Execute code review
    try:
        result = skill_registry.execute(
            name="code_review",
            input_data={
                "modified_files": modified_files,
                "file_diffs": file_diffs,
                "planned_files": args.planned_files.split(',') if args.planned_files else None,
                "pr_description": args.pr_description,
                "check_imports": True
            },
            context=context
        )
        
        # Print results
        print("\n" + "="*60)
        print("BOUNDED AUTONOMY COMPLIANCE CHECK")
        print("="*60)
        print(f"\nStatus: {result['compliance_status'].upper()}")
        print(f"Files Modified: {result['total_files_modified']}")
        print(f"Lines Changed: ~{result['total_lines_changed']}")
        
        # P0 Violations
        p0 = result.get('p0_violations', [])
        if p0:
            print(f"\n❌ P0 VIOLATIONS ({len(p0)}) - BLOCKING:")
            for v in p0:
                file_info = f" [{v['file']}]" if v.get('file') else ""
                print(f"  - [{v['rule_id']}]{file_info} {v['message']}")
        
        # P1 Violations
        p1 = result.get('p1_violations', [])
        if p1:
            print(f"\n⚠️  P1 WARNINGS ({len(p1)}):")
            for v in p1:
                file_info = f" [{v['file']}]" if v.get('file') else ""
                print(f"  - [{v['rule_id']}]{file_info} {v['message']}")
        
        # P2 Suggestions
        p2 = result.get('p2_suggestions', [])
        if p2:
            print(f"\n💡 P2 SUGGESTIONS ({len(p2)}):")
            for v in p2:
                print(f"  - [{v['rule_id']}] {v['message']}")
        
        # Recommendations
        recs = result.get('recommendations', [])
        if recs:
            print(f"\nRECOMMENDATIONS:")
            for rec in recs:
                print(f"  - {rec}")
        
        if result['compliance_status'] == 'compliant':
            print("\n✅ All checks passed! Ready to merge.")
            return 0
        elif result['compliance_status'] == 'warnings':
            print("\n⚠️  Has warnings but can proceed with caution.")
            return 0
        else:
            print("\n❌ Has blocking violations. Cannot merge until fixed.")
            return 1
    
    except Exception as e:
        print(f"Error during compliance check: {e}")
        return 1


def cmd_plan(args: argparse.Namespace) -> int:
    """Generate a plan with context gating."""
    setup_logging()
    
    # Initialize registries
    skill_registry = get_skill_registry()
    skill_registry.register(ContextGateSkill())
    
    # Parse visible files
    visible_files = args.files.split(',') if args.files else []
    
    # Create execution context
    context = ExecutionContext(
        trace_id=f"plan-{args.task[:20]}",
        job_id="cli-plan",
        agent_id="cli"
    )
    
    # Build available context - if files specified, they're both visible and modifiable
    available_context = {}
    if visible_files:
        available_context["file_allowlist"] = visible_files
    
    # Execute context gate
    try:
        result = skill_registry.execute(
            name="context_gate",
            input_data={
                "task_description": args.task,
                "visible_files": visible_files,
                "available_context": available_context,
                "max_questions": 5
            },
            context=context
        )
        
        # Print results
        print("\n" + "="*60)
        print("CONTEXT GATE ANALYSIS")
        print("="*60)
        print(f"\nStatus: {result['status'].upper()}")
        print(f"Can Proceed: {'✅ Yes' if result['can_proceed'] else '❌ No'}")
        
        # Questions
        questions = result.get('questions', [])
        if questions:
            print(f"\nQUESTIONS ({len(questions)}):")
            for i, q in enumerate(questions, 1):
                print(f"\n  Q{i} [{q['priority'].upper()}]:")
                print(f"      {q['question']}")
                print(f"      Reason: {q['reason']}")
        
        # Missing context
        missing = result.get('missing_context', [])
        if missing:
            print(f"\nMISSING CONTEXT:")
            for m in missing:
                print(f"  - {m}")
        
        # Assumptions
        assumptions = result.get('assumptions', [])
        if assumptions:
            print(f"\nASSUMPTIONS:")
            for a in assumptions:
                print(f"  - {a}")
        
        # Required files
        required = result.get('required_files', [])
        if required:
            print(f"\nREQUIRED FILES:")
            for f in required:
                print(f"  - {f}")
        
        if result['can_proceed']:
            print("\n✅ Ready to proceed with implementation!")
            return 0
        else:
            print("\n❌ Answer questions before proceeding.")
            return 1
    
    except Exception as e:
        print(f"Error during planning: {e}")
        return 1


def cmd_review(args: argparse.Namespace) -> int:
    """Run bounded autonomy agent in review mode."""
    setup_logging()
    
    # Initialize registries
    skill_registry = get_skill_registry()
    agent_registry = get_agent_registry()
    
    skill_registry.register(CodeReviewSkill())
    skill_registry.register(ContextGateSkill())
    agent_registry.register(BoundedAutonomyAgent())
    
    # Parse files
    modified_files = args.files.split(',') if args.files else []
    
    if not modified_files:
        print("Error: No files specified. Use --files 'file1.py,file2.py'")
        return 1
    
    # Read diffs
    file_diffs = {}
    for file_path in modified_files:
        path = Path(file_path)
        if path.exists():
            file_diffs[file_path] = path.read_text()
    
    # Create execution context
    context = ExecutionContext(
        trace_id=f"review-{args.files[:20]}",
        job_id="cli-review",
        agent_id="bounded_autonomy"
    )
    
    # Execute agent
    try:
        agent = agent_registry.get("bounded_autonomy")
        result = agent.run(
            input_data={
                "mode": "review",
                "modified_files": modified_files,
                "file_diffs": file_diffs,
                "pr_description": args.pr_description
            },
            context=context
        )
        
        # Print results
        print("\n" + "="*60)
        print("BOUNDED AUTONOMY AGENT - REVIEW MODE")
        print("="*60)
        print(f"\n{result['summary']}")
        
        next_steps = result.get('next_steps', [])
        if next_steps:
            print(f"\nNEXT STEPS:")
            for step in next_steps:
                print(step)
        
        return 0 if result['status'] in ['compliant', 'warnings'] else 1
    
    except Exception as e:
        print(f"Error during review: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Bounded Autonomy CLI - Enforce P0/P1/P2 rules",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # prompt command
    prompt_parser = subparsers.add_parser('prompt', help='Generate a prompt template')
    prompt_parser.add_argument('--template', required=True,
                               choices=['A0', 'A1', 'A1-reliability', 'bugfix', 'new-skill', 'new-agent', 'refactor', 'docs'],
                               help='Template name')
    prompt_parser.add_argument('--task', help='Task description')
    prompt_parser.add_argument('--plan', help='Plan file path')
    prompt_parser.add_argument('--files', help='Comma-separated file list')
    prompt_parser.add_argument('--bug', help='Bug description')
    prompt_parser.add_argument('--error', help='Error trace')
    prompt_parser.add_argument('--name', help='Skill/agent name')
    prompt_parser.add_argument('--purpose', help='Purpose description')
    prompt_parser.add_argument('--side-effects', help='Side effects type')
    prompt_parser.add_argument('--timeout', type=int, help='Timeout in seconds')
    prompt_parser.add_argument('--steps', help='Workflow steps')
    
    # check-compliance command
    compliance_parser = subparsers.add_parser('check-compliance', help='Check P0/P1/P2 compliance')
    compliance_parser.add_argument('--pr-files', required=True, help='Comma-separated list of modified files')
    compliance_parser.add_argument('--planned-files', help='Comma-separated list of planned files')
    compliance_parser.add_argument('--pr-description', help='PR description text')
    
    # plan command
    plan_parser = subparsers.add_parser('plan', help='Generate plan with context gating')
    plan_parser.add_argument('--task', required=True, help='Task description')
    plan_parser.add_argument('--files', help='Comma-separated list of visible files')
    
    # review command
    review_parser = subparsers.add_parser('review', help='Review code changes')
    review_parser.add_argument('--files', required=True, help='Comma-separated list of modified files')
    review_parser.add_argument('--pr-description', help='PR description text')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'prompt':
        return cmd_prompt(args)
    elif args.command == 'check-compliance':
        return cmd_check_compliance(args)
    elif args.command == 'plan':
        return cmd_plan(args)
    elif args.command == 'review':
        return cmd_review(args)
    else:
        print(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
