"""
Redis Memory Node for AI Agent conversation history storage.

This node provides Redis-backed conversation memory for AI Agent workflows,
equivalent to n8n's MemoryRedisChat node. Unlike the in-process BufferMemoryNode,
this stores conversations in Redis for:
  - Persistence across worker restarts
  - Shared memory across multiple workers (horizontal scaling)
  - TTL-based automatic expiration
  - Production-grade reliability

Architecture Notes:
  - Uses `redis-py` library for Redis communication
  - Compatible with Celery gevent pool (non-blocking operations)
  - Implements the same MemoryManager interface as buffer_memory.py
  - Outputs `ai_memory` type for AI Agent node consumption

Session Key Format:
  - Keys stored as: `memory:redis:{session_id}`
  - Messages serialized as JSON arrays
  - TTL managed by Redis EXPIRE command

Dependencies:
  - redis>=4.0.0 (install via: pip install redis)
"""
from __future__ import annotations

from typing import Dict, List, Any, Optional
import logging
import json
from time import time

from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#                          REDIS CONNECTION MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class _RedisConnectionManager:
    """
    Manages Redis connections with connection pooling and error handling.
    
    ARCHITECTURE NOTES:
    - Uses a shared connection pool to minimize connection overhead
    - Thread-safe and gevent-compatible
    - Lazy initialization (connects on first use)
    - Connection health checks before operations
    
    TODO: Consider implementing connection pool per credential set
          for multi-tenant scenarios with different Redis instances.
    """
    
    _pools: Dict[str, Any] = {}  # Cache of connection pools by config hash
    
    @classmethod
    def get_client(cls, credentials: Dict[str, Any]) -> Any:
        """
        Get a Redis client from the connection pool.
        
        Args:
            credentials: Dictionary containing Redis connection parameters
            
        Returns:
            redis.Redis client instance
            
        Raises:
            ImportError: If redis package is not installed
            ConnectionError: If connection to Redis fails
        """
        try:
            import redis
        except ImportError:
            raise ImportError(
                "Redis package not installed. Install with: pip install redis"
            )
        
        # Extract connection parameters from credentials
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 6379))
        database = int(credentials.get("database", 0))
        user = credentials.get("user", "") or None
        password = credentials.get("password", "") or None
        ssl = credentials.get("ssl", False)
        connection_timeout = int(credentials.get("connectionTimeout", 10))
        socket_timeout = int(credentials.get("socketTimeout", 30))
        
        # Create unique key for this connection configuration
        # NOTE: Password excluded from hash for security (logged as asterisks)
        config_key = f"{host}:{port}:{database}:{user or 'none'}:{ssl}"
        
        # Get or create connection pool
        if config_key not in cls._pools:
            logger.info(
                f"[RedisMemory] Creating new connection pool for {host}:{port} "
                f"(db={database}, ssl={ssl})"
            )
            
            pool = redis.ConnectionPool(
                host=host,
                port=port,
                db=database,
                username=user,
                password=password,
                socket_timeout=socket_timeout,
                socket_connect_timeout=connection_timeout,
                decode_responses=True,  # Return strings instead of bytes
                max_connections=10,  # Limit concurrent connections
                # TODO: Add SSL context configuration for custom certificates
            )
            
            if ssl:
                pool.connection_kwargs["ssl"] = True
                # TODO: Add ssl_cert_reqs and ssl_ca_certs for certificate validation
                logger.debug("[RedisMemory] SSL enabled for connection pool")
            
            cls._pools[config_key] = pool
        
        # Create client from pool
        client = redis.Redis(connection_pool=cls._pools[config_key])
        
        return client
    
    @classmethod
    def close_all(cls) -> None:
        """
        Close all connection pools.
        
        Call this during application shutdown for graceful cleanup.
        """
        for config_key, pool in cls._pools.items():
            try:
                pool.disconnect()
                logger.debug(f"[RedisMemory] Closed connection pool: {config_key}")
            except Exception as e:
                logger.warning(f"[RedisMemory] Error closing pool {config_key}: {e}")
        cls._pools.clear()


