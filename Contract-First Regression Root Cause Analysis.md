  
Contract-First Regression Root Cause Analysis

1\. Root Cause  
The regression stems from a fundamental architectural inversion: the pipeline treats contracts and schemas as code generation sources rather than validation constraints.

Observable evidence:

1.1 Schema-Driven Generation Replaces Code Conversion  
The impl.py operates in two conflicting modes:

Lines 170-190: Attempts to extract code from TypeScript source (\_extract\_execute\_body)  
Lines 218-226: Falls back to schema-derived properties when extraction fails  
The failure occurs because:

\# From impl.py lines 216-225schema\_params \= node\_schema.get("properties", {}).get("parameters", \[\])if schema\_params:    properties \= schema\_params  \# \<-- Uses schema, not source codeelse:    properties \= \_extract\_properties(main\_node\_ts)

When schema-infer produces a schema (even a low-quality one), code-convert prefers it over actual TypeScript extraction.

1.2 Stub Generation as Default Path  
When \_extract\_operations() fails to find API call patterns (lines 873-875):

else:  
    \# No API call found \- add placeholder  
    lines.append("\# TODO: Implement API call")  
    lines.append("response \= {}")

The broken output shows 20+ \# TODO: Implement API call stubs where the working code has actual HTTP calls with URL construction, authentication, and pagination.

1.3 Validator Blindness to Behavioral Content  
The validator.py validates structural completeness (schemas, side-effects declared, timeouts) but has zero checks for:

Actual HTTP call presence  
Non-stub method implementations  
Operation-to-endpoint mapping parity

2\. Failure Classification  
2.1 SEMANTIC ERASURE ✓  
Definition: Logic that existed in source is absent in output.

Evidence:

Working node has \_api\_request() with:  
quote() for URL encoding (line 152, 169\)  
Auth header construction (lines 391-413)  
Pagination logic (lines 330-386)  
Broken node has:  
Hardcoded url \= f"https://api.github.com/repos/test-owner/test-repo{endpoint}" (line 434-435)  
No auth headers  
response \= {} stubs

2.2 CONTRACT OVER-DOMINANCE ✓  
Definition: Contract-derived structure overwrites source-derived behavior.

Evidence:  
The node\_schema from schema-infer generates a generic CRUD template (create/delete/get/getAll/update) for every resource, regardless of what the actual TypeScript source implements:

\# Broken output \- generic operations  
{"name": "Create", "value": "create", "description": "Create workflow"},  
{"name": "Delete", "value": "delete", "description": "Delete workflow"},

\# Working code \- actual operations  
{"name": "Disable", "value": "disable", "description": "Disable a workflow"},  
{"name": "Dispatch", "value": "dispatch", "description": "Dispatch a workflow event"},  
{"name": "Get Usage", "value": "getUsage", "description": "Get the usage of a workflow"},

The schema's inferred operations (CRUD template) replaced the actual operations from TypeScript.

2.3 GENERATOR COLLAPSE TO SCAFFOLDING ✓  
Definition: Generator produces scaffolds when it should produce implementations.

Evidence:  
impl.py is designed to produce stubs (lines 90-95):

result \= {  
    "status": "not\_implemented",  
    "message": f"Operation '{operation}' not yet implemented",  
}

But code-convert falls back to scaffold-like output when:

TypeScript extraction fails (regex misses complex patterns)  
Schema is present but extraction is not  
The pipeline lacks a gate that says: "If source type is TYPE1 (code), scaffold output is always wrong."

2.4 VALIDATOR BLINDNESS TO BEHAVIOR ✓  
Definition: Validators check form, not function.

Evidence from node\_contract.py lines 24-33:

\# Hard-Fail Invariants (ANY failure \= automatic rejection):  
\# \- No machine-readable contract manifest  
\# \- Input/output schema cannot be validated  
\# \- Undeclared side-effects  
\# \- No hard execution timeout  
\# \- Retry policy without idempotency semantics  
\# \- Placeholder endpoints (example.com, TODO, empty DSN)  \<-- Only checks endpoints, not method bodies

The validator should reject output with:

response \= {} in operation handlers  
\# TODO: Implement comments  
Missing URL construction from parameters

3\. Corrected Pipeline Design  
3.1 Source of Truth Hierarchy

