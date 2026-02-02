"""
LangChain-compatible Memory implementations.

Wraps our existing memory management (MemoryManager) as LangChain Runnables,
enabling memory operations to be composed in LCEL chains.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
import logging

from utils.langchain_base import BaseLangChainRunnable

logger = logging.getLogger(__name__)


class MemoryRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible wrapper for memory operations.
    
    Wraps our in-process MemoryManager to provide session-based conversation
    history storage with LangChain Runnable interface.
    
    Input format:
        {
            "action": "load" | "save" | "clear",  # operation to perform
            "messages": Optional[List[Dict]],  # messages to save (for save action)
            "context": Optional[Dict[str, Any]]  # additional context
        }
    
    Output format:
        {
            "messages": List[Dict],  # loaded/saved messages
            "success": bool,  # operation status
            "session_id": str,  # session identifier
            "count": int  # number of messages
        }
    
    Example:
        memory = MemoryRunnable(
            session_id="user_123",
            context_window=5,
            ttl_seconds=3600
        )
        
        # Load conversation history
        result = memory.invoke({"action": "load"})
        # result: {"messages": [...], "success": True, "count": 10}
        
        # Save new messages
        result = memory.invoke({
            "action": "save",
            "messages": [{"role": "user", "content": "Hello"}]
        })
    """
    
    def __init__(
        self,
        session_id: str,
        context_window: int = 5,
        ttl_seconds: Optional[int] = None,
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Memory Runnable.
        
        Args:
            session_id: Unique session identifier for conversation
            context_window: Number of recent turns to include when loading
            ttl_seconds: Time-to-live for stored messages (seconds)
            name: Optional memory name
            **kwargs: Additional config
        """
        super().__init__(name=name or f"Memory:{session_id}", **kwargs)
        self.session_id = session_id
        self.context_window = context_window
        self.ttl_seconds = ttl_seconds
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute memory operation.
        
        Args:
            input: Dict with "action" and optional "messages"
            config: Runtime config
        
        Returns:
            Dict with messages, success status, and metadata
        """
        try:
            from nodes.memory.buffer_memory import MemoryManager
            
            action = input.get("action", "load")
            
            if action == "load":
                return self._load_memory()
            
            elif action == "save":
                messages = input.get("messages", [])
                return self._save_memory(messages)
            
            elif action == "clear":
                return self._clear_memory()
            
            else:
                return {
                    "messages": [],
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "session_id": self.session_id,
                    "count": 0
                }
        
        except Exception as e:
            logger.error(f"[MemoryRunnable] Error during {input.get('action', 'unknown')}: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0
            }
    
    def _load_memory(self) -> Dict[str, Any]:
        """
        Load conversation history from memory.
        
        Returns:
            Dict with loaded messages
        """
        from nodes.memory.buffer_memory import MemoryManager
        
        try:
            messages = MemoryManager.load(self.session_id, self.context_window)
            
            logger.info(
                f"[MemoryRunnable] Loaded {len(messages)} messages "
                f"for session '{self.session_id}'"
            )
            
            return {
                "messages": messages,
                "success": True,
                "session_id": self.session_id,
                "count": len(messages)
            }
        
        except Exception as e:
            logger.error(f"[MemoryRunnable] Load failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0
            }
    
    def _save_memory(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save conversation history to memory.
        
        Args:
            messages: Messages to save
        
        Returns:
            Dict with save status
        """
        from nodes.memory.buffer_memory import MemoryManager
        
        try:
            ttl = self.ttl_seconds or MemoryManager.DEFAULT_TTL_SECONDS
            # CRITICAL FIX: Pass context_window to save() to prevent unbounded accumulation
            # auto_clear_on_full=True: When window is full, clear and start fresh
            MemoryManager.save(
                self.session_id, 
                messages, 
                ttl_seconds=ttl,
                context_window=self.context_window,  # Apply window during save
                auto_clear_on_full=True  # Clear cache when full, start fresh
            )
            
            logger.info(
                f"[MemoryRunnable] Saved {len(messages)} messages "
                f"for session '{self.session_id}' (TTL: {ttl}s, window: {self.context_window})"
            )
            
            return {
                "messages": messages,
                "success": True,
                "session_id": self.session_id,
                "count": len(messages)
            }
        
        except Exception as e:
            logger.error(f"[MemoryRunnable] Save failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0
            }
    
    def _clear_memory(self) -> Dict[str, Any]:
        """
        Clear conversation history from memory.
        
        Returns:
            Dict with clear status
        """
        from nodes.memory.buffer_memory import MemoryManager
        
        try:
            MemoryManager.clear(self.session_id)
            
            logger.info(f"[MemoryRunnable] Cleared memory for session '{self.session_id}'")
            
            return {
                "messages": [],
                "success": True,
                "session_id": self.session_id,
                "count": 0
            }
        
        except Exception as e:
            logger.error(f"[MemoryRunnable] Clear failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0
            }
    
    def with_session(self, session_id: str) -> "MemoryRunnable":
        """
        Create a new MemoryRunnable with different session ID.
        
        Args:
            session_id: New session identifier
        
        Returns:
            New MemoryRunnable instance
        """
        return MemoryRunnable(
            session_id=session_id,
            context_window=self.context_window,
            ttl_seconds=self.ttl_seconds,
            name=f"Memory:{session_id}",
            **self._config
        )
    
    def with_window(self, context_window: int) -> "MemoryRunnable":
        """
        Create a new MemoryRunnable with different context window.
        
        Args:
            context_window: Number of recent turns to include
        
        Returns:
            New MemoryRunnable instance
        """
        return MemoryRunnable(
            session_id=self.session_id,
            context_window=context_window,
            ttl_seconds=self.ttl_seconds,
            name=self.name,
            **self._config
        )
    
    def __repr__(self) -> str:
        return (
            f"MemoryRunnable("
            f"session='{self.session_id}', "
            f"window={self.context_window}, "
            f"ttl={self.ttl_seconds}"
            f")"
        )


# ============================================================================
# Redis Memory Runnable
# ============================================================================

class RedisMemoryRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible wrapper for Redis-backed memory operations.
    
    Wraps RedisMemoryManager to provide session-based conversation
    history storage with persistence and horizontal scaling support.
    
    Input format:
        {
            "action": "load" | "save" | "clear",  # operation to perform
            "messages": Optional[List[Dict]],  # messages to save (for save action)
            "context": Optional[Dict[str, Any]]  # additional context
        }
    
    Output format:
        {
            "messages": List[Dict],  # loaded/saved messages
            "success": bool,  # operation status
            "session_id": str,  # session identifier
            "count": int,  # number of messages
            "storage": "redis"  # storage type identifier
        }
    
    Example:
        memory = RedisMemoryRunnable(
            session_id="user_123",
            context_window=5,
            ttl_seconds=3600,
            credentials={"host": "localhost", "port": 6379}
        )
        
        # Load conversation history
        result = memory.invoke({"action": "load"})
        
        # Save new messages
        result = memory.invoke({
            "action": "save",
            "messages": [{"role": "user", "content": "Hello"}]
        })
    """
    
    def __init__(
        self,
        session_id: str,
        context_window: int = 5,
        ttl_seconds: Optional[int] = None,
        credentials: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Redis Memory Runnable.
        
        Args:
            session_id: Unique session identifier for conversation
            context_window: Number of recent turns to include when loading
            ttl_seconds: Time-to-live for stored messages (seconds)
            credentials: Redis connection credentials (host, port, password, etc.)
            name: Optional memory name
            **kwargs: Additional config
        """
        super().__init__(name=name or f"RedisMemory:{session_id}", **kwargs)
        self.session_id = session_id
        self.context_window = context_window
        self.ttl_seconds = ttl_seconds
        self.credentials = credentials or {}
        self._manager = None
    
    def _get_manager(self):
        """
        Get or create RedisMemoryManager instance (lazy initialization).
        
        Returns:
            RedisMemoryManager instance
        """
        if self._manager is None:
            from nodes.memory.redis_memory import RedisMemoryManager
            self._manager = RedisMemoryManager(self.credentials)
        return self._manager
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute Redis memory operation.
        
        Args:
            input: Dict with "action" and optional "messages"
            config: Runtime config
        
        Returns:
            Dict with messages, success status, and metadata
        """
        try:
            action = input.get("action", "load")
            
            if action == "load":
                return self._load_memory()
            
            elif action == "save":
                messages = input.get("messages", [])
                return self._save_memory(messages)
            
            elif action == "clear":
                return self._clear_memory()
            
            else:
                return {
                    "messages": [],
                    "success": False,
                    "error": f"Unknown action: {action}",
                    "session_id": self.session_id,
                    "count": 0,
                    "storage": "redis"
                }
        
        except Exception as e:
            logger.error(f"[RedisMemoryRunnable] Error during {input.get('action', 'unknown')}: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0,
                "storage": "redis"
            }
    
    def _load_memory(self) -> Dict[str, Any]:
        """
        Load conversation history from Redis.
        
        Returns:
            Dict with loaded messages
        """
        try:
            manager = self._get_manager()
            messages = manager.load(self.session_id, self.context_window)
            
            logger.info(
                f"[RedisMemoryRunnable] Loaded {len(messages)} messages "
                f"for session '{self.session_id}' from Redis"
            )
            
            return {
                "messages": messages,
                "success": True,
                "session_id": self.session_id,
                "count": len(messages),
                "storage": "redis"
            }
        
        except Exception as e:
            logger.error(f"[RedisMemoryRunnable] Load failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0,
                "storage": "redis"
            }
    
    def _save_memory(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Save conversation history to Redis.
        
        Args:
            messages: Messages to save
        
        Returns:
            Dict with save status
        """
        try:
            manager = self._get_manager()
            ttl = self.ttl_seconds or manager.DEFAULT_TTL_SECONDS
            
            manager.save(
                self.session_id,
                messages,
                ttl_seconds=ttl,
                context_window=self.context_window,
                auto_clear_on_full=True
            )
            
            logger.info(
                f"[RedisMemoryRunnable] Saved {len(messages)} messages "
                f"for session '{self.session_id}' to Redis (TTL: {ttl}s)"
            )
            
            return {
                "messages": messages,
                "success": True,
                "session_id": self.session_id,
                "count": len(messages),
                "storage": "redis"
            }
        
        except Exception as e:
            logger.error(f"[RedisMemoryRunnable] Save failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0,
                "storage": "redis"
            }
    
    def _clear_memory(self) -> Dict[str, Any]:
        """
        Clear conversation history from Redis.
        
        Returns:
            Dict with clear status
        """
        try:
            manager = self._get_manager()
            manager.clear(self.session_id)
            
            logger.info(f"[RedisMemoryRunnable] Cleared Redis memory for session '{self.session_id}'")
            
            return {
                "messages": [],
                "success": True,
                "session_id": self.session_id,
                "count": 0,
                "storage": "redis"
            }
        
        except Exception as e:
            logger.error(f"[RedisMemoryRunnable] Clear failed: {e}")
            return {
                "messages": [],
                "success": False,
                "error": str(e),
                "session_id": self.session_id,
                "count": 0,
                "storage": "redis"
            }
    
    def with_session(self, session_id: str) -> "RedisMemoryRunnable":
        """
        Create a new RedisMemoryRunnable with different session ID.
        
        Args:
            session_id: New session identifier
        
        Returns:
            New RedisMemoryRunnable instance
        """
        return RedisMemoryRunnable(
            session_id=session_id,
            context_window=self.context_window,
            ttl_seconds=self.ttl_seconds,
            credentials=self.credentials,
            name=f"RedisMemory:{session_id}",
            **self._config
        )
    
    def with_window(self, context_window: int) -> "RedisMemoryRunnable":
        """
        Create a new RedisMemoryRunnable with different context window.
        
        Args:
            context_window: Number of recent turns to include
        
        Returns:
            New RedisMemoryRunnable instance
        """
        return RedisMemoryRunnable(
            session_id=self.session_id,
            context_window=context_window,
            ttl_seconds=self.ttl_seconds,
            credentials=self.credentials,
            name=self.name,
            **self._config
        )
    
    def __repr__(self) -> str:
        return (
            f"RedisMemoryRunnable("
            f"session='{self.session_id}', "
            f"window={self.context_window}, "
            f"ttl={self.ttl_seconds}, "
            f"host='{self.credentials.get('host', 'localhost')}'"
            f")"
        )


# ============================================================================
# Factory Functions
# ============================================================================

def create_memory(
    session_id: str,
    context_window: int = 5,
    ttl_seconds: Optional[int] = None
) -> MemoryRunnable:
    """
    Factory function to create a MemoryRunnable.
    
    Args:
        session_id: Unique session identifier
        context_window: Number of recent turns to include
        ttl_seconds: Time-to-live for stored messages
    
    Returns:
        MemoryRunnable instance
    """
    return MemoryRunnable(
        session_id=session_id,
        context_window=context_window,
        ttl_seconds=ttl_seconds
    )


def create_redis_memory(
    session_id: str,
    context_window: int = 5,
    ttl_seconds: Optional[int] = None,
    credentials: Optional[Dict[str, Any]] = None
) -> RedisMemoryRunnable:
    """
    Factory function to create a RedisMemoryRunnable.
    
    Args:
        session_id: Unique session identifier
        context_window: Number of recent turns to include
        ttl_seconds: Time-to-live for stored messages
        credentials: Redis connection credentials
    
    Returns:
        RedisMemoryRunnable instance
    """
    return RedisMemoryRunnable(
        session_id=session_id,
        context_window=context_window,
        ttl_seconds=ttl_seconds,
        credentials=credentials
    )