# ══════════════════════════════════════════════════════════════════════════════
#                          REDIS MEMORY MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class RedisMemoryManager:
    """
    Redis-backed memory manager for AI Agent conversation storage.
    
    Provides the same interface as MemoryManager from buffer_memory.py,
    but persists data to Redis instead of in-process memory.
    
    Key Features:
    - Persistent storage across worker restarts
    - Shared memory for horizontal scaling
    - TTL-based automatic cleanup (no background greenlet needed)
    - Context window truncation during load
    - System message preservation
    
    Thread Safety:
    - All operations are atomic at the Redis level
    - Safe for concurrent access from multiple workers
    
    Comparison with BufferMemoryNode's MemoryManager:
    ┌─────────────────────┬──────────────────────┬───────────────────────┐
    │ Feature             │ BufferMemoryNode     │ RedisMemoryNode       │
    ├─────────────────────┼──────────────────────┼───────────────────────┤
    │ Storage             │ In-process dict      │ Redis server          │
    │ Persistence         │ Lost on restart      │ Survives restarts     │
    │ Horizontal scaling  │ No (worker-local)    │ Yes (shared)          │
    │ TTL management      │ Background greenlet  │ Redis EXPIRE command  │
    │ Dependencies        │ None                 │ redis>=4.0.0          │
    │ Latency             │ ~0.01ms              │ ~1-5ms (network)      │
    └─────────────────────┴──────────────────────┴───────────────────────┘
    """
    
    DEFAULT_TTL_SECONDS = 3600  # 1 hour default session expiry
    KEY_PREFIX = "memory:redis:"  # Distinguishes from buffer_memory keys
    
    def __init__(self, credentials: Dict[str, Any]):
        """
        Initialize Redis memory manager with credentials.
        
        Args:
            credentials: Dictionary containing Redis connection parameters
        """
        self.credentials = credentials
        self._client = None
    
    def _get_client(self):
        """
        Get Redis client (lazy initialization).
        
        Returns:
            redis.Redis client instance
        """
        if self._client is None:
            self._client = _RedisConnectionManager.get_client(self.credentials)
        return self._client
    
    def _key(self, session_id: str) -> str:
        """
        Generate Redis key for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Fully qualified Redis key string
        """
        return f"{self.KEY_PREFIX}{session_id}"
    
    def load(self, session_id: str, context_window: int) -> List[Dict[str, Any]]:
        """
        Load conversation history for a session.
        
        Retrieves messages from Redis and applies context window truncation.
        System messages are always preserved.
        
        Args:
            session_id: Unique session identifier
            context_window: Number of recent turns to return (0 = all)
            
        Returns:
            List of message dictionaries with role and content
        """
        try:
            client = self._get_client()
            key = self._key(session_id)
            
            # Get stored messages JSON
            stored_json = client.get(key)
            
            if not stored_json:
                logger.debug(f"[RedisMemory] No messages found for session: {session_id}")
                return []
            
            # Parse JSON to list of messages
            stored = json.loads(stored_json)
            
            if not isinstance(stored, list):
                logger.warning(
                    f"[RedisMemory] Invalid data format for session {session_id}, "
                    f"expected list, got {type(stored)}"
                )
                return []
            
            # Separate system messages from conversation messages
            system_msgs = [m for m in stored if m.get("role") == "system"]
            non_system = [m for m in stored if m.get("role") != "system"]
            
            # Apply context window truncation
            # Window is number of "turns" (approximately 4 messages per turn)
            window = max(0, int(context_window))
            if window > 0:
                # Approximate 1 turn = up to 4 messages (user, assistant, tool calls, tool results)
                recent = non_system[-(window * 4):] if len(non_system) > window * 4 else non_system
            else:
                recent = non_system
            
            result = system_msgs + recent
            
            logger.debug(
                f"[RedisMemory] Loaded {len(result)} messages for session {session_id} "
                f"(window={context_window}, system={len(system_msgs)}, recent={len(recent)})"
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"[RedisMemory] JSON decode error for session {session_id}: {e}")
            return []
        except Exception as e:
            logger.error(f"[RedisMemory] Load failed for session {session_id}: {e}")
            return []
    
    def save(
        self,
        session_id: str,
        messages: List[Dict[str, Any]],
        ttl_seconds: Optional[int] = None,
        context_window: Optional[int] = None,
        auto_clear_on_full: bool = True
    ) -> None:
        """
        Save conversation messages to Redis.
        
        Stores messages as JSON with optional TTL and context window truncation.
        
        Args:
            session_id: Unique session identifier
            messages: List of message dictionaries to save
            ttl_seconds: Time-to-live in seconds (None = use default)
            context_window: If provided, truncate to N recent turns
            auto_clear_on_full: If True, clear old messages when window is full
        """
        try:
            client = self._get_client()
            key = self._key(session_id)
            
            # Apply context window truncation if specified
            if context_window is not None and context_window > 0:
                # Separate system from conversation messages
                system_msgs = [m for m in messages if m.get("role") == "system"]
                non_system = [m for m in messages if m.get("role") != "system"]
                
                # Calculate max messages based on window
                window = max(0, int(context_window))
                max_messages = window * 4  # 4 messages per turn
                
                # Count actual turns (user messages)
                user_messages = [m for m in non_system if m.get("role") == "user"]
                turn_count = len(user_messages)
                
                # AUTO-CLEAR LOGIC: Reset when window is full
                if auto_clear_on_full and turn_count >= window:
                    # Find last turn start (last user message)
                    user_indices = [i for i, m in enumerate(non_system) if m.get("role") == "user"]
                    last_turn_start = user_indices[-1] if user_indices else 0
                    recent = non_system[last_turn_start:]
                    
                    logger.info(
                        f"[RedisMemory] Auto-clear triggered for session {session_id}: "
                        f"Window FULL ({turn_count} turns >= {window} limit). "
                        f"Cleared {len(non_system) - len(recent)} old messages."
                    )
                else:
                    # Normal truncation
                    recent = non_system[-max_messages:] if len(non_system) > max_messages else non_system
                
                messages_to_save = system_msgs + recent
            else:
                # Hard cap to prevent unbounded growth (800 messages max)
                messages_to_save = messages[-800:] if len(messages) > 800 else messages
            
            # Serialize to JSON
            messages_json = json.dumps(messages_to_save, ensure_ascii=False)
            
            # Determine TTL
            effective_ttl = ttl_seconds if ttl_seconds is not None else self.DEFAULT_TTL_SECONDS
            
            # Save to Redis with TTL
            if effective_ttl > 0:
                client.setex(key, effective_ttl, messages_json)
            else:
                # TTL of 0 means no expiration
                client.set(key, messages_json)
            
            logger.debug(
                f"[RedisMemory] Saved {len(messages_to_save)} messages for session {session_id} "
                f"(ttl={effective_ttl}s)"
            )
            
        except Exception as e:
            logger.error(f"[RedisMemory] Save failed for session {session_id}: {e}")
            # NOTE: We don't raise here to avoid breaking the AI Agent workflow
            # Memory loss is preferable to workflow failure
    
    def clear(self, session_id: str) -> None:
        """
        Clear all messages for a session.
        
        Args:
            session_id: Unique session identifier
        """
        try:
            client = self._get_client()
            key = self._key(session_id)
            
            deleted = client.delete(key)
            
            if deleted:
                logger.info(f"[RedisMemory] Cleared session: {session_id}")
            else:
                logger.debug(f"[RedisMemory] Session not found (already cleared): {session_id}")
                
        except Exception as e:
            logger.error(f"[RedisMemory] Clear failed for session {session_id}: {e}")
    
    def exists(self, session_id: str) -> bool:
        """
        Check if a session has stored messages.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if session has messages, False otherwise
        """
        try:
            client = self._get_client()
            key = self._key(session_id)
            return bool(client.exists(key))
        except Exception as e:
            logger.error(f"[RedisMemory] Exists check failed for session {session_id}: {e}")
            return False
    
    def get_ttl(self, session_id: str) -> int:
        """
        Get remaining TTL for a session in seconds.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Remaining TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        try:
            client = self._get_client()
            key = self._key(session_id)
            return client.ttl(key)
        except Exception as e:
            logger.error(f"[RedisMemory] TTL check failed for session {session_id}: {e}")
            return -2


# ══════════════════════════════════════════════════════════════════════════════
#                          REDIS MEMORY NODE
# ══════════════════════════════════════════════════════════════════════════════

class RedisMemoryNode(BaseNode):
    """
    Redis-backed Memory Node for AI Agent conversation history.
    
    This node stores conversation memory in Redis for persistence and
    horizontal scaling. It outputs an `ai_memory` configuration that
    the AI Agent node consumes for context management.
    
    Equivalent to n8n's MemoryRedisChat node.
    
    Parameters:
        - sessionId: Unique session identifier (supports expressions)
        - sessionKey: Alternative session ID from previous node
        - contextWindowLength: Number of turns to include in context
        - ttlSeconds: Session expiration time
        
    Outputs:
        - ai_memory: Configuration object for AI Agent consumption
        
    Credentials:
        - redisApi: Redis connection credentials
        
    Usage in Workflow:
        ┌─────────────┐     ┌──────────────┐     ┌───────────┐
        │   Trigger   │────▶│ Redis Memory │────▶│ AI Agent  │
        └─────────────┘     └──────────────┘     └───────────┘
                                   │
                                   ▼
                             ┌───────────┐
                             │   Redis   │
                             │  Server   │
                             └───────────┘
    """
    
    type = "redis_memory"
    version = 1
    
    description = {
        "displayName": "Redis Chat Memory",
        "name": "redis_memory",
        "icon": "file:redis.svg",
        "group": ["ai"],
        "description": "Redis-backed memory for AI Agent conversation history with persistence and scaling support.",
        "defaults": {"name": "Redis Chat Memory"},
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
                "description": "Unique session identifier for this conversation. Supports expressions.",
            },
            {
                "name": "sessionKey",
                "type": NodeParameterType.STRING,
                "displayName": "Session Key From Previous Node",
                "default": "{{ $json.sessionId }}",
                "description": "Optional: Take the session ID from previous node data (overrides sessionId).",
            },
            {
                "name": "contextWindowLength",
                "type": NodeParameterType.NUMBER,
                "displayName": "Context Window Length",
                "default": 5,
                "typeOptions": {"minValue": 0, "maxValue": 50},
                "description": "Number of past conversation turns the AI model receives as context.",
            },
            {
                "name": "ttlSeconds",
                "type": NodeParameterType.NUMBER,
                "displayName": "Session TTL (seconds)",
                "default": 3600,
                "typeOptions": {"minValue": 0, "maxValue": 604800},  # Max 7 days
                "description": "How long to keep session memory. 0 = no expiration. Default: 1 hour.",
            },
            {
                "name": "separateSessionPerUser",
                "type": NodeParameterType.BOOLEAN,
                "displayName": "Separate Session Per User",
                "default": True,
                "description": "If enabled, each user gets their own conversation history.",
            },
        ],
        "credentials": [{"name": "redisApi", "required": True}],
    }
    
    icon = "redis.svg"
    color = "#D82C20"  # Redis brand color
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the Redis Memory node.
        
        Processes input items and outputs ai_memory configuration
        for each item. The AI Agent node uses this configuration
        to load/save conversation history.
        
        Returns:
            List of output items with ai_memory configuration
        """
        try:
            # Get input data (may be empty for first run)
            input_items = self.get_input_data() or [
                NodeExecutionData(json_data={}, binary_data=None)
            ]
            
            # Get Redis credentials
            credentials = self.get_credentials("redisApi")
            if not credentials:
                raise ValueError(
                    "Redis credentials not configured. "
                    "Please add Redis credentials to this node."
                )
            
            # Validate Redis connection on first execution
            # TODO: Consider caching connection validation to reduce latency
            self._validate_connection(credentials)
            
            output_items: List[NodeExecutionData] = []
            
            for idx, item in enumerate(input_items):
                try:
                    # Get parameters with expression evaluation
                    session_id = self.get_node_parameter("sessionId", idx, "default")
                    session_key = self.get_node_parameter("sessionKey", idx, "")
                    context_window = int(
                        self.get_node_parameter("contextWindowLength", idx, 5)
                    )
                    ttl_seconds = int(
                        self.get_node_parameter("ttlSeconds", idx, 3600)
                    )
                    separate_per_user = self.get_node_parameter(
                        "separateSessionPerUser", idx, True
                    )
                    
                    # Session key takes precedence if provided
                    final_session_id = session_key if session_key else session_id
                    
                    # Optionally include user context in session ID
                    # TODO: Get user ID from workflow context when available
                    if separate_per_user:
                        # For now, use session_id as-is
                        # In production, prepend user ID: f"{user_id}:{final_session_id}"
                        pass
                    
                    # Build ai_memory configuration
                    # This structure is consumed by the AI Agent node
                    memory_config = {
                        "type": "redis_memory",  # Identifies the memory type
                        "session_id": final_session_id,
                        "context_window_length": context_window,
                        "ttl_seconds": ttl_seconds,
                        "credentials": credentials,  # Passed for lazy loading
                    }
                    
                    # Preserve input data and add memory config
                    raw_json = item.json_data or {}
                    output_json = {**raw_json, "ai_memory": memory_config}
                    
                    output_items.append(
                        NodeExecutionData(
                            json_data=output_json,
                            binary_data=item.binary_data,
                        )
                    )
                    
                    logger.debug(
                        f"[RedisMemoryNode] Configured memory for session '{final_session_id}' "
                        f"(window={context_window}, ttl={ttl_seconds}s)"
                    )
                    
                except Exception as e:
                    logger.error(f"[RedisMemoryNode] Error processing item {idx}: {e}")
                    output_items.append(
                        NodeExecutionData(
                            json_data={"error": str(e), "item_index": idx},
                            binary_data=None,
                        )
                    )
            
            return [output_items]
            
        except Exception as e:
            logger.error(f"[RedisMemoryNode] Execution failed: {e}")
            return [
                [
                    NodeExecutionData(
                        json_data={"error": f"Redis Memory node error: {str(e)}"},
                        binary_data=None,
                    )
                ]
            ]
    
    def _validate_connection(self, credentials: Dict[str, Any]) -> None:
        """
        Validate Redis connection before processing.
        
        Args:
            credentials: Redis connection credentials
            
        Raises:
            ConnectionError: If Redis is unreachable
        """
        try:
            client = _RedisConnectionManager.get_client(credentials)
            
            # Simple PING to verify connection
            response = client.ping()
            
            if not response:
                raise ConnectionError("Redis PING failed")
                
            logger.debug("[RedisMemoryNode] Redis connection validated")
            
        except ImportError:
            raise ImportError(
                "Redis package not installed. Install with: pip install redis"
            )
        except Exception as e:
            logger.error(f"[RedisMemoryNode] Connection validation failed: {e}")
            raise ConnectionError(f"Cannot connect to Redis: {str(e)}")
    
    # ══════════════════════════════════════════════════════════════════════════
    #                      LANGCHAIN RUNNABLE INTEGRATION
    # ══════════════════════════════════════════════════════════════════════════
    
    def get_runnable(self, item_index: int = 0):
        """
        Get LangChain-compatible Runnable for LCEL composition.
        
        Creates a MemoryRunnable that wraps Redis memory operations,
        enabling integration with LangChain chains and agents.
        
        Args:
            item_index: Index of the input item for parameter resolution
            
        Returns:
            MemoryRunnable: A Runnable for memory operations
            
        Example:
            memory = redis_memory_node.get_runnable()
            
            # Load conversation history
            result = memory.invoke({"action": "load"})
            
            # Save new messages
            result = memory.invoke({
                "action": "save",
                "messages": [{"role": "user", "content": "Hello"}]
            })
        """
        # Import here to avoid circular dependencies
        from utils.langchain_memory import RedisMemoryRunnable
        
        # Get parameters
        session_id = self.get_node_parameter("sessionId", item_index, "default")
        session_key = self.get_node_parameter("sessionKey", item_index, "")
        context_window = int(self.get_node_parameter("contextWindowLength", item_index, 5))
        ttl_seconds = int(self.get_node_parameter("ttlSeconds", item_index, 3600))
        
        # Get credentials
        credentials = self.get_credentials("redisApi")
        if not credentials:
            raise ValueError("Redis credentials not configured")
        
        # Use session_key if provided
        final_session_id = session_key if session_key else session_id
        
        # Create Runnable
        runnable = RedisMemoryRunnable(
            session_id=final_session_id,
            context_window=context_window,
            ttl_seconds=ttl_seconds,
            credentials=credentials,
        )
        
        logger.info(
            f"[RedisMemoryNode] Created RedisMemoryRunnable for session '{final_session_id}' "
            f"(window={context_window}, ttl={ttl_seconds}s)"
        )
        
        return runnable
    
    def get_memory_manager(self, item_index: int = 0) -> RedisMemoryManager:
        """
        Get a RedisMemoryManager instance for direct memory operations.
        
        Useful for programmatic access outside of workflow execution.
        
        Args:
            item_index: Index of the input item for parameter resolution
            
        Returns:
            RedisMemoryManager: Manager instance for memory operations
        """
        credentials = self.get_credentials("redisApi")
        if not credentials:
            raise ValueError("Redis credentials not configured")
        
        return RedisMemoryManager(credentials)


# ══════════════════════════════════════════════════════════════════════════════
#                          CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def create_redis_memory_manager(credentials: Dict[str, Any]) -> RedisMemoryManager:
    """
    Factory function to create a RedisMemoryManager.
    
    Useful for direct access outside of node execution context.
    
    Args:
        credentials: Dictionary with Redis connection parameters
                    (host, port, database, user, password, ssl)
        
    Returns:
        RedisMemoryManager instance
        
    Example:
        from nodes.memory.redis_memory import create_redis_memory_manager
        
        manager = create_redis_memory_manager({
            "host": "localhost",
            "port": 6379,
            "database": 0,
            "password": "secret"
        })
        
        # Load messages
        messages = manager.load("session-123", context_window=5)
        
        # Save messages
        manager.save("session-123", messages, ttl_seconds=3600)
    """
    return RedisMemoryManager(credentials)