GROUND TRUTH (for TYPE1/code sources):  
┌─────────────────────────────────────────────────┐  
│ 1\. BEHAVIORAL GROUND TRUTH: Existing Python     │  
│    implementations (avidflow-back/nodes/\*.py)   │  
├─────────────────────────────────────────────────┤  
│ 2\. SOURCE TRUTH: TypeScript source code         │  
│    (input\_sources/\*/node.ts)                    │  
├─────────────────────────────────────────────────┤  
│ 3\. SCHEMA (constraints only): Contract YAML     │  
│    \- Declares expected operations (validation)  │  
│    \- Does NOT generate implementations          │  
└─────────────────────────────────────────────────┘

3.2 Revised Skill Pipeline

┌──────────────────────────────────────────────────────────────────────────────┐  
│                              PHASE 1: ANALYSIS                               │  
├──────────────────────────────────────────────────────────────────────────────┤  
│ source-ingest ──► source-classify ──► schema-infer                           │  
│                                            │                                 │  
│                                            ▼                                 │  
│                                   inferred\_schema.json                       │  
│                                   (operations, parameters)                   │  
└──────────────────────────────────────────────────────────────────────────────┘  
                                            │  
                                            ▼  
┌──────────────────────────────────────────────────────────────────────────────┐  
│                        PHASE 2: GOLDEN TRUTH EXTRACTION                      │  
├──────────────────────────────────────────────────────────────────────────────┤  
│ NEW SKILL: golden-extract                                                    │  
│   Input: correlation\_id, node\_type                                           │  
│   Action: Locate existing working implementation                             │  
│   Output: golden\_impl (dict of method\_name → code\_body)                      │  
│                                                                              │  
│ IF golden\_impl exists:                                                       │  
│   ├─ PASS THROUGH golden\_impl to code-convert as source\_of\_truth            │  
│   └─ Schema validates against golden\_impl (not vice versa)                   │  
│ ELSE:                                                                        │  
│   └─ Proceed with TYPE1 TypeScript extraction                                │  
└──────────────────────────────────────────────────────────────────────────────┘  
                                            │  
                                            ▼  
