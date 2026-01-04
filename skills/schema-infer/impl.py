"""
Schema Infer Skill - HYBRID backbone implementation.

HYBRID EXECUTION MODEL:
1. DETERMINISTIC FIRST: For TYPE1 (TypeScript), use regex/AST extraction
   - No LLM calls for well-structured TypeScript
   - Direct extraction of functions, types, interfaces
   
2. ADVISOR FALLBACK: For TYPE2 (docs) or when deterministic fails
   - Advisor suggests schemas from unstructured documentation
   - All advisor outputs validated before becoming outputs
   - Trace map links every field to evidence (no hallucination)

This skill demonstrates the agent capability pattern:
- First turn: Validate inputs, request missing if needed (INPUT_REQUIRED)
- Subsequent turns: Resume from stored state and complete

SYNC-CELERY SAFE:
- No async, no threads
- All state persisted to StateStore between turns
- Resumable via context_id
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import runtime types
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.protocol import (
    AgentId,
    AgentResponse,
    ContextId,
    InputFieldSpec,
    InputRequest,
    TaskState,
)
from runtime.state_store import (
    ConversationEvent,
    PocketFact,
    create_state_store,
)
from runtime.executor import ExecutionContext


# =============================================================================
# HYBRID BACKBONE CONFIGURATION
# =============================================================================

# Minimum confidence thresholds for schema extraction
MIN_DETERMINISTIC_CONFIDENCE = 0.8  # TYPE1 deterministic extraction
MIN_ADVISOR_CONFIDENCE = 0.6       # TYPE2 advisor-assisted extraction
MAX_ASSUMPTION_RATIO = 0.3         # Max 30% ASSUMPTION entries in trace map


# =============================================================================
# MAIN ENTRY POINT (called by executor)
# =============================================================================

def execute_schema_infer(ctx: ExecutionContext) -> AgentResponse:
    """
    Execute schema inference with agent-style multi-turn support.
    
    Returns AgentResponse directly - executor now handles this natively (STEP 3).
    TaskState maps to ExecutionStatus for backward compatibility:
      - COMPLETED -> SUCCESS
      - INPUT_REQUIRED -> PENDING (with agent_metadata for caller)
      - FAILED -> FAILURE
    """
    return execute_schema_infer_agent(ctx)


def execute_schema_infer_agent(ctx: ExecutionContext) -> AgentResponse:
    """
    Agent-style schema inference with proper state management.
    
    Turn 1: Validate inputs, request missing if needed
    Turn 2+: Resume and complete inference
    """
    context_id = ctx.correlation_id
    agent_id = AgentId("schema-infer")
    
    # Initialize state store for this context
    state_store = create_state_store()
    
    # Load existing state to determine turn
    existing_state = state_store.get_state(context_id)
    current_turn = (existing_state.current_turn + 1) if existing_state else 1
    
    # Merge stored inputs with current inputs
    inputs = dict(ctx.inputs)
    if existing_state:
        stored_inputs = state_store.get_facts_by_bucket(context_id, "inputs")
        inputs = {**stored_inputs, **inputs}
    
    # Store current inputs
    for key, value in inputs.items():
        state_store.put_fact(context_id, PocketFact(bucket="inputs", key=key, value=value))
    
    # Check required inputs
    missing = _check_required_inputs(inputs)
    
    if missing:
        # Record event and return INPUT_REQUIRED
        state_store.append_event(
            context_id,
            ConversationEvent(
                event_type="input_required",
                payload={"missing_fields": [f.name for f in missing]},
                turn_number=current_turn,
                agent_id=str(agent_id),
            ),
        )
        state_store.update_task_state(context_id, TaskState.INPUT_REQUIRED.value, current_turn)
        
        return AgentResponse(
            state=TaskState.INPUT_REQUIRED,
            input_request=InputRequest(
                missing_fields=missing,
                reason="Schema inference requires source data. Please provide the missing fields.",
                partial_outputs={},
            ),
            turn_number=current_turn,
            state_handle=context_id,
        )
    
    # All inputs present - perform inference
    try:
        result = _perform_schema_inference(
            correlation_id=context_id,
            parsed_sections=inputs.get("parsed_sections", {}),
            source_type=inputs.get("source_type", "TYPE2"),
            artifacts_dir=ctx.artifacts_dir,
        )
        
        # Record completion
        state_store.append_event(
            context_id,
            ConversationEvent(
                event_type="inference_completed",
                payload={
                    "schema_fields": len(result.get("inferred_schema", {}).get("operations", [])),
                    "trace_entries": len(result.get("trace_map", {}).get("trace_entries", [])),
                },
                turn_number=current_turn,
                agent_id=str(agent_id),
            ),
        )
        state_store.update_task_state(context_id, TaskState.COMPLETED.value, current_turn)
        
        # Store outputs as facts
        for key, value in result.items():
            state_store.put_fact(context_id, PocketFact(bucket="outputs", key=key, value=value))
        
        return AgentResponse(
            state=TaskState.COMPLETED,
            outputs=result,
            turn_number=current_turn,
        )
    
    except Exception as e:
        state_store.update_task_state(context_id, TaskState.FAILED.value, current_turn)
        return AgentResponse(
            state=TaskState.FAILED,
            errors=[str(e)],
            turn_number=current_turn,
        )


# =============================================================================
# INPUT VALIDATION
# =============================================================================

def _check_required_inputs(inputs: Dict[str, Any]) -> List[InputFieldSpec]:
    """Check for missing required inputs."""
    missing = []
    
    # correlation_id is always provided by executor, no need to check
    
    # parsed_sections is required
    if "parsed_sections" not in inputs or not inputs["parsed_sections"]:
        missing.append(InputFieldSpec(
            name="parsed_sections",
            type="object",
            description="Parsed source sections from source-ingest skill. Contains code, docs, or API specs.",
            required=True,
        ))
    
    # source_type is required
    if "source_type" not in inputs or inputs["source_type"] not in ("TYPE1", "TYPE2"):
        missing.append(InputFieldSpec(
            name="source_type",
            type="string",
            description="Source type: 'TYPE1' for TypeScript source code, 'TYPE2' for documentation/API specs.",
            required=True,
        ))
    
    return missing


# =============================================================================
# SCHEMA INFERENCE LOGIC
# =============================================================================

def _perform_schema_inference(
    correlation_id: str,
    parsed_sections: Dict[str, Any],
    source_type: str,
    artifacts_dir: Path,
) -> Dict[str, Any]:
    """
    Perform actual schema inference from parsed source.
    
    HYBRID EXECUTION MODEL:
    
    TYPE1 (TypeScript): DETERMINISTIC extraction
    - Parse TypeScript for interfaces, functions, types
    - Extract operations, credentials, parameters directly
    - High confidence, minimal assumptions
    
    TYPE2 (Docs): DETERMINISTIC first, ADVISOR fallback
    - First: Regex patterns for common API docs format
    - If insufficient: Advisor assists (NOT IMPLEMENTED - stub returns partial)
    - All advisor outputs require trace map validation
    
    Returns:
        Schema inference result with trace map linking every field to evidence
    """
    # Extract node type from parsed sections or generate from correlation_id
    node_type = parsed_sections.get("node_name", correlation_id.split("-")[0] if "-" in correlation_id else "unknown")
    
    # Initialize trace entries
    trace_entries = []
    assumptions = []
    
    # =================================================================
    # PHASE 1: DETERMINISTIC EXTRACTION (always runs first)
    # =================================================================
    
    operations = []
    extracted_parameters = []
    extraction_confidence = 0.0
    
    if source_type == "TYPE1":
        # TypeScript source - FULLY DETERMINISTIC
        operations, op_traces, confidence = _extract_operations_deterministic_ts(parsed_sections)
        trace_entries.extend(op_traces)
        extraction_confidence = confidence
        
        # Also extract n8n-specific parameters
        code_sections = parsed_sections.get("code", [])
        for section in code_sections:
            content = section.get("content", "") if isinstance(section, dict) else str(section)
            file_name = section.get("file", "unknown") if isinstance(section, dict) else "unknown"
            params = _extract_n8n_parameters(content, file_name)
            if params:
                extracted_parameters.extend(params)
    else:
        # Documentation - DETERMINISTIC FIRST
        operations, op_traces, confidence = _extract_operations_deterministic_docs(parsed_sections)
        trace_entries.extend(op_traces)
        extraction_confidence = confidence
    
    # =================================================================
    # PHASE 2: ADVISOR FALLBACK (only if deterministic insufficient)
    # =================================================================
    
    advisor_used = False
    
    if extraction_confidence < MIN_DETERMINISTIC_CONFIDENCE and source_type == "TYPE2":
        # ADVISOR FALLBACK: Would call LLM to suggest schema from docs
        # NOT IMPLEMENTED - just note that we would use advisor here
        #
        # In production, this would:
        # 1. Send docs to advisor with structured prompt
        # 2. Receive suggested schema
        # 3. Validate via AdvisorOutputValidator
        # 4. Merge with deterministic results
        #
        # For now, we mark as needing advisor but proceed with what we have
        advisor_used = True
        trace_entries.append({
            "field_path": "_metadata.advisor_fallback",
            "source": "ASSUMPTION",
            "evidence": "Deterministic extraction insufficient; advisor assistance recommended",
            "confidence": "low",
            "assumption_rationale": f"Extraction confidence {extraction_confidence:.2f} < {MIN_DETERMINISTIC_CONFIDENCE}",
        })
        assumptions.append(f"Low extraction confidence ({extraction_confidence:.2f}) - manual review recommended")
    
    # =================================================================
    # PHASE 3: FALLBACK TO DEFAULTS (if extraction failed)
    # =================================================================
    
    # If no operations found, add assumption
    if not operations:
        operations = [{"name": "execute", "description": "Default operation"}]
        trace_entries.append({
            "field_path": "operations[0]",
            "source": "ASSUMPTION",
            "evidence": "No operations found in source; defaulting to single 'execute' operation",
            "confidence": "low",
            "assumption_rationale": "Source may be incomplete or use different patterns",
        })
        assumptions.append("Default 'execute' operation assumed - verify against actual API")
    
    # Extract credentials
    credentials, cred_traces = _extract_credentials(parsed_sections, source_type)
    trace_entries.extend(cred_traces)
    
    # =================================================================
    # VALIDATE TRACE MAP QUALITY
    # =================================================================
    
    assumption_count = sum(1 for t in trace_entries if t.get("source") == "ASSUMPTION")
    assumption_ratio = assumption_count / len(trace_entries) if trace_entries else 0
    
    if assumption_ratio > MAX_ASSUMPTION_RATIO:
        assumptions.append(
            f"WARNING: High assumption ratio ({assumption_ratio:.1%}) exceeds {MAX_ASSUMPTION_RATIO:.0%} threshold"
        )
    
    # Build inferred schema
    # Use extracted parameters if available, otherwise build from operations
    final_parameters = extracted_parameters if extracted_parameters else _build_parameters(operations)
    
    # Add operation selector at the beginning if we have n8n operations
    if operations and any("display_name" in op for op in operations):
        # This is an n8n node with proper operations
        op_param = {
            "name": "operation",
            "type": "OPTIONS",
            "display_name": "Operation",
            "options": [
                {"name": op.get("display_name", op["name"]), "value": op["name"], "description": op.get("description", "")}
                for op in operations
            ],
            "default": operations[0]["name"],
            "description": "Operation to perform",
        }
        # Insert operation at the beginning
        final_parameters = [op_param] + [p for p in final_parameters if p.get("name") != "operation"]
    
    inferred_schema = {
        "type": node_type,
        "version": 1,
        "description": {
            "displayName": _to_display_name(node_type),
            "name": node_type.lower(),
            "inputs": [{"name": "main", "type": "main"}],
            "outputs": [{"name": "main", "type": "main"}],
        },
        "properties": {
            "parameters": final_parameters,
        },
        "operations": operations,
        "credentials": credentials,
    }
    
    # Build trace map with metadata
    trace_map = {
        "correlation_id": correlation_id,
        "node_type": node_type,
        "trace_entries": trace_entries,
        "generated_at": datetime.utcnow().isoformat(),
        "skill_version": "1.0.0",
        # HYBRID BACKBONE METADATA
        "_hybrid_metadata": {
            "source_type": source_type,
            "extraction_confidence": extraction_confidence,
            "advisor_used": advisor_used,
            "assumption_ratio": assumption_ratio,
            "deterministic_operations": len([t for t in trace_entries if t.get("source") in ("SOURCE_CODE", "API_DOCS")]),
            "assumption_operations": assumption_count,
        },
    }
    
    # Write artifacts
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    schema_path = artifacts_dir / "inferred_schema.json"
    schema_path.write_text(json.dumps(inferred_schema, indent=2))
    
    trace_path = artifacts_dir / "trace_map.json"
    trace_path.write_text(json.dumps(trace_map, indent=2))
    
    return {
        "inferred_schema": inferred_schema,
        "trace_map": trace_map,
        "assumptions": assumptions,
        "artifacts_written": [str(schema_path), str(trace_path)],
        # HYBRID metadata for logging/debugging
        "extraction_confidence": extraction_confidence,
        "advisor_used": advisor_used,
    }


def _extract_operations_deterministic_ts(
    parsed_sections: Dict[str, Any],
) -> Tuple[List[Dict], List[Dict], float]:
    """
    DETERMINISTIC extraction of operations from TypeScript source.
    
    This is PURE DETERMINISTIC - no LLM calls.
    Uses regex patterns to extract:
    - Function definitions
    - Interface methods
    - Class methods
    
    Returns:
        (operations, trace_entries, confidence_score)
    """
    operations = []
    traces = []
    total_possible = 0  # Track how many potential sources we checked
    found = 0           # Track how many we extracted
    
    code_sections = parsed_sections.get("code", [])
    if isinstance(code_sections, str):
        code_sections = [{"content": code_sections, "file": "source.ts"}]
    
    for section in code_sections:
        content = section.get("content", "") if isinstance(section, dict) else str(section)
        file_name = section.get("file", "unknown") if isinstance(section, dict) else "unknown"
        
        # Pattern 1: Function definitions (async function foo, function foo, const foo =)
        func_pattern = r"(?:export\s+)?(?:async\s+)?(?:function\s+)?(\w+)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*[:{]"
        matches = list(re.finditer(func_pattern, content))
        total_possible += 1  # We checked for functions
        
        # Keywords to exclude (control flow, JS builtins, lifecycle methods)
        EXCLUDED_NAMES = {
            # Control flow
            "if", "else", "for", "while", "switch", "case", "do", "try", "catch", "finally",
            # JS/TS keywords
            "return", "throw", "new", "delete", "typeof", "instanceof", "void", "yield", "await",
            # Lifecycle/internal
            "constructor", "execute", "init", "destroy", "super", "this",
            # Common non-operation patterns
            "get", "set", "has", "is", "can", "should", "will", "did",
        }
        
        for match in matches:
            func_name = match.group(1)
            # Skip internal/lifecycle methods and control flow keywords
            if func_name.startswith("_") or func_name.lower() in EXCLUDED_NAMES:
                continue
            
            operations.append({
                "name": func_name,
                "description": f"Operation: {func_name}",
            })
            traces.append({
                "field_path": f"operations[{len(operations)-1}].name",
                "source": "SOURCE_CODE",
                "evidence": f"Function '{func_name}' defined in {file_name}",
                "confidence": "high",
                "source_file": file_name,
                "line_range": f"L{content[:match.start()].count(chr(10))+1}",
                "excerpt_hash": _hash_excerpt(content[match.start():match.end()]),
            })
            found += 1
        
        # Pattern 2: Interface method signatures
        interface_pattern = r"interface\s+\w+\s*\{([^}]+)\}"
        for iface_match in re.finditer(interface_pattern, content, re.DOTALL):
            total_possible += 1
            method_pattern = r"(\w+)\s*\([^)]*\)\s*:\s*"
            for method_match in re.finditer(method_pattern, iface_match.group(1)):
                method_name = method_match.group(1)
                if method_name not in [op["name"] for op in operations]:
                    operations.append({
                        "name": method_name,
                        "description": f"Interface method: {method_name}",
                    })
                    traces.append({
                        "field_path": f"operations[{len(operations)-1}].name",
                        "source": "SOURCE_CODE",
                        "evidence": f"Interface method '{method_name}' in {file_name}",
                        "confidence": "high",
                        "source_file": file_name,
                        "excerpt_hash": _hash_excerpt(method_match.group(0)),
                    })
                    found += 1
        
        # Pattern 3: n8n operation options from properties array
        # Matches: name: 'operation', ... options: [{ name: 'X', value: 'y' }, ...]
        # This is the primary pattern for n8n nodes
        n8n_ops, n8n_traces = _extract_n8n_operations(content, file_name, len(operations))
        if n8n_ops:
            total_possible += 1
            # If we found n8n operations, prefer them over function definitions
            # as they represent the actual user-facing operations
            operations = n8n_ops  # Replace with n8n operations
            traces = n8n_traces
            found = len(n8n_ops)
    
    # Calculate confidence: ratio of successful extractions to attempts
    # Base confidence for TypeScript is high since it's well-structured
    if total_possible == 0:
        confidence = 0.0
    elif found == 0:
        confidence = 0.2  # We tried but found nothing
    else:
        confidence = min(0.95, 0.6 + (found / max(1, total_possible)) * 0.35)
    
    return operations, traces, confidence


def _extract_n8n_operations(
    content: str, file_name: str, start_index: int = 0
) -> Tuple[List[Dict], List[Dict]]:
    """
    Extract n8n operations from the properties array.
    
    n8n nodes define operations like:
    {
        name: 'operation',
        type: 'options',
        options: [
            { name: 'Domain Search', value: 'domainSearch', description: '...' },
            { name: 'Email Finder', value: 'emailFinder', description: '...' },
        ],
    }
    
    Returns:
        (operations, trace_entries)
    """
    operations = []
    traces = []
    
    # Look for the operation property definition
    # Pattern: name: 'operation' or name: "operation" followed by options array
    operation_block_pattern = r"name:\s*['\"]operation['\"].*?options:\s*\[(.*?)\]"
    
    match = re.search(operation_block_pattern, content, re.DOTALL | re.IGNORECASE)
    if not match:
        return [], []
    
    options_content = match.group(1)
    line_num = content[:match.start()].count('\n') + 1
    
    # Extract individual options: { name: 'X', value: 'y', description: '...' }
    # Handle both single and double quotes
    option_pattern = r"\{\s*name:\s*['\"]([^'\"]+)['\"].*?value:\s*['\"]([^'\"]+)['\"](?:.*?description:\s*['\"]([^'\"]*)['\"])?"
    
    for i, opt_match in enumerate(re.finditer(option_pattern, options_content, re.DOTALL)):
        display_name = opt_match.group(1)
        value = opt_match.group(2)
        description = opt_match.group(3) if opt_match.group(3) else f"Operation: {display_name}"
        
        operations.append({
            "name": value,
            "display_name": display_name,
            "description": description,
        })
        
        traces.append({
            "field_path": f"operations[{start_index + i}].name",
            "source": "SOURCE_CODE",
            "evidence": f"n8n operation '{value}' (display: '{display_name}') in {file_name}",
            "confidence": "high",
            "source_file": file_name,
            "line_range": f"L{line_num}",
            "excerpt_hash": _hash_excerpt(opt_match.group(0)),
        })
    
    return operations, traces


def _extract_n8n_parameters(content: str, file_name: str) -> List[Dict]:
    """
    Extract n8n parameters from the properties array.
    
    n8n nodes define parameters like:
    {
        displayName: 'Domain',
        name: 'domain',
        type: 'string',
        default: '',
        required: true,
        description: '...',
        displayOptions: { show: { operation: ['domainSearch'] } }
    }
    
    Returns:
        List of parameter definitions
    """
    parameters = []
    
    # Pattern to match individual property objects in the properties array
    # Looking for objects with name, type, and other fields
    param_pattern = r"\{\s*(?:displayName|name):\s*['\"]([^'\"]+)['\"].*?name:\s*['\"]([^'\"]+)['\"].*?type:\s*['\"]([^'\"]+)['\"]"
    
    # Find the properties array section
    props_match = re.search(r"properties:\s*\[(.*)\]", content, re.DOTALL)
    if not props_match:
        return []
    
    props_content = props_match.group(1)
    
    # Split by opening braces at proper level to get individual property objects
    # Simple approach: find each { ... } block that has name and type
    for match in re.finditer(param_pattern, props_content, re.DOTALL):
        display_name = match.group(1)
        name = match.group(2)
        param_type = match.group(3)
        
        # Skip the operation parameter (already handled separately)
        if name == "operation" or name == "resource":
            continue
        
        # Map n8n types to our types
        type_map = {
            "string": "STRING",
            "number": "NUMBER",
            "boolean": "BOOLEAN",
            "options": "OPTIONS",
            "multiOptions": "MULTIOPTIONS",
            "collection": "COLLECTION",
            "fixedCollection": "COLLECTION",
        }
        
        param_def = {
            "name": name,
            "display_name": display_name,
            "type": type_map.get(param_type, param_type.upper()),
        }
        
        # Try to extract additional fields
        # Get the full block for this parameter
        block_start = match.start()
        brace_count = 0
        block_end = block_start
        for i, c in enumerate(props_content[block_start:]):
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    block_end = block_start + i + 1
                    break
        
        block = props_content[block_start:block_end]
        
        # Extract default value
        default_match = re.search(r"default:\s*([^,}\n]+)", block)
        if default_match:
            default_val = default_match.group(1).strip().strip("'\"")
            if default_val == "true":
                param_def["default"] = True
            elif default_val == "false":
                param_def["default"] = False
            elif default_val.isdigit():
                param_def["default"] = int(default_val)
            else:
                param_def["default"] = default_val
        
        # Extract required
        if "required: true" in block.lower() or "required:true" in block.lower():
            param_def["required"] = True
        
        # Extract description
        desc_match = re.search(r"description:\s*['\"]([^'\"]*)['\"]", block)
        if desc_match:
            param_def["description"] = desc_match.group(1)
        
        # Extract displayOptions
        display_opts_match = re.search(r"displayOptions:\s*\{[^}]*show:\s*\{([^}]+)\}", block, re.DOTALL)
        if display_opts_match:
            show_content = display_opts_match.group(1)
            display_options = {"show": {}}
            
            # Extract operation conditions
            op_match = re.search(r"operation:\s*\[([^\]]+)\]", show_content)
            if op_match:
                ops = re.findall(r"['\"]([^'\"]+)['\"]", op_match.group(1))
                display_options["show"]["operation"] = ops
            
            if display_options["show"]:
                param_def["display_options"] = display_options
        
        # Extract options for OPTIONS type
        if param_type in ("options", "multiOptions"):
            options_match = re.search(r"options:\s*\[(.*?)\]", block, re.DOTALL)
            if options_match:
                options_content = options_match.group(1)
                options = []
                for opt in re.finditer(r"name:\s*['\"]([^'\"]+)['\"].*?value:\s*['\"]([^'\"]+)['\"]", options_content, re.DOTALL):
                    options.append({"name": opt.group(1), "value": opt.group(2)})
                if options:
                    param_def["options"] = options
        
        parameters.append(param_def)
    
    return parameters


def _extract_operations_deterministic_docs(
    parsed_sections: Dict[str, Any],
) -> Tuple[List[Dict], List[Dict], float]:
    """
    DETERMINISTIC extraction of operations from documentation.
    
    First pass - use regex patterns for common API doc formats.
    Returns lower confidence than TypeScript since docs are less structured.
    
    Returns:
        (operations, trace_entries, confidence_score)
    """
    operations = []
    traces = []
    total_patterns_checked = 0
    patterns_matched = 0
    
    # Look for API endpoints, method names, etc.
    docs = parsed_sections.get("docs", parsed_sections.get("content", ""))
    if isinstance(docs, list):
        docs = "\n".join(str(d) for d in docs)
    docs_str = str(docs)
    
    # Pattern 1: REST API endpoints (GET /users, POST /items)
    total_patterns_checked += 1
    endpoint_pattern = r"(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}]+)"
    endpoint_matches = list(re.finditer(endpoint_pattern, docs_str))
    if endpoint_matches:
        patterns_matched += 1
        for match in endpoint_matches:
            method = match.group(1)
            path = match.group(2)
            # Convert path to operation name (e.g., /users/{id} -> getUser)
            op_name = _path_to_operation_name(method, path)
            
            if op_name not in [op["name"] for op in operations]:
                operations.append({
                    "name": op_name,
                    "description": f"{method} {path}",
                    "method": method,
                    "path": path,
                })
                traces.append({
                    "field_path": f"operations[{len(operations)-1}].name",
                    "source": "API_DOCS",
                    "evidence": f"REST endpoint '{method} {path}' documented",
                    "confidence": "high",
                    "excerpt_hash": _hash_excerpt(match.group(0)),
                })
    
    # Pattern 2: Method/function mentions in docs
    total_patterns_checked += 1
    method_pattern = r"(?:method|function|operation|endpoint)[:\s]+[`'\"]?(\w+)[`'\"]?"
    method_matches = list(re.finditer(method_pattern, docs_str, re.IGNORECASE))
    if method_matches:
        patterns_matched += 1
        for match in method_matches:
            method_name = match.group(1)
            if method_name not in [op["name"] for op in operations]:
                operations.append({
                    "name": method_name,
                    "description": f"Method: {method_name}",
                })
                traces.append({
                    "field_path": f"operations[{len(operations)-1}].name",
                    "source": "API_DOCS",
                    "evidence": f"Method '{method_name}' referenced in documentation",
                    "confidence": "medium",
                    "excerpt_hash": _hash_excerpt(match.group(0)),
                })
    
    # Pattern 3: OpenAPI-style operation IDs
    total_patterns_checked += 1
    operationid_pattern = r"operationId[:\s]+['\"]?(\w+)['\"]?"
    opid_matches = list(re.finditer(operationid_pattern, docs_str, re.IGNORECASE))
    if opid_matches:
        patterns_matched += 1
        for match in opid_matches:
            op_id = match.group(1)
            if op_id not in [op["name"] for op in operations]:
                operations.append({
                    "name": op_id,
                    "description": f"Operation: {op_id}",
                })
                traces.append({
                    "field_path": f"operations[{len(operations)-1}].name",
                    "source": "API_DOCS",
                    "evidence": f"OpenAPI operationId '{op_id}' found",
                    "confidence": "high",
                    "excerpt_hash": _hash_excerpt(match.group(0)),
                })
    
    # Calculate confidence
    # Docs are inherently less structured, so max confidence is lower
    if total_patterns_checked == 0:
        confidence = 0.0
    elif patterns_matched == 0:
        confidence = 0.1  # Very low - docs didn't match any patterns
    else:
        base_confidence = 0.4
        pattern_bonus = (patterns_matched / total_patterns_checked) * 0.3
        operation_bonus = min(0.2, len(operations) * 0.05)
        confidence = min(0.85, base_confidence + pattern_bonus + operation_bonus)
    
    return operations, traces, confidence


def _path_to_operation_name(method: str, path: str) -> str:
    """Convert REST path to operation name (e.g., GET /users/{id} -> getUser)."""
    # Extract resource name from path
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    if not parts:
        return method.lower()
    
    resource = parts[-1]
    # Singularize if plural and method is GET with {id}
    if "{" in path and resource.endswith("s"):
        resource = resource[:-1]
    
    method_prefix = {
        "GET": "get",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method, method.lower())
    
    return f"{method_prefix}{resource.capitalize()}"


def _extract_credentials(parsed_sections: Dict[str, Any], source_type: str) -> Tuple[List[str], List[Dict]]:
    """Extract credential requirements."""
    credentials = []
    traces = []
    
    content = json.dumps(parsed_sections).lower()
    
    # Look for auth patterns
    auth_patterns = [
        (r"api[_-]?key", "apiKey"),
        (r"oauth", "oauth2"),
        (r"bearer", "bearerToken"),
        (r"basic[_-]?auth", "basicAuth"),
        (r"token", "apiToken"),
    ]
    
    for pattern, cred_type in auth_patterns:
        if re.search(pattern, content):
            credentials.append(cred_type)
            traces.append({
                "field_path": f"credentials[{len(credentials)-1}]",
                "source": "SOURCE_CODE" if source_type == "TYPE1" else "API_DOCS",
                "evidence": f"Auth pattern '{pattern}' found in source",
                "confidence": "medium",
            })
            break  # Only take first match
    
    # Default if none found
    if not credentials:
        credentials.append("genericApi")
        traces.append({
            "field_path": "credentials[0]",
            "source": "ASSUMPTION",
            "evidence": "No specific auth pattern detected; assuming generic API credentials",
            "confidence": "low",
            "assumption_rationale": "Most APIs require some form of authentication",
        })
    
    return credentials, traces


def _build_parameters(operations: List[Dict]) -> List[Dict]:
    """Build parameter specs from operations."""
    params = []
    
    if operations:
        # Add resource selector if multiple operations
        if len(operations) > 1:
            params.append({
                "name": "resource",
                "type": "options",
                "options": [{"name": op["name"], "value": op["name"]} for op in operations],
                "default": operations[0]["name"],
                "description": "Select the resource/operation",
            })
        
        # Add operation selector
        params.append({
            "name": "operation",
            "type": "options",
            "options": [{"name": op["name"], "value": op["name"]} for op in operations],
            "default": operations[0]["name"] if operations else "execute",
            "description": "Operation to perform",
        })
    
    return params


def _to_display_name(name: str) -> str:
    """Convert snake/kebab case to display name."""
    words = re.split(r"[-_]", name)
    return " ".join(w.capitalize() for w in words)


def _hash_excerpt(text: str) -> str:
    """Generate short hash of excerpt for trace map."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]
