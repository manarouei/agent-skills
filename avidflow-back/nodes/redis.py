"""
Redis node for Redis database operations.

Based on n8n's Redis node implementation.
Supports operations:
- Delete: Delete a key from Redis
- Get: Get the value of a key
- Increment: Atomically increment a key by 1
- Info: Get Redis server information
- Keys: Get all keys matching a pattern
- List Length: Get the length of a list
- Pop: Pop data from a Redis list
- Publish: Publish message to a Redis channel
- Push: Push data to a Redis list
- Set: Set the value of a key

Compatible with the existing redisApi credential type.
"""
import redis
import json
import logging
from typing import Dict, List, Optional, Any, Union

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class RedisNode(BaseNode):
    """
    Redis node for interacting with Redis database.
    
    Provides full CRUD operations, list manipulation, pub/sub,
    and server info capabilities.
    """

    type = "redis"
    version = 1

    description = {
        "displayName": "Redis",
        "name": "redis",
        "icon": "file:redis.svg",
        "group": ["input"],
        "description": "Get, send and update data in Redis",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "parameters": [
            # ----------------------------------
            # Operation Selection
            # ----------------------------------
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {
                        "name": "Delete",
                        "value": "delete",
                        "description": "Delete a key from Redis",
                    },
                    {
                        "name": "Get",
                        "value": "get",
                        "description": "Get the value of a key from Redis",
                    },
                    {
                        "name": "Increment",
                        "value": "incr",
                        "description": "Atomically increments a key by 1. Creates the key if it does not exist.",
                    },
                    {
                        "name": "Info",
                        "value": "info",
                        "description": "Returns generic information about the Redis instance",
                    },
                    {
                        "name": "Keys",
                        "value": "keys",
                        "description": "Returns all keys matching a pattern",
                    },
                    {
                        "name": "List Length",
                        "value": "llen",
                        "description": "Returns the length of a list",
                    },
                    {
                        "name": "Pop",
                        "value": "pop",
                        "description": "Pop data from a Redis list",
                    },
                    {
                        "name": "Publish",
                        "value": "publish",
                        "description": "Publish message to Redis channel",
                    },
                    {
                        "name": "Push",
                        "value": "push",
                        "description": "Push data to a Redis list",
                    },
                    {
                        "name": "Set",
                        "value": "set",
                        "description": "Set the value of a key in Redis",
                    },
                ],
                "default": "info",
                "description": "The operation to perform",
            },
            
            # ----------------------------------
            # DELETE Operation Parameters
            # ----------------------------------
            {
                "name": "key",
                "type": NodeParameterType.STRING,
                "display_name": "Key",
                "default": "",
                "required": True,
                "description": "Name of the key to delete from Redis",
                "display_options": {"show": {"operation": ["delete"]}},
            },
            
            # ----------------------------------
            # GET Operation Parameters
            # ----------------------------------
            {
                "name": "propertyName",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "propertyName",
                "required": True,
                "description": "Name of the property to write received data to. Supports dot-notation (e.g., 'data.person[0].name').",
                "display_options": {"show": {"operation": ["get"]}},
            },
            {
                "name": "key",
                "type": NodeParameterType.STRING,
                "display_name": "Key",
                "default": "",
                "required": True,
                "description": "Name of the key to get from Redis",
                "display_options": {"show": {"operation": ["get"]}},
            },
            {
                "name": "keyType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Key Type",
                "options": [
                    {
                        "name": "Automatic",
                        "value": "automatic",
                        "description": "Requests the type before requesting the data (slower)",
                    },
                    {
                        "name": "Hash",
                        "value": "hash",
                        "description": "Data in key is of type 'hash'",
                    },
                    {
                        "name": "List",
                        "value": "list",
                        "description": "Data in key is of type 'list'",
                    },
                    {
                        "name": "Sets",
                        "value": "sets",
                        "description": "Data in key is of type 'sets'",
                    },
                    {
                        "name": "String",
                        "value": "string",
                        "description": "Data in key is of type 'string'",
                    },
                ],
                "default": "automatic",
                "description": "The type of the key to get",
                "display_options": {"show": {"operation": ["get"]}},
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "dotNotation",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Dot Notation",
                        "default": True,
                        "description": "By default, dot-notation is used in property names. This means that 'a.b' will set the property 'b' underneath 'a' so {'a': {'b': value}}. If deactivated, it will set {'a.b': value} instead.",
                    },
                ],
                "display_options": {"show": {"operation": ["get"]}},
            },
            
            # ----------------------------------
            # INCREMENT Operation Parameters
            # ----------------------------------
            {
                "name": "key",
                "type": NodeParameterType.STRING,
                "display_name": "Key",
                "default": "",
                "required": True,
                "description": "Name of the key to increment",
                "display_options": {"show": {"operation": ["incr"]}},
            },
            {
                "name": "expire",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Expire",
                "default": False,
                "description": "Whether to set a timeout on key",
                "display_options": {"show": {"operation": ["incr"]}},
            },
            {
                "name": "ttl",
                "type": NodeParameterType.NUMBER,
                "display_name": "TTL",
                "default": 60,
                "description": "Number of seconds before key expiration",
                "display_options": {"show": {"operation": ["incr"], "expire": [True]}},
            },
            
            # ----------------------------------
            # KEYS Operation Parameters
            # ----------------------------------
            {
                "name": "keyPattern",
                "type": NodeParameterType.STRING,
                "display_name": "Key Pattern",
                "default": "",
                "required": True,
                "description": "The key pattern for the keys to return (e.g., 'user:*', 'session:*')",
                "display_options": {"show": {"operation": ["keys"]}},
            },
            {
                "name": "getValues",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Get Values",
                "default": True,
                "description": "Whether to get the value of matching keys",
                "display_options": {"show": {"operation": ["keys"]}},
            },
            
            # ----------------------------------
            # LLEN (List Length) Operation Parameters
            # ----------------------------------
            {
                "name": "list",
                "type": NodeParameterType.STRING,
                "display_name": "List",
                "default": "",
                "required": True,
                "description": "Name of the list in Redis",
                "display_options": {"show": {"operation": ["llen"]}},
            },
            
            # ----------------------------------
            # SET Operation Parameters
            # ----------------------------------
            {
                "name": "key",
                "type": NodeParameterType.STRING,
                "display_name": "Key",
                "default": "",
                "required": True,
                "description": "Name of the key to set in Redis",
                "display_options": {"show": {"operation": ["set"]}},
            },
            {
                "name": "value",
                "type": NodeParameterType.STRING,
                "display_name": "Value",
                "default": "",
                "description": "The value to write in Redis",
                "display_options": {"show": {"operation": ["set"]}},
            },
            {
                "name": "keyType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Key Type",
                "options": [
                    {
                        "name": "Automatic",
                        "value": "automatic",
                        "description": "Tries to figure out the type automatically depending on the data",
                    },
                    {
                        "name": "Hash",
                        "value": "hash",
                        "description": "Data in key is of type 'hash'",
                    },
                    {
                        "name": "List",
                        "value": "list",
                        "description": "Data in key is of type 'list'",
                    },
                    {
                        "name": "Sets",
                        "value": "sets",
                        "description": "Data in key is of type 'sets'",
                    },
                    {
                        "name": "String",
                        "value": "string",
                        "description": "Data in key is of type 'string'",
                    },
                ],
                "default": "automatic",
                "description": "The type of the key to set",
                "display_options": {"show": {"operation": ["set"]}},
            },
            {
                "name": "valueIsJSON",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Value Is JSON",
                "default": True,
                "description": "Whether the value is JSON or key-value pairs",
                "display_options": {"show": {"operation": ["set"], "keyType": ["hash"]}},
            },
            {
                "name": "expire",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Expire",
                "default": False,
                "description": "Whether to set a timeout on key",
                "display_options": {"show": {"operation": ["set"]}},
            },
            {
                "name": "ttl",
                "type": NodeParameterType.NUMBER,
                "display_name": "TTL",
                "default": 60,
                "description": "Number of seconds before key expiration",
                "display_options": {"show": {"operation": ["set"], "expire": [True]}},
            },
            
            # ----------------------------------
            # PUBLISH Operation Parameters
            # ----------------------------------
            {
                "name": "channel",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "description": "Channel name",
                "display_options": {"show": {"operation": ["publish"]}},
            },
            {
                "name": "messageData",
                "type": NodeParameterType.STRING,
                "display_name": "Data",
                "default": "",
                "required": True,
                "description": "Data to publish",
                "display_options": {"show": {"operation": ["publish"]}},
            },
            
            # ----------------------------------
            # PUSH Operation Parameters
            # ----------------------------------
            {
                "name": "list",
                "type": NodeParameterType.STRING,
                "display_name": "List",
                "default": "",
                "required": True,
                "description": "Name of the list in Redis",
                "display_options": {"show": {"operation": ["push"]}},
            },
            {
                "name": "messageData",
                "type": NodeParameterType.STRING,
                "display_name": "Data",
                "default": "",
                "required": True,
                "description": "Data to push",
                "display_options": {"show": {"operation": ["push"]}},
            },
            {
                "name": "tail",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Tail",
                "default": False,
                "description": "Whether to push data to the end of the list (RPUSH) instead of the beginning (LPUSH)",
                "display_options": {"show": {"operation": ["push"]}},
            },
            
            # ----------------------------------
            # POP Operation Parameters
            # ----------------------------------
            {
                "name": "list",
                "type": NodeParameterType.STRING,
                "display_name": "List",
                "default": "",
                "required": True,
                "description": "Name of the list in Redis",
                "display_options": {"show": {"operation": ["pop"]}},
            },
            {
                "name": "tail",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Tail",
                "default": False,
                "description": "Whether to pop data from the end of the list (RPOP) instead of the beginning (LPOP)",
                "display_options": {"show": {"operation": ["pop"]}},
            },
            {
                "name": "propertyName",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "propertyName",
                "description": "Optional name of the property to write received data to. Supports dot-notation.",
                "display_options": {"show": {"operation": ["pop"]}},
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "dotNotation",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Dot Notation",
                        "default": True,
                        "description": "By default, dot-notation is used in property names. This means that 'a.b' will set the property 'b' underneath 'a' so {'a': {'b': value}}. If deactivated, it will set {'a.b': value} instead.",
                    },
                ],
                "display_options": {"show": {"operation": ["pop"]}},
            },
        ],
        "credentials": [{"name": "redisApi", "required": True}],
    }

    icon = "redis.svg"
    color = "#D82C20"
    
    # ----------------------------------
    # Helper Methods
    # ----------------------------------
    
    def _get_redis_client(self) -> redis.Redis:
        """
        Create and return a Redis client using the configured credentials.
        
        Returns:
            redis.Redis: Configured Redis client instance
            
        Raises:
            Exception: If credentials are not properly configured
        """
        credentials = self.get_credentials("redisApi")
        
        if not credentials:
            raise Exception("Redis credentials not configured")
        
        # Extract connection parameters from credentials
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 6379))
        database = int(credentials.get("database", 0))
        user = credentials.get("user", "") or None
        password = credentials.get("password", "") or None
        ssl = credentials.get("ssl", False)
        connection_timeout = int(credentials.get("connectionTimeout", 10))
        socket_timeout = int(credentials.get("socketTimeout", 30))
        
        # Create Redis client
        client = redis.Redis(
            host=host,
            port=port,
            db=database,
            username=user if user else None,
            password=password if password else None,
            ssl=ssl,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connection_timeout,
            decode_responses=True  # Return strings instead of bytes
        )
        
        return client
    
    def _convert_info_to_object(self, string_data: str) -> Dict[str, Any]:
        """
        Convert Redis INFO string response into a structured dictionary.
        
        Args:
            string_data: Raw INFO command output from Redis
            
        Returns:
            Dictionary with parsed Redis info
        """
        return_data: Dict[str, Any] = {}
        
        for line in string_data.split('\n'):
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
                
            # Split key:value pairs
            if ':' not in line:
                continue
                
            key, value = line.split(':', 1)
            value = value.strip()
            
            # Handle nested values (e.g., cmdstat_get:calls=100,usec=500)
            if '=' in value:
                return_data[key] = {}
                for key_value_pair in value.split(','):
                    if '=' in key_value_pair:
                        k2, v2 = key_value_pair.split('=', 1)
                        return_data[key][k2] = self._parse_value(v2)
            else:
                return_data[key] = self._parse_value(value)
        
        return return_data
    
    def _parse_value(self, value: str) -> Union[str, int, float]:
        """
        Parse a string value into appropriate type (number or string).
        
        Args:
            value: String value to parse
            
        Returns:
            Parsed value as int, float, or string
        """
        # Check if the value is numeric
        if value.replace('.', '', 1).replace('-', '', 1).isdigit():
            if '.' in value:
                return float(value)
            return int(value)
        return value
    
    async def _get_value(
        self, 
        client: redis.Redis, 
        key_name: str, 
        key_type: Optional[str] = None
    ) -> Any:
        """
        Get value from Redis with automatic type detection.
        
        Args:
            client: Redis client instance
            key_name: Name of the key to retrieve
            key_type: Optional type hint ('string', 'hash', 'list', 'sets', 'automatic')
            
        Returns:
            Value from Redis (type depends on stored data type)
        """
        # Auto-detect type if needed
        if key_type is None or key_type == "automatic":
            key_type = client.type(key_name)
        
        if key_type == "string":
            return client.get(key_name)
        elif key_type == "hash":
            return client.hgetall(key_name)
        elif key_type == "list":
            return client.lrange(key_name, 0, -1)
        elif key_type in ("sets", "set"):
            return list(client.smembers(key_name))
        else:
            # Unknown type, try to get as string
            return client.get(key_name)
    
    async def _set_value(
        self,
        client: redis.Redis,
        key_name: str,
        value: Union[str, int, float, List, Dict],
        expire: bool,
        ttl: int,
        key_type: Optional[str] = None,
        value_is_json: bool = True
    ) -> None:
        """
        Set value in Redis with automatic type detection.
        
        Args:
            client: Redis client instance
            key_name: Name of the key to set
            value: Value to store
            expire: Whether to set expiration
            ttl: Time-to-live in seconds (if expire is True)
            key_type: Optional type hint ('string', 'hash', 'list', 'sets', 'automatic')
            value_is_json: Whether hash values should be parsed as JSON
        """
        # Auto-detect type if needed
        if key_type is None or key_type == "automatic":
            if isinstance(value, str):
                # Try to parse as JSON to determine type
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        key_type = "list"
                        value = parsed
                    elif isinstance(parsed, dict):
                        key_type = "hash"
                        value = parsed
                    else:
                        key_type = "string"
                except (json.JSONDecodeError, TypeError):
                    key_type = "string"
            elif isinstance(value, list):
                key_type = "list"
            elif isinstance(value, dict):
                key_type = "hash"
            else:
                key_type = "string"
        
        # Set value based on type
        if key_type == "string":
            client.set(key_name, str(value))
        elif key_type == "hash":
            if value_is_json:
                # Parse JSON if it's a string
                values = value
                if isinstance(value, str):
                    try:
                        values = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        values = {"value": value}
                
                # Set hash values
                if isinstance(values, dict):
                    for k, v in values.items():
                        client.hset(key_name, k, str(v) if v is not None else "")
            else:
                # Key-value pair format (space separated)
                if isinstance(value, str):
                    pairs = value.split(' ')
                    if len(pairs) >= 2:
                        for i in range(0, len(pairs) - 1, 2):
                            client.hset(key_name, pairs[i], pairs[i + 1])
        elif key_type == "list":
            # Clear existing list and add new values
            client.delete(key_name)
            if isinstance(value, list):
                for item in value:
                    client.rpush(key_name, str(item))
            else:
                client.rpush(key_name, str(value))
        elif key_type in ("sets", "set"):
            # Clear existing set and add new values
            client.delete(key_name)
            if isinstance(value, list):
                for item in value:
                    client.sadd(key_name, str(item))
            else:
                client.sadd(key_name, str(value))
        
        # Set expiration if requested
        if expire and ttl > 0:
            client.expire(key_name, ttl)
    
    def _set_nested_value(
        self, 
        obj: Dict[str, Any], 
        path: str, 
        value: Any, 
        use_dot_notation: bool = True
    ) -> None:
        """
        Set a nested value in a dictionary using dot notation.
        
        Args:
            obj: Target dictionary
            path: Property path (e.g., 'a.b.c' or 'a.b[0].c')
            value: Value to set
            use_dot_notation: Whether to interpret dots as nesting
        """
        if not use_dot_notation:
            obj[path] = value
            return
        
        keys = path.replace('[', '.').replace(']', '').split('.')
        current = obj
        
        for i, key in enumerate(keys[:-1]):
            if key.isdigit():
                key = int(key)
            if isinstance(current, list):
                while len(current) <= key:
                    current.append({})
                if not isinstance(current[key], (dict, list)):
                    current[key] = {}
                current = current[key]
            else:
                if key not in current:
                    # Check if next key is numeric (array index)
                    next_key = keys[i + 1] if i + 1 < len(keys) else None
                    if next_key and next_key.isdigit():
                        current[key] = []
                    else:
                        current[key] = {}
                current = current[key]
        
        final_key = keys[-1]
        if final_key.isdigit():
            final_key = int(final_key)
            while len(current) <= final_key:
                current.append(None)
        current[final_key] = value
    
    # ----------------------------------
    # Execute Method
    # ----------------------------------
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the Redis operation based on the configured parameters.
        
        Returns:
            List of NodeExecutionData containing operation results
        """
        input_data = self.get_input_data()
        results: List[NodeExecutionData] = []
        client = None
        
        try:
            # Get operation type
            operation = self.get_node_parameter("operation", 0, "info")
            
            # Create Redis client
            client = self._get_redis_client()
            
            # Test connection
            client.ping()
            
            # Handle INFO operation (no input items needed)
            if operation == "info":
                try:
                    info_result = client.info()
                    # info() returns dict in redis-py, convert if needed
                    if isinstance(info_result, str):
                        parsed_info = self._convert_info_to_object(info_result)
                    else:
                        parsed_info = info_result
                    results.append(NodeExecutionData(json_data=parsed_info))
                except Exception as e:
                    logger.error(f"Redis INFO operation failed: {e}")
                    results.append(NodeExecutionData(json_data={"error": str(e)}))
                
                return [results]
            
            # Process each input item for other operations
            if not input_data:
                input_data = [NodeExecutionData(json_data={})]
            
            for item_index, item in enumerate(input_data):
                try:
                    result_json: Dict[str, Any] = {}
                    
                    if operation == "delete":
                        # DELETE operation
                        key = self.get_node_parameter("key", item_index, "")
                        if key:
                            client.delete(key)
                            result_json = {"deleted": True, "key": key}
                        else:
                            result_json = {"deleted": False, "error": "No key specified"}
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    elif operation == "get":
                        # GET operation
                        property_name = self.get_node_parameter("propertyName", item_index, "propertyName")
                        key = self.get_node_parameter("key", item_index, "")
                        key_type = self.get_node_parameter("keyType", item_index, "automatic")
                        options = self.get_node_parameter("options", item_index, {}) or {}
                        use_dot_notation = options.get("dotNotation", True)
                        
                        if key:
                            # Get value from Redis (synchronously for redis-py)
                            value = self._get_value_sync(client, key, key_type)
                            
                            # Set value using dot notation if enabled
                            if use_dot_notation:
                                self._set_nested_value(result_json, property_name, value, True)
                            else:
                                result_json[property_name] = value
                        
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    elif operation == "incr":
                        # INCREMENT operation
                        key = self.get_node_parameter("key", item_index, "")
                        expire = self.get_node_parameter("expire", item_index, False)
                        ttl = self.get_node_parameter("ttl", item_index, 60)
                        
                        if key:
                            increment_val = client.incr(key)
                            if expire and ttl > 0:
                                client.expire(key, ttl)
                            result_json = {key: increment_val}
                        
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    elif operation == "keys":
                        # KEYS operation
                        key_pattern = self.get_node_parameter("keyPattern", item_index, "*")
                        get_values = self.get_node_parameter("getValues", item_index, True)
                        
                        keys = client.keys(key_pattern)
                        
                        if not get_values:
                            # Return just the keys list
                            result_json = {"keys": keys}
                        else:
                            # Get values for each key
                            for key_name in keys:
                                value = self._get_value_sync(client, key_name)
                                result_json[key_name] = value
                        
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    elif operation == "llen":
                        # LIST LENGTH operation
                        list_name = self.get_node_parameter("list", item_index, "")
                        
                        if list_name:
                            length = client.llen(list_name)
                            result_json = {list_name: length}
                        
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    elif operation == "set":
                        # SET operation
                        key = self.get_node_parameter("key", item_index, "")
                        value = self.get_node_parameter("value", item_index, "")
                        key_type = self.get_node_parameter("keyType", item_index, "automatic")
                        value_is_json = self.get_node_parameter("valueIsJSON", item_index, True)
                        expire = self.get_node_parameter("expire", item_index, False)
                        ttl = self.get_node_parameter("ttl", item_index, 60)
                        
                        if key:
                            self._set_value_sync(
                                client, key, value, expire, ttl, key_type, value_is_json
                            )
                            # Return the original input item
                            results.append(NodeExecutionData(json_data=item.json_data if item.json_data else {"success": True, "key": key}))
                        else:
                            results.append(NodeExecutionData(json_data={"error": "No key specified"}))
                    
                    elif operation == "publish":
                        # PUBLISH operation
                        channel = self.get_node_parameter("channel", item_index, "")
                        message_data = self.get_node_parameter("messageData", item_index, "")
                        
                        if channel:
                            subscribers = client.publish(channel, message_data)
                            result_json = {
                                "channel": channel,
                                "subscribers": subscribers,
                                "message": message_data
                            }
                            results.append(NodeExecutionData(json_data=item.json_data if item.json_data else result_json))
                        else:
                            results.append(NodeExecutionData(json_data={"error": "No channel specified"}))
                    
                    elif operation == "push":
                        # PUSH operation
                        list_name = self.get_node_parameter("list", item_index, "")
                        message_data = self.get_node_parameter("messageData", item_index, "")
                        tail = self.get_node_parameter("tail", item_index, False)
                        
                        if list_name:
                            if tail:
                                client.rpush(list_name, message_data)
                            else:
                                client.lpush(list_name, message_data)
                            # Return the original input item
                            results.append(NodeExecutionData(json_data=item.json_data if item.json_data else {"success": True, "list": list_name}))
                        else:
                            results.append(NodeExecutionData(json_data={"error": "No list specified"}))
                    
                    elif operation == "pop":
                        # POP operation
                        list_name = self.get_node_parameter("list", item_index, "")
                        tail = self.get_node_parameter("tail", item_index, False)
                        property_name = self.get_node_parameter("propertyName", item_index, "propertyName")
                        options = self.get_node_parameter("options", item_index, {}) or {}
                        use_dot_notation = options.get("dotNotation", True)
                        
                        if list_name:
                            if tail:
                                value = client.rpop(list_name)
                            else:
                                value = client.lpop(list_name)
                            
                            # Try to parse as JSON
                            output_value = value
                            if value:
                                try:
                                    output_value = json.loads(value)
                                except (json.JSONDecodeError, TypeError):
                                    output_value = value
                            
                            # Set value using dot notation if enabled
                            if use_dot_notation:
                                self._set_nested_value(result_json, property_name, output_value, True)
                            else:
                                result_json[property_name] = output_value
                        
                        results.append(NodeExecutionData(json_data=result_json))
                    
                    else:
                        # Unknown operation
                        results.append(NodeExecutionData(
                            json={"error": f"Unknown operation: {operation}"}
                        ))
                
                except Exception as e:
                    logger.error(f"Redis operation '{operation}' failed for item {item_index}: {e}")
                    results.append(NodeExecutionData(
                        json={"error": str(e)},
                        pairedItem={"item": item_index}
                    ))
            
            return [results]
        
        except redis.AuthenticationError as e:
            logger.error(f"Redis authentication failed: {e}")
            return [[NodeExecutionData(json_data={"error": f"Authentication failed: {str(e)}"})]]
        
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            return [[NodeExecutionData(json_data={"error": f"Connection failed: {str(e)}"})]]
        
        except redis.TimeoutError as e:
            logger.error(f"Redis timeout: {e}")
            return [[NodeExecutionData(json_data={"error": f"Connection timeout: {str(e)}"})]]
        
        except Exception as e:
            logger.error(f"Redis operation failed: {e}")
            return [[NodeExecutionData(json_data={"error": str(e)})]]
        
        finally:
            # Ensure the Redis client is always closed
            if client:
                try:
                    client.close()
                except Exception:
                    # Ignore close errors
                    pass
    
    # ----------------------------------
    # Synchronous Helper Methods
    # (redis-py is synchronous by default)
    # ----------------------------------
    
    def _get_value_sync(
        self, 
        client: redis.Redis, 
        key_name: str, 
        key_type: Optional[str] = None
    ) -> Any:
        """
        Synchronous version of _get_value for redis-py.
        
        Args:
            client: Redis client instance
            key_name: Name of the key to retrieve
            key_type: Optional type hint
            
        Returns:
            Value from Redis
        """
        # Auto-detect type if needed
        if key_type is None or key_type == "automatic":
            key_type = client.type(key_name)
        
        if key_type == "string":
            return client.get(key_name)
        elif key_type == "hash":
            return client.hgetall(key_name)
        elif key_type == "list":
            return client.lrange(key_name, 0, -1)
        elif key_type in ("sets", "set"):
            return list(client.smembers(key_name))
        elif key_type == "none":
            # Key doesn't exist
            return None
        else:
            # Try to get as string for unknown types
            return client.get(key_name)
    
    def _set_value_sync(
        self,
        client: redis.Redis,
        key_name: str,
        value: Union[str, int, float, List, Dict],
        expire: bool,
        ttl: int,
        key_type: Optional[str] = None,
        value_is_json: bool = True
    ) -> None:
        """
        Synchronous version of _set_value for redis-py.
        
        Args:
            client: Redis client instance
            key_name: Name of the key to set
            value: Value to store
            expire: Whether to set expiration
            ttl: Time-to-live in seconds
            key_type: Optional type hint
            value_is_json: Whether hash values should be parsed as JSON
        """
        # Auto-detect type if needed
        if key_type is None or key_type == "automatic":
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        key_type = "list"
                        value = parsed
                    elif isinstance(parsed, dict):
                        key_type = "hash"
                        value = parsed
                    else:
                        key_type = "string"
                except (json.JSONDecodeError, TypeError):
                    key_type = "string"
            elif isinstance(value, list):
                key_type = "list"
            elif isinstance(value, dict):
                key_type = "hash"
            else:
                key_type = "string"
        
        # Set value based on type
        if key_type == "string":
            client.set(key_name, str(value))
        elif key_type == "hash":
            if value_is_json:
                values = value
                if isinstance(value, str):
                    try:
                        values = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        values = {"value": value}
                
                if isinstance(values, dict):
                    # Delete existing key first for clean update
                    client.delete(key_name)
                    for k, v in values.items():
                        client.hset(key_name, k, str(v) if v is not None else "")
            else:
                pairs = value.split(' ') if isinstance(value, str) else []
                if len(pairs) >= 2:
                    client.delete(key_name)
                    for i in range(0, len(pairs) - 1, 2):
                        client.hset(key_name, pairs[i], pairs[i + 1])
        elif key_type == "list":
            client.delete(key_name)
            if isinstance(value, list):
                for item in value:
                    client.rpush(key_name, str(item))
            elif isinstance(value, str):
                # Try to parse as JSON array
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        for item in parsed:
                            client.rpush(key_name, str(item))
                    else:
                        client.rpush(key_name, str(value))
                except (json.JSONDecodeError, TypeError):
                    client.rpush(key_name, str(value))
            else:
                client.rpush(key_name, str(value))
        elif key_type in ("sets", "set"):
            client.delete(key_name)
            if isinstance(value, list):
                for item in value:
                    client.sadd(key_name, str(item))
            elif isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        for item in parsed:
                            client.sadd(key_name, str(item))
                    else:
                        client.sadd(key_name, str(value))
                except (json.JSONDecodeError, TypeError):
                    client.sadd(key_name, str(value))
            else:
                client.sadd(key_name, str(value))
        
        # Set expiration if requested
        if expire and ttl > 0:
            client.expire(key_name, ttl)
