from __future__ import annotations
from typing import Any, List
from models import NodeExecutionData

def run_node_inline(node_model: Any, workflow: Any, execution_data: dict) -> None:
    """
    Execute a provider node inline and persist its outputs into execution_data
    so that ConnectionResolver can pick them up. Designed for provider nodes (LLM, memory, tool).
    """
    from nodes import node_definitions
    info = node_definitions.get(node_model.type)
    if not info:
        raise RuntimeError(f"No node_class for type={node_model.type}")
    node_cls = info["node_class"]
    inst = node_cls(node_model, workflow, execution_data)

    inst.input_data = {"main": [[NodeExecutionData(json_data={}, binary_data=None)]]}
    out = inst.execute() or [[]]
    produced: List[NodeExecutionData] = out[0] if out and len(out) > 0 else []
    if produced is None:
        produced = []
    execution_data.setdefault(node_model.name, [])
    execution_data[node_model.name] = [produced]
