from __future__ import annotations
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from time import time
import time as time_module  # For sleep() in threading fallback
import logging

from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

# Import gevent for Celery worker compatibility (gevent pool mode)
try:
    import gevent
    from gevent.lock import RLock as GeventLock
    GEVENT_AVAILABLE = True
except ImportError:
    import threading
    GeventLock = threading.RLock  # Fallback for non-gevent environments
    GEVENT_AVAILABLE = False

# ── In-process conversation store (no Redis) ──────────────────────────────────

@dataclass
class _Entry:
    messages: List[Dict[str, Any]]
    expires_at: float

class _InMemoryConversationStore:
    def __init__(self) -> None:
        self._lock = GeventLock()  # Use gevent-compatible lock
        self._store: Dict[str, _Entry] = {}
        self._cleanup_running = False
        self._start_cleanup_greenlet()

    def _start_cleanup_greenlet(self) -> None:
        """
        Start background cleanup greenlet to actively purge expired sessions.
        
        CRITICAL: 
        - Uses gevent.spawn() for Celery gevent pool compatibility
        - Without this, expired sessions sit in RAM forever (only cleaned on access)
        - This prevents memory leaks in production with many inactive sessions
        
        ARCHITECTURE NOTE:
        - Celery workers run with --pool=gevent (see docker-compose.yml)
        - gevent uses cooperative multitasking (greenlets), not OS threads
        - Using threading.Thread would BLOCK the entire worker
        - gevent.sleep() yields control, allowing other tasks to run
        
        EDGE CASES HANDLED:
        - Idempotent: Can be called multiple times safely (checks flag)
        - Exception recovery: Catches all exceptions, continues running
        - Graceful degradation: Falls back to threading if gevent unavailable
        - Race condition prevention: Sets flag BEFORE spawning to prevent duplicates
        """
        # CRITICAL FIX: Check and set flag atomically to prevent race conditions
        if self._cleanup_running:
            logger.debug("[Memory Cleanup] Already running, skipping duplicate spawn")
            return
        
        # Set flag BEFORE spawning to prevent race condition in multi-threaded init
        self._cleanup_running = True
        
        def cleanup_loop():
            """
            Background cleanup loop with robust error handling.
            
            This loop NEVER exits - it recovers from all exceptions.
            If it ever crashes, _cleanup_running stays True preventing restart.
            """
            # Determine runtime environment
            runtime = "gevent" if GEVENT_AVAILABLE else "threading"
            logger.info(f"[Memory Cleanup] Background cleanup started (runtime: {runtime})")
            
            while True:
                try:
                    # Sleep first (don't run cleanup immediately on startup)
                    if GEVENT_AVAILABLE:
                        gevent.sleep(300)  # Yields to other greenlets - non-blocking
                    else:
                        time_module.sleep(300)  # Fallback for non-gevent environments
                    
                    # Run cleanup with full exception protection
                    try:
                        self._purge_expired()
                    except Exception as e:
                        # CRITICAL: Catch exceptions from _purge_expired to prevent loop crash
                        logger.error(
                            f"[Memory Cleanup] Error in _purge_expired: {e}",
                            exc_info=True  # Include full traceback
                        )
                        # Continue loop despite error
                        
                except KeyboardInterrupt:
                    # Allow graceful shutdown during development
                    logger.info("[Memory Cleanup] Interrupted, shutting down")
                    self._cleanup_running = False
                    break
                except Exception as e:
                    # Catch ANY exception (even from sleep) to prevent crash
                    logger.error(
                        f"[Memory Cleanup] Fatal error in cleanup loop: {e}",
                        exc_info=True
                    )
                    # Small sleep to prevent tight loop if persistent error
                    try:
                        if GEVENT_AVAILABLE:
                            gevent.sleep(60)  # Wait 1 minute before retry
                        else:
                            time_module.sleep(60)
                    except:
                        pass  # Even if sleep fails, continue
        
        # Spawn greenlet (gevent) or thread (fallback)
        try:
            if GEVENT_AVAILABLE:
                gevent.spawn(cleanup_loop)  # Non-blocking cooperative greenlet
                logger.debug("[Memory Cleanup] Spawned as gevent greenlet (Celery compatible)")
            else:
                import threading
                thread = threading.Thread(target=cleanup_loop, daemon=True, name="MemoryCleanup")
                thread.start()
                logger.debug("[Memory Cleanup] Spawned as Python thread (development mode)")
        except Exception as e:
            # CRITICAL: If spawn fails, reset flag so it can be retried
            logger.error(f"[Memory Cleanup] Failed to spawn cleanup: {e}", exc_info=True)
            self._cleanup_running = False
            raise

    def _purge_expired(self) -> None:
        """Remove expired entries and log cleanup stats"""
        now = time()
        to_del = []
        
        with self._lock:
            for k, v in self._store.items():
                if v.expires_at and v.expires_at <= now:
                    to_del.append(k)
            
            for k in to_del:
                self._store.pop(k, None)
            
            # Log cleanup statistics
            if to_del:
                logger.info(
                    f"[Memory Cleanup] Purged {len(to_del)} expired sessions. "
                    f"Active sessions: {len(self._store)}"
                )
            
            # Warning if too many active sessions (potential memory pressure)
            if len(self._store) > 1000:
                logger.warning(
                    f"[Memory Cleanup] High session count: {len(self._store)} active sessions. "
                    f"Consider using Redis for production!"
                )

    def get(self, key: str) -> List[Dict[str, Any]]:
        with self._lock:
            self._purge_expired()
            entry = self._store.get(key)
            if not entry:
                return []
            return list(entry.messages)

    def set(self, key: str, messages: List[Dict[str, Any]], ttl_seconds: Optional[int]) -> None:
        with self._lock:
            self._purge_expired()
            expires_at = time() + ttl_seconds if ttl_seconds else 0
            # cap stored messages to avoid unbounded growth (soft cap)
            capped = messages[-800:] if len(messages) > 800 else list(messages)
            self._store[key] = _Entry(messages=capped, expires_at=expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

_STORE = _InMemoryConversationStore()

# ── Memory Manager API used by the Agent ──────────────────────────────────────

class MemoryManager:
    """
    Synchronous memory helpers using an in-process store.
    Behavior mirrors n8n's MemoryBufferWindow:
      - Keep system messages
      - Return the last N interactions for context (window)
    """

    DEFAULT_TTL_SECONDS = 3600  # 1 hour

    @staticmethod
    def _key(session_id: str) -> str:
        return f"memory:session:{session_id}"

    @staticmethod
    def load(session_id: str, context_window: int) -> List[Dict[str, Any]]:
        try:
            key = MemoryManager._key(session_id)
            stored = _STORE.get(key) or []

            # Separate system from others, keep all system messages
            system_msgs = [m for m in stored if m.get("role") == "system"]
            non_system = [m for m in stored if m.get("role") != "system"]

            # Window is number of recent "turns" (user/assistant/tool)
            window = max(0, int(context_window))
            # Approximate 1 turn = up to 4 messages (user, assistant, tool(s))
            recent = non_system[-(window * 4):] if window else []
            return system_msgs + recent
        except Exception as e:
            logger.warning(f"Memory load failed: {e}")
            return []

    @staticmethod
    def save(
        session_id: str, 
        messages: List[Dict[str, Any]], 
        ttl_seconds: Optional[int] = None, 
        context_window: Optional[int] = None,
        auto_clear_on_full: bool = True
    ) -> None:
        """
        Save messages to memory with optional context window truncation.
        
        Args:
            session_id: Session identifier
            messages: Messages to save
            ttl_seconds: Time-to-live for stored messages
            context_window: If provided, only keep the last N turns (prevents unbounded growth)
            auto_clear_on_full: If True, clear all messages when window is full and start fresh
        """
        try:
            # CRITICAL FIX: Apply context window during save to prevent accumulation
            if context_window is not None and context_window > 0:
                # Separate system from others, keep all system messages
                system_msgs = [m for m in messages if m.get("role") == "system"]
                non_system = [m for m in messages if m.get("role") != "system"]
                
                # Window is number of recent "turns" (user/assistant/tool)
                # Approximate 1 turn = up to 4 messages (user, assistant, tool(s))
                window = max(0, int(context_window))
                max_messages = window * 4  # e.g., window=6 → max 24 messages
                
                # Count actual turns (user messages)
                user_messages = [m for m in non_system if m.get("role") == "user"]
                turn_count = len(user_messages)
                
                # AUTO-CLEAR LOGIC: If we've reached window limit, start fresh
                if auto_clear_on_full and turn_count >= window:
                    # Window is FULL - clear everything and keep only the latest turn
                    # Find the last user message (start of last turn)
                    user_message_indices = [i for i, m in enumerate(non_system) if m.get("role") == "user"]
                    last_turn_start = user_message_indices[-1]
                    recent = non_system[last_turn_start:]
                    
                    logger.info(
                        f"[MemoryManager] 🔄 Auto-clear triggered: "
                        f"Window FULL ({turn_count} turns ≥ {window} window limit). "
                        f"Cleared {len(non_system) - len(recent)} old messages, "
                        f"keeping only last turn ({len(recent)} messages)"
                    )
                else:
                    # Normal case: just truncate to max_messages
                    recent = non_system[-(max_messages):] if len(non_system) > max_messages else non_system
                
                messages_to_save = system_msgs + recent
                
                # Log what's happening
                if len(non_system) != len(recent):
                    logger.info(
                        f"[MemoryManager] Context window applied: "
                        f"{len(non_system)} messages → {len(recent)} messages "
                        f"(turns: {turn_count}/{window}, window={context_window})"
                    )
            else:
                messages_to_save = messages
            
            # Use explicit None check to allow ttl_seconds=0 (no expiration)
            effective_ttl = ttl_seconds if ttl_seconds is not None else MemoryManager.DEFAULT_TTL_SECONDS
            _STORE.set(MemoryManager._key(session_id), messages_to_save, effective_ttl)
        except Exception as e:
            logger.warning(f"Memory save failed: {e}")

    @staticmethod
    def clear(session_id: str) -> None:
        try:
            _STORE.delete(MemoryManager._key(session_id))
        except Exception as e:
            logger.warning(f"Memory clear failed: {e}")

# ── Node: Simple Memory (like n8n MemoryBufferWindow) ─────────────────────────

class BufferMemoryNode(BaseNode):
    """
    Simple Memory that stores conversation history in-process (per worker).
    Parameters:
      - sessionId / sessionKey
      - contextWindowLength
      - ttlSeconds (optional)
    Outputs:
      - ai_memory config consumed by the AI Agent
    """

    type = "buffer_memory"
    version = 1

    description = {
        "displayName": "Simple Memory",
        "name": "buffer_memory",
        "icon": "file:memory.svg",
        "group": ["ai"],
        "description": "Simple buffer memory that stores conversation for a session (in-process, no credentials).",
        "defaults": {"name": "Simple Memory"},
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "ai_memory", "type": "ai_memory", "required": True}],
    }

    properties = {
        "parameters": [
            {
                "name": "sessionId",
                "type": NodeParameterType.STRING,
                "displayName": "Session ID",
                "default": "{{ $json.sessionId || 'default' }}",
                "description": "Unique session identifier for this conversation",
            },
            {
                "name": "sessionKey",
                "type": NodeParameterType.STRING,
                "displayName": "Session Key From Previous Node",
                "default": "{{ $json.sessionId }}",
                "description": "Optional: take the session id from previous node data",
            },
            {
                "name": "contextWindowLength",
                "type": NodeParameterType.NUMBER,
                "displayName": "Context Window Length",
                "default": 5,
                "typeOptions": {"minValue": 0, "maxValue": 50},
                "description": "How many past interactions the model receives as context",
            },
            {
                "name": "ttlSeconds",
                "type": NodeParameterType.NUMBER,
                "displayName": "TTL (seconds)",
                "default": 3600,
                "typeOptions": {"minValue": 0, "maxValue": 86400},
                "description": "How long to keep memory for this session. 0 disables expiration.",
            },
        ]
    }

    def execute(self) -> List[List[NodeExecutionData]]:
        try:
            input_items = self.get_input_data() or [NodeExecutionData(json_data={}, binary_data=None)]
            out: List[NodeExecutionData] = []
            for idx, item in enumerate(input_items):
                raw_json = item.json_data or {}
                session_id = self.get_node_parameter("sessionId", idx, "default")
                session_key = self.get_node_parameter("sessionKey", idx, "")
                context_len = int(self.get_node_parameter("contextWindowLength", idx, 5))
                ttl_seconds = int(self.get_node_parameter("ttlSeconds", idx, MemoryManager.DEFAULT_TTL_SECONDS))
                final_session = session_key or session_id
                mem = {
                    "type": "simple_memory",
                    "session_id": final_session,
                    "context_window_length": context_len,
                    "ttl_seconds": ttl_seconds,
                }
                out.append(
                    NodeExecutionData(
                        json_data={**raw_json, "ai_memory": mem},
                        binary_data=item.binary_data,
                    )
                )
            return [out]
        except Exception as e:
            logger.error(f"Simple Memory error: {e}")
            return [[NodeExecutionData(json_data={"error": str(e)}, binary_data=None)]]
    
    # ==================== LangChain Runnable Integration ====================
    
    def get_runnable(self, item_index: int = 0):
        """
        Get LangChain-compatible MemoryRunnable for LCEL composition.
        
        This method wraps memory management logic as a Runnable, enabling:
        - Composition with other Runnables using LCEL (|)
        - Direct memory load/save/clear operations without workflow context
        - Integration with LangChain chains and agents
        
        Args:
            item_index: Index of the input item to use for configuration (default: 0)
        
        Returns:
            MemoryRunnable: A Runnable that performs memory operations
        
        Example:
            # Get the memory as a Runnable
            memory = memory_node.get_runnable()
            
            # Load conversation history
            result = memory.invoke({"action": "load"})
            
            # Save new messages
            result = memory.invoke({
                "action": "save",
                "messages": [{"role": "user", "content": "Hello"}]
            })
        """
        
        from utils.langchain_memory import MemoryRunnable
        from utils.langchain_base import RunnableRegistry
        
        # Get parameters
        session_id = self.get_node_parameter("sessionId", item_index, "default")
        session_key = self.get_node_parameter("sessionKey", item_index, "")
        context_window = int(self.get_node_parameter("contextWindowLength", item_index, 5))
        ttl_seconds = int(self.get_node_parameter("ttlSeconds", item_index, MemoryManager.DEFAULT_TTL_SECONDS))
        
        # Use session_key if provided, otherwise use session_id
        final_session_id = session_key or session_id
        
        # Create Runnable
        runnable = MemoryRunnable(
            session_id=final_session_id,
            context_window=context_window,
            ttl_seconds=ttl_seconds
        )
        
        # NOTE: Registry cleanup removed - use managed_runnable() context manager instead
        # For manual registration, call RunnableRegistry.register(runnable) explicitly
        # See utils.runnable_helpers.managed_runnable for automatic lifecycle management
        
        logger.info(
            f"[BufferMemoryNode] Created MemoryRunnable for session '{final_session_id}' "
            f"(window={context_window}, ttl={ttl_seconds}s)"
        )
        
        return runnable