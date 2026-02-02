from __future__ import annotations
from typing import List, Optional, Dict, Any
from models import NodeExecutionData, Node as NodeModel, WorkflowModel
import logging, json

logger = logging.getLogger(__name__)

class ConnectionResolver:
    """
    Central utility for resolving:
      - input slot index by input name
      - inbound items for an input
      - upstream node models feeding an input
    """

    @staticmethod
    def get_expected_input_type(node_model: NodeModel, input_name: str) -> Optional[str]:
        desc = ConnectionResolver._coerce_description(getattr(node_model, "description", None))
        inputs = desc.get("inputs") or []
        if not inputs:
            class_desc = ConnectionResolver._get_class_description(node_model)
            inputs = class_desc.get("inputs") or []
        target = (input_name or "").strip().lower()
        for inp in inputs:
            if (inp.get("name","").strip().lower() == target) or (
                not inp.get("name") and (inp.get("type","").strip().lower() == target)
            ):
                return (inp.get("type") or "").strip()
        return None

    @staticmethod
    def _coerce_description(desc_any: Any) -> Dict[str, Any]:
        if not desc_any:
            return {}
        if isinstance(desc_any, dict):
            return desc_any
        if isinstance(desc_any, str):
            try:
                return json.loads(desc_any)
            except Exception:
                return {}
        return {}

    @staticmethod
    def _get_class_description(node_model: NodeModel) -> Dict[str, Any]:
        try:
            from nodes import node_definitions
            info = node_definitions.get(getattr(node_model, "type", ""), {})
            cls = info.get("node_class")
            if cls and hasattr(cls, "description"):
                return getattr(cls, "description") or {}
        except Exception:
            pass
        return {}

    @staticmethod
    def get_input_slot(node_model, input_name: str) -> int:
        """
        n8n semantics: every input list uses index 0. We keep this function
        for compatibility, but always return 0 to avoid index-based routing.
        """
        return 0

    @staticmethod
    def _iter_edges(workflow: WorkflowModel):
        connections = getattr(workflow, "connections", None)
        if hasattr(connections, "root"):
            connections = connections.root
        if not isinstance(connections, dict):
            return
        for source_name, source_outputs in connections.items():
            if not isinstance(source_outputs, dict):
                continue
            for conn_type, outputs in source_outputs.items():
                if not isinstance(outputs, list):
                    continue
                for out_idx, conns in enumerate(outputs):
                    if not isinstance(conns, list):
                        continue
                    for c in conns:
                        yield source_name, conn_type, out_idx, c  # c.node, c.index

    @staticmethod
    def get_upstream_nodes(workflow: WorkflowModel, node_name: str, input_name: str) -> List[NodeModel]:
        nodes = {n.name: n for n in getattr(workflow, "nodes", []) or []}
        target_model = nodes.get(node_name)
        if not target_model:
            return []

        expected_type = (ConnectionResolver.get_expected_input_type(target_model, input_name) or "").strip()
        input_name = (input_name or "").strip()
        valid_keys = {expected_type, input_name, "main"} - {""}
        upstream_order: List[str] = []
        upstream: List[NodeModel] = []
        for src_name, conn_key, _out_idx, edge in ConnectionResolver._iter_edges(workflow):
            if getattr(edge, "node", None) != node_name:
                continue
            # n8n-compatible: accept conn_key by expected TYPE, INPUT NAME, or 'main'
            ck = (conn_key or "").strip()
            if valid_keys and ck:
                if ck == "main":
                    # Only accept 'main' when the inner edge.type matches the expected typed channel
                    edge_t = (getattr(edge, "type", "") or "").strip()
                    if expected_type and edge_t != expected_type:
                        continue
                else:
                    # Accept exact match on expected type OR input name
                    if ck not in (expected_type, input_name):
                        continue
            nm = nodes.get(src_name)
            if nm and nm.name not in upstream_order:
                upstream_order.append(nm.name)
                upstream.append(nm)
        #logger.info(f"[Connection Resolver] Found upstream nodes': {upstream}")
        return upstream

    @staticmethod
    def get_items(
        workflow: WorkflowModel,
        execution_data: Dict[str, Any],
        node_name: str,
        input_name: str
    ) -> List[NodeExecutionData]:
        """
        n8n-style helper:
         - finds upstream nodes for the given typed input
         - returns their already-materialized items (after lazy exec)
        """
        items: List[NodeExecutionData] = []
        upstream = ConnectionResolver.get_upstream_nodes(workflow, node_name, input_name)
        for u in upstream:
            node_chunks = (execution_data or {}).get(u.name) or []
            if node_chunks and len(node_chunks) > 0:
                # Take first output channel by convention
                items.extend(node_chunks[0] or [])

        return items