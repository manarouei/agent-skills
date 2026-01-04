#!/usr/bin/env python3
"""
report_gaps.py - Script E: Compare skill contracts vs KB coverage

Analyzes the knowledge base coverage against skill requirements:
- Parses skill SKILL.md files for required pattern categories
- Compares against current KB entries
- Identifies coverage gaps
- Produces gap report for prioritization

Output: Gap analysis report in artifacts/<run_id>/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.kb.candidates import MiningRunManifest
from runtime.kb.loader import CANONICAL_CATEGORIES, KnowledgeBase, normalize_category


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class SkillRequirement:
    """KB pattern requirement from a skill."""
    skill_name: str
    category: str
    description: str
    priority: str = "medium"  # high, medium, low
    source_file: str = ""
    line_number: int = 0


@dataclass
class KBCoverage:
    """Coverage information for a KB category."""
    category: str
    pattern_count: int
    pattern_names: list[str] = field(default_factory=list)
    skills_requiring: list[str] = field(default_factory=list)
    gap_score: float = 0.0  # 0 = fully covered, 1 = no coverage


@dataclass
class GapReport:
    """Overall gap analysis report."""
    run_id: str
    timestamp: str
    skills_analyzed: int
    categories_analyzed: int
    total_requirements: int
    coverage_summary: dict[str, KBCoverage]
    gaps: list[dict[str, Any]]
    recommendations: list[str]


# ---------------------------------------------------------------------------
# Skill Contract Parsing
# ---------------------------------------------------------------------------


def parse_skill_contract(skill_dir: Path) -> list[SkillRequirement]:
    """Parse SKILL.md for KB pattern requirements."""
    requirements: list[SkillRequirement] = []
    
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return requirements
    
    content = skill_md.read_text(encoding="utf-8")
    skill_name = skill_dir.name
    
    # Parse YAML frontmatter for explicit requirements
    frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if frontmatter_match:
        frontmatter = frontmatter_match.group(1)
        
        # Look for kb_requirements in frontmatter
        kb_req_match = re.search(
            r'kb_requirements:\s*\n((?:\s+-.*\n)*)',
            frontmatter,
        )
        if kb_req_match:
            for line in kb_req_match.group(1).strip().split('\n'):
                line = line.strip()
                if line.startswith('-'):
                    category = line[1:].strip()
                    if category in CANONICAL_CATEGORIES:
                        requirements.append(SkillRequirement(
                            skill_name=skill_name,
                            category=category,
                            description=f"Explicit requirement in {skill_name}",
                            priority="high",
                            source_file=str(skill_md),
                        ))
    
    # Parse content for implicit requirements
    # Look for mentions of KB categories in description
    content_lower = content.lower()
    
    # Auth patterns
    if any(word in content_lower for word in ["credential", "authentication", "auth", "api key", "oauth"]):
        requirements.append(SkillRequirement(
            skill_name=skill_name,
            category="auth",
            description="Skill handles authentication or credentials",
            priority="medium",
            source_file=str(skill_md),
        ))
    
    # Pagination patterns
    if any(word in content_lower for word in ["pagination", "paginate", "cursor", "offset", "page"]):
        requirements.append(SkillRequirement(
            skill_name=skill_name,
            category="pagination",
            description="Skill handles paginated data",
            priority="medium",
            source_file=str(skill_md),
        ))
    
    # TypeScript to Python patterns
    if any(word in content_lower for word in ["typescript", "convert", "transform", "ts_to_python"]):
        requirements.append(SkillRequirement(
            skill_name=skill_name,
            category="ts_to_python",
            description="Skill converts TypeScript to Python",
            priority="medium",
            source_file=str(skill_md),
        ))
    
    # Service quirks
    if any(word in content_lower for word in ["api", "service", "endpoint", "http", "request"]):
        requirements.append(SkillRequirement(
            skill_name=skill_name,
            category="service_quirk",
            description="Skill interacts with external services",
            priority="low",
            source_file=str(skill_md),
        ))
    
    # Deduplicate by category
    seen_categories: set[str] = set()
    unique_requirements: list[SkillRequirement] = []
    for req in requirements:
        if req.category not in seen_categories:
            seen_categories.add(req.category)
            unique_requirements.append(req)
    
    return unique_requirements


def scan_skills_directory(skills_dir: Path) -> list[SkillRequirement]:
    """Scan all skill directories for requirements."""
    all_requirements: list[SkillRequirement] = []
    
    if not skills_dir.exists():
        return all_requirements
    
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir() and not skill_dir.name.startswith("_"):
            requirements = parse_skill_contract(skill_dir)
            all_requirements.extend(requirements)
    
    return all_requirements


# ---------------------------------------------------------------------------
# KB Coverage Analysis
# ---------------------------------------------------------------------------


def analyze_kb_coverage(kb: KnowledgeBase) -> dict[str, KBCoverage]:
    """Analyze coverage of each KB category."""
    coverage: dict[str, KBCoverage] = {}
    
    for category in CANONICAL_CATEGORIES:
        patterns = kb.get_patterns_by_category(category)
        coverage[category] = KBCoverage(
            category=category,
            pattern_count=len(patterns),
            pattern_names=[p.name for p in patterns],
        )
    
    return coverage


def calculate_gaps(
    coverage: dict[str, KBCoverage],
    requirements: list[SkillRequirement],
) -> list[dict[str, Any]]:
    """Calculate gaps between requirements and coverage."""
    gaps: list[dict[str, Any]] = []
    
    # Group requirements by category
    by_category: dict[str, list[SkillRequirement]] = {}
    for req in requirements:
        by_category.setdefault(req.category, []).append(req)
    
    for category, cat_requirements in by_category.items():
        cat_coverage = coverage.get(category)
        
        if cat_coverage is None:
            # Category not in KB at all
            gaps.append({
                "category": category,
                "severity": "critical",
                "pattern_count": 0,
                "skills_requiring": [r.skill_name for r in cat_requirements],
                "requirement_count": len(cat_requirements),
                "description": f"Category '{category}' has no patterns in KB",
            })
            continue
        
        # Update coverage with requiring skills
        cat_coverage.skills_requiring = [r.skill_name for r in cat_requirements]
        
        # Calculate gap score
        if cat_coverage.pattern_count == 0:
            cat_coverage.gap_score = 1.0
            severity = "critical"
        elif cat_coverage.pattern_count < 3:
            cat_coverage.gap_score = 0.7
            severity = "high"
        elif cat_coverage.pattern_count < 5:
            cat_coverage.gap_score = 0.4
            severity = "medium"
        else:
            cat_coverage.gap_score = 0.1
            severity = "low"
        
        if cat_coverage.gap_score > 0.3:
            gaps.append({
                "category": category,
                "severity": severity,
                "pattern_count": cat_coverage.pattern_count,
                "skills_requiring": cat_coverage.skills_requiring,
                "requirement_count": len(cat_requirements),
                "gap_score": cat_coverage.gap_score,
                "description": f"Category '{category}' has {cat_coverage.pattern_count} patterns, {len(cat_requirements)} skills need it",
            })
    
    # Sort by severity (critical first)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    gaps.sort(key=lambda g: (severity_order.get(g["severity"], 4), -g.get("requirement_count", 0)))
    
    return gaps


def generate_recommendations(
    gaps: list[dict[str, Any]],
    coverage: dict[str, KBCoverage],
) -> list[str]:
    """Generate actionable recommendations from gaps."""
    recommendations: list[str] = []
    
    critical_gaps = [g for g in gaps if g["severity"] == "critical"]
    high_gaps = [g for g in gaps if g["severity"] == "high"]
    
    if critical_gaps:
        recommendations.append(
            f"CRITICAL: {len(critical_gaps)} categories have no KB patterns. "
            f"Run mining scripts for: {', '.join(g['category'] for g in critical_gaps)}"
        )
    
    if high_gaps:
        recommendations.append(
            f"HIGH: {len(high_gaps)} categories need more patterns. "
            f"Focus on: {', '.join(g['category'] for g in high_gaps)}"
        )
    
    # Specific recommendations by category
    for gap in gaps[:5]:  # Top 5 gaps
        category = gap["category"]
        skills = gap.get("skills_requiring", [])
        
        if category == "auth":
            recommendations.append(
                f"Run: python scripts/kb/mine_back_credentials.py --credentials-dir <path> "
                f"(required by: {', '.join(skills[:3])})"
            )
        elif category == "pagination":
            recommendations.append(
                f"Run: python scripts/kb/mine_back_nodes.py --nodes-dir <path> "
                f"(look for pagination patterns, required by: {', '.join(skills[:3])})"
            )
        elif category == "ts_to_python":
            recommendations.append(
                f"Run: python scripts/kb/mine_trace_maps.py --artifacts-dir artifacts/ "
                f"(required by: {', '.join(skills[:3])})"
            )
    
    if not recommendations:
        recommendations.append("KB coverage is adequate for current skill requirements.")
    
    return recommendations


# ---------------------------------------------------------------------------
# Main Analysis Logic
# ---------------------------------------------------------------------------


def analyze_gaps(
    skills_dir: Path,
    kb_dir: Path,
    output_dir: Path,
    run_id: str,
    verbose: bool = False,
) -> tuple[GapReport, MiningRunManifest]:
    """
    Analyze gaps between skill requirements and KB coverage.
    
    Args:
        skills_dir: Path to skills/ directory
        kb_dir: Path to runtime/kb/ directory
        output_dir: Path to output artifacts directory
        run_id: Unique identifier for this analysis run
        verbose: Print verbose output
        
    Returns:
        Tuple of (gap_report, manifest)
    """
    errors: list[str] = []
    files_processed: list[str] = []
    
    if verbose:
        print(f"Analyzing gaps...")
        print(f"Skills dir: {skills_dir}")
        print(f"KB dir: {kb_dir}")
    
    # Scan skill requirements
    if verbose:
        print("\nScanning skill contracts...")
    
    requirements = scan_skills_directory(skills_dir)
    
    if verbose:
        print(f"Found {len(requirements)} requirements from skills")
        for req in requirements:
            print(f"  - {req.skill_name}: {req.category} ({req.priority})")
    
    # Track processed skill files
    for skill_dir in skills_dir.iterdir():
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            files_processed.append(str(skill_md))
    
    # Load KB
    if verbose:
        print("\nLoading knowledge base...")
    
    try:
        kb = KnowledgeBase(kb_dir)
        kb_loaded = True
    except Exception as e:
        errors.append(f"Failed to load KB: {e}")
        kb_loaded = False
        kb = None
    
    if kb_loaded and kb:
        if verbose:
            print(f"KB loaded with {sum(len(kb.get_patterns_by_category(c)) for c in CANONICAL_CATEGORIES)} patterns")
        
        # Analyze coverage
        coverage = analyze_kb_coverage(kb)
        
        if verbose:
            print("\nCoverage by category:")
            for cat, cov in coverage.items():
                print(f"  - {cat}: {cov.pattern_count} patterns")
    else:
        # Create empty coverage for gap analysis
        coverage = {
            cat: KBCoverage(category=cat, pattern_count=0)
            for cat in CANONICAL_CATEGORIES
        }
    
    # Calculate gaps
    if verbose:
        print("\nCalculating gaps...")
    
    gaps = calculate_gaps(coverage, requirements)
    
    if verbose:
        print(f"Found {len(gaps)} gaps")
        for gap in gaps:
            print(f"  - {gap['category']}: {gap['severity']} ({gap['description']})")
    
    # Generate recommendations
    recommendations = generate_recommendations(gaps, coverage)
    
    # Create report
    report = GapReport(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        skills_analyzed=len(set(r.skill_name for r in requirements)),
        categories_analyzed=len(CANONICAL_CATEGORIES),
        total_requirements=len(requirements),
        coverage_summary={k: asdict(v) for k, v in coverage.items()},
        gaps=gaps,
        recommendations=recommendations,
    )
    
    # Create manifest
    manifest = MiningRunManifest(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        script_name="report_gaps.py",
        inputs=[str(skills_dir), str(kb_dir)],
        candidate_count=0,  # This script doesn't generate candidates
        git_commit=None,
    )
    
    return report, manifest


def write_outputs(
    report: GapReport,
    manifest: MiningRunManifest,
    output_dir: Path,
    verbose: bool = False,
) -> None:
    """Write gap report and manifest to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest.to_json())
    if verbose:
        print(f"Wrote manifest: {manifest_path}")
    
    # Write report JSON
    report_path = output_dir / "gap_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, indent=2, default=str)
    if verbose:
        print(f"Wrote report: {report_path}")
    
    # Write summary markdown
    summary_path = output_dir / "summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# KB Gap Analysis: {report.run_id}\n\n")
        f.write(f"**Timestamp:** {report.timestamp}\n")
        f.write(f"**Skills Analyzed:** {report.skills_analyzed}\n")
        f.write(f"**Categories Analyzed:** {report.categories_analyzed}\n")
        f.write(f"**Total Requirements:** {report.total_requirements}\n\n")
        
        f.write("## Coverage Summary\n\n")
        f.write("| Category | Patterns | Skills Requiring | Gap Score |\n")
        f.write("|----------|----------|------------------|----------|\n")
        for cat, cov in report.coverage_summary.items():
            skills = ", ".join(cov.get("skills_requiring", [])[:3])
            if len(cov.get("skills_requiring", [])) > 3:
                skills += "..."
            gap = cov.get("gap_score", 0)
            gap_indicator = "🔴" if gap > 0.7 else "🟡" if gap > 0.3 else "🟢"
            f.write(f"| {cat} | {cov.get('pattern_count', 0)} | {skills} | {gap_indicator} {gap:.1%} |\n")
        f.write("\n")
        
        if report.gaps:
            f.write("## Gaps\n\n")
            for gap in report.gaps:
                severity_icon = {
                    "critical": "🔴",
                    "high": "🟠",
                    "medium": "🟡",
                    "low": "🟢",
                }.get(gap["severity"], "⚪")
                f.write(f"### {severity_icon} {gap['category']} ({gap['severity']})\n\n")
                f.write(f"{gap['description']}\n\n")
                if gap.get("skills_requiring"):
                    f.write(f"**Required by:** {', '.join(gap['skills_requiring'])}\n\n")
        
        f.write("## Recommendations\n\n")
        for i, rec in enumerate(report.recommendations, 1):
            f.write(f"{i}. {rec}\n")
    
    if verbose:
        print(f"Wrote summary: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze gaps between skill requirements and KB coverage"
    )
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path("skills"),
        help="Path to skills/ directory (default: skills/)",
    )
    parser.add_argument(
        "--kb-dir",
        type=Path,
        default=Path("runtime/kb"),
        help="Path to runtime/kb/ directory (default: runtime/kb/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: artifacts/<run_id>/)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        help="Analysis run ID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Generate run ID if not provided
    run_id = args.run_id or f"gap-analysis-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Set output directory
    output_dir = args.output_dir or Path("artifacts") / run_id

    if args.verbose:
        print(f"Gap analysis run: {run_id}")
        print(f"Skills dir: {args.skills_dir}")
        print(f"KB dir: {args.kb_dir}")
        print(f"Output dir: {output_dir}")
        print()

    # Run analysis
    report, manifest = analyze_gaps(
        skills_dir=args.skills_dir,
        kb_dir=args.kb_dir,
        output_dir=output_dir,
        run_id=run_id,
        verbose=args.verbose,
    )

    # Write outputs
    write_outputs(report, manifest, output_dir, verbose=args.verbose)

    # Print summary
    print(f"\nGap analysis complete")
    print(f"  Skills analyzed: {report.skills_analyzed}")
    print(f"  Categories: {report.categories_analyzed}")
    print(f"  Gaps found: {len(report.gaps)}")
    
    critical = len([g for g in report.gaps if g["severity"] == "critical"])
    if critical > 0:
        print(f"  ⚠️  Critical gaps: {critical}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