┌──────────────────────────────────────────────────────────────────────────────┐  
│                          PHASE 3: CODE CONVERSION                            │  
├──────────────────────────────────────────────────────────────────────────────┤  
│ code-convert (MODIFIED)                                                      │  
│   Input: source\_ts, node\_schema (validation), golden\_impl (if exists)        │  
│                                                                              │  
│   Priority:                                                                  │  
│   1\. golden\_impl method bodies (copy, don't regenerate)                      │  
│   2\. TypeScript extraction (deterministic regex/AST)                         │  
│   3\. FAIL if neither produces implementation                                 │  
│                                                                              │  
│   FORBIDDEN:                                                                 │  
│   \- Generating stub methods when source has implementation                   │  
│   \- Using schema to generate method bodies                                   │  
│   \- Outputting "\# TODO" in operation handlers                                │  
└──────────────────────────────────────────────────────────────────────────────┘  
                                            │  
                                            ▼  
┌──────────────────────────────────────────────────────────────────────────────┐  
│                       PHASE 4: BEHAVIORAL VALIDATION                         │  
├──────────────────────────────────────────────────────────────────────────────┤  
│ NEW SKILL: behavioral-validate                                               │  
│   Compares: generated\_node vs golden\_impl (or vs source\_ts)                  │  
│                                                                              │  
│   Checks:                                                                    │  
│   \- Operation coverage: every operation in golden has implementation         │  
│   \- HTTP call parity: every handler with HTTP in source has HTTP in output   │  
│   \- No stub detection: FAIL if "TODO: Implement" appears in handlers         │  
│   \- URL construction: endpoint patterns match source                         │  
│   \- Auth pattern: credential access matches source                           │  
│                                                                              │  
│   Output: behavioral\_diff.json with pass/fail and specific mismatches        │  
└──────────────────────────────────────────────────────────────────────────────┘

3.3 Contract Role Redefinition  
Contracts MUST be:

Validation checkpoints: "Does output declare these operations?"  
Constraint envelopes: "Timeout must exist, side-effects must be declared"  
NOT code generators: Contracts never produce method bodies  
Schema-infer output changes:

\# OLD (generates code from schema)  
operations:  
  \- name: create  
    description: "Create workflow"  \# Generic, destroys source semantics

\# NEW (validates against source)  
operations:  
  \- name: dispatch  
    source\_evidence: "line 342 of GitHub.node.ts"  
    http\_method: POST  
    endpoint\_pattern: "/repos/{owner}/{repo}/actions/workflows/{workflow\_id}/dispatches"  
    implementation\_required: true  \# Validator enforces this

4\. Mechanical Safeguards  
4.1 No-Stub Gate (scripts/validate\_no\_stubs.py)

\#\!/usr/bin/env python3  
"""Reject any converted node with stub implementations."""

import re  
import sys  
from pathlib import Path

STUB\_PATTERNS \= \[  
    r'\#\\s\*TODO:\\s\*Implement',  
    r'response\\s\*=\\s\*\\{\\s\*\\}',  
    r'raise\\s+NotImplementedError',  
    r'pass\\s\*$',  \# Empty method body  
\]

def validate\_no\_stubs(node\_file: Path) \-\> bool:  
    content \= node\_file.read\_text()  
    violations \= \[\]  
      
    for i, line in enumerate(content.split('\\n'), 1):  
        for pattern in STUB\_PATTERNS:  
            if re.search(pattern, line):  
                violations.append(f"Line {i}: {line.strip()}")  
      
    if violations:  
        print(f"❌ STUB VIOLATIONS in {node\_file.name}:")  
        for v in violations:  
            print(f"  {v}")  
        return False  
    return True

Integration: Add to agent\_gate.py as mandatory check.

4.2 Side-Effect Parity Check  
def validate\_side\_effect\_parity(source\_ts: str, generated\_py: str) \-\> bool:  
    """Every HTTP call in source must have HTTP call in output."""  
      
    \# Count HTTP calls in source  
    source\_http\_patterns \= \[  
        r'\\.request\\(',  
        r'ApiRequest\\.call',  
        r'fetch\\(',  
    \]  
    source\_http\_count \= sum(  
        len(re.findall(p, source\_ts)) for p in source\_http\_patterns  
    )  
      
    \# Count HTTP calls in output  
    output\_http\_patterns \= \[  
        r'requests\\.(get|post|put|delete|patch|request)\\(',  
        r'self\\.\_api\_request\\(',  
        r'self\\.\_http\_request\\(',  
    \]  
    output\_http\_count \= sum(  
        len(re.findall(p, generated\_py)) for p in output\_http\_patterns  
    )  
      
    if source\_http\_count \> 0 and output\_http\_count \== 0:  
        print(f"❌ HTTP PARITY FAIL: Source has {source\_http\_count} HTTP calls, output has 0")  
        return False  
    return True

4.3 Semantic Diff Against Golden

def semantic\_diff(golden\_py: str, generated\_py: str) \-\> Dict\[str, Any\]:  
    """Compare operation implementations between golden and generated."""  
      
    def extract\_operation\_methods(code: str) \-\> Dict\[str, str\]:  
        """Extract \_resource\_operation methods and their bodies."""  
        pattern \= r'def (\_\\w+\_\\w+)\\(self\[^)\]\*\\):\[^}\]+?(?=\\n    def |\\Z)'  
        methods \= {}  
        for match in re.finditer(pattern, code, re.DOTALL):  
            name \= match.group(1)  
            body \= match.group(0)  
            methods\[name\] \= body  
        return methods  
      
    golden\_ops \= extract\_operation\_methods(golden\_py)  
    generated\_ops \= extract\_operation\_methods(generated\_py)  
      
    results \= {  
        "missing\_in\_generated": \[\],  
        "stub\_in\_generated": \[\],  
        "http\_missing": \[\],  
    }  
      
    for op\_name, golden\_body in golden\_ops.items():  
        if op\_name not in generated\_ops:  
            results\["missing\_in\_generated"\].append(op\_name)  
        else:  
            gen\_body \= generated\_ops\[op\_name\]  
            \# Check if golden has HTTP but generated doesn't  
            if 'self.\_api\_request' in golden\_body and 'self.\_api\_request' not in gen\_body:  
                results\["http\_missing"\].append(op\_name)  
            \# Check for stubs  
            if 'TODO: Implement' in gen\_body or 'response \= {}' in gen\_body:  
                results\["stub\_in\_generated"\].append(op\_name)  
      
    return results

4.4 Contract-Code Round-Trip Validation

def validate\_contract\_code\_roundtrip(contract\_yaml: Path, generated\_py: Path) \-\> bool:  
    """  
    Ensure contract-declared operations exist with non-stub implementations.  
    """  
    contract \= yaml.safe\_load(contract\_yaml.read\_text())  
    code \= generated\_py.read\_text()  
      
    declared\_ops \= \[\]  
    for op in contract.get("operations", \[\]):  
        resource \= op.get("resource", "")  
        operation \= op.get("name", "")  
        declared\_ops.append(f"\_{resource}\_{operation}" if resource else f"\_{operation}")  
      
    missing \= \[\]  
    stub \= \[\]  
      
    for op\_method in declared\_ops:  
        if f"def {op\_method}(" not in code:  
            missing.append(op\_method)  
        else:  
            \# Extract method body and check for stubs  
            pattern \= rf'def {op\_method}\\(\[^)\]\*\\):(.\*?)(?=\\n    def |\\Z)'  
            match \= re.search(pattern, code, re.DOTALL)  
            if match and ('TODO: Implement' in match.group(1) or 'response \= {}' in match.group(1)):  
                stub.append(op\_method)  
      
    if missing or stub:  
        print(f"❌ CONTRACT-CODE MISMATCH:")  
        if missing:  
            print(f"  Missing methods: {missing}")  
        if stub:  
            print(f"  Stub methods: {stub}")  
        return False  
    return True

4.5 Updated Agent Gate

\# scripts/agent\_gate.py additions  
def run\_behavioral\_gates(correlation\_id: str) \-\> bool:  
    artifacts\_dir \= Path(f"artifacts/{correlation\_id}")  
      
    \# 1\. No-stub check  
    node\_file \= artifacts\_dir / "converted\_node" / f"{node\_name}.py"  
    if not validate\_no\_stubs(node\_file):  
        return False  
      
    \# 2\. Golden parity (if golden exists)  
    golden\_path \= Path(f"avidflow-back/nodes/{node\_name}.py")  
    if golden\_path.exists():  
        diff \= semantic\_diff(golden\_path.read\_text(), node\_file.read\_text())  
        if diff\["stub\_in\_generated"\] or diff\["http\_missing"\]:  
            print(f"❌ SEMANTIC REGRESSION: {diff}")  
            return False  
      
    \# 3\. Source parity (if TypeScript source exists)  
    source\_ts \= (artifacts\_dir / "source\_bundle" / f"{node\_name}.node.ts")  
    if source\_ts.exists():  
        if not validate\_side\_effect\_parity(source\_ts.read\_text(), node\_file.read\_text()):  
            return False  
      
    return True

5\. Anthropic Alignment Clarification  
5.1 What We Misunderstood  
From "Writing Tools for Agents":

Anthropic's guidance: Tools should have "clear input/output schemas" and "predictable behavior."

Our misinterpretation: We applied "clear schemas" to mean "generate code from schemas."

Correct interpretation: Schemas define tool interfaces (what the agent can call), not tool implementations (what the tool does internally).

The Anthropic pattern is:  
User intent → Agent reasoning → Tool call (schema-constrained) → Execution (implementation)  
                                      ↑                              ↑  
                                 Schema defines               Implementation is  
                                 valid inputs                 independent of schema

We inverted this to:  
Schema → Code generation → Output  
           ↑  
      Schema replaces implementation

5.2 What We Applied Correctly  
Contract-as-constraint concept: The idea that contracts bound agent behavior is correct.  
Trace map evidence: Linking inferred fields to source evidence is sound.  
HYBRID backbone: Using deterministic extraction before advisor fallback is correct.  
Sync-Celery constraint: Non-negotiable runtime constraints are properly enforced.

5.3 What Must Be Adapted  
Anthropic Context	Production Code Generation  
Agent tools are stateless functions	Nodes have implementation state (HTTP calls, auth)  
Schema ensures valid invocation	Schema must not generate body  
Incorrect tool call \= retry	Incorrect generation \= permanent semantic loss  
Tool failure is recoverable	Stub output cannot self-heal

Adaptation required:

Contracts validate, not generate: A contract for a GitHub node says "must have \_issue\_create method"; it does NOT define what that method does.

Ground truth is code, not schema: For TYPE1 conversions, the TypeScript source (or existing Python) is authoritative. Schema is derived FROM code, not the reverse.

Advisor outputs are proposals, not implementations: When AI assists with inference, its outputs must be validated against source evidence before becoming part of the conversion.

Silent failure is worse than loud failure: The current pipeline produces syntactically valid but semantically empty output. This is worse than crashing, because downstream systems cannot distinguish broken output from working output.

Summary  
Issue	Fix  
Schema generates code	Schema validates; code comes from source  
Stub fallback is silent	Stub detection gate fails build  
No behavioral validation	Semantic diff against golden/source  
Contract satisfaction \= completion	Contract \+ behavior parity \= completion  
Single validator (contract)	Three validators: contract \+ stub \+ parity  
