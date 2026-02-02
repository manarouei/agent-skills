#!/usr/bin/env python3
"""
Redis Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: convert-redis-debug-002
Generated: 2026-02-02T05:32:58.920035

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List
from urllib.parse import quote

import requests

from .base import BaseNode, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class RedisNode(BaseNode):
    """
    Redis node.
    
    
    """

    type = "redis"
    version = 1
    
    description = {
        "displayName": "Redis",
        "name": "redis",
        "icon": "file:redis.svg",
        "group": ['output'],
        "description": "",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Delete", "value": "delete", "description": "Delete a key from Redis", "display_options": {'show': {'resource': ['']}}},
                {"name": "Get", "value": "get", "description": "Get the value of a key from Redis", "display_options": {'show': {'resource': ['']}}},
                {"name": "Increment", "value": "incr", "description": "Atomically increments a key by 1. Creates the key if it does not exist.", "display_options": {'show': {'resource': ['']}}},
                {"name": "Info", "value": "info", "description": "Returns generic information about the Redis instance", "display_options": {'show': {'resource': ['']}}},
                {"name": "Keys", "value": "keys", "description": "Returns all the keys matching a pattern", "display_options": {'show': {'resource': ['']}}},
                {"name": "Pop", "value": "pop", "description": "Pop data from a redis list", "display_options": {'show': {'resource': ['']}}},
                {"name": "Publish", "value": "publish", "description": "Publish message to redis channel", "display_options": {'show': {'resource': ['']}}},
                {"name": "Push", "value": "push", "description": "Push data to a redis list", "display_options": {'show': {'resource': ['']}}},
                {"name": "Set", "value": "set", "description": "Set the value of a key in redis", "display_options": {'show': {'resource': ['']}}}
            ], "default": "delete", "description": "Operation to perform"},
            {"name": "key", "type": NodeParameterType.STRING, "display_name": "Key", "default": "", "required": True, "description": "Name of the key to delete from Redis", "display_options": {'show': {'operation': ['delete']}}},
            {"name": "propertyName", "type": NodeParameterType.STRING, "display_name": "Name", "default": "propertyName", "required": True, "description": "Name of the property to write received data to. Supports dot-notation. Example: ", "display_options": {'show': {'operation': ['get']}}},
            {"name": "keyType", "type": NodeParameterType.OPTIONS, "display_name": "Key Type", "options": [
                {"name": "Automatic", "value": "automatic"},
                {"name": "Hash", "value": "hash"},
                {"name": "List", "value": "list"},
                {"name": "Sets", "value": "sets"},
                {"name": "String", "value": "string"}
            ], "default": "automatic", "description": "Requests the type before requesting the data (slower)", "display_options": {'show': {'operation': ['get']}}},
            {"name": "options", "type": NodeParameterType.COLLECTION, "display_name": "Options", "default": "", "description": "<p>By default, dot-notation is used in property names. This means that ", "display_options": {'show': {'operation': ['get']}}},
            {"name": "expire", "type": NodeParameterType.BOOLEAN, "display_name": "Expire", "default": False, "description": "Whether to set a timeout on key", "display_options": {'show': {'operation': ['incr']}}},
            {"name": "ttl", "type": NodeParameterType.NUMBER, "display_name": "TTL", "default": 60, "description": "Number of seconds before key expiration", "display_options": {'show': {'operation': ['incr']}}},
            {"name": "keyPattern", "type": NodeParameterType.STRING, "display_name": "Key Pattern", "default": "", "required": True, "description": "The key pattern for the keys to return", "display_options": {'show': {'operation': ['keys']}}},
            {"name": "getValues", "type": NodeParameterType.BOOLEAN, "display_name": "Get Values", "default": True, "description": "Whether to get the value of matching keys", "display_options": {'show': {'operation': ['keys']}}},
            {"name": "value", "type": NodeParameterType.STRING, "display_name": "Value", "default": "", "description": "The value to write in Redis", "display_options": {'show': {'operation': ['set']}}},
            {"name": "valueIsJSON", "type": NodeParameterType.BOOLEAN, "display_name": "Value Is JSON", "default": True, "description": "Whether the value is JSON or key value pairs"},
            {"name": "channel", "type": NodeParameterType.STRING, "display_name": "Channel", "default": "", "required": True, "description": "Channel name", "display_options": {'show': {'operation': ['publish']}}},
            {"name": "messageData", "type": NodeParameterType.STRING, "display_name": "Data", "default": "", "required": True, "description": "Data to publish", "display_options": {'show': {'operation': ['publish']}}},
            {"name": "list", "type": NodeParameterType.STRING, "display_name": "List", "default": "", "required": True, "description": "Name of the list in Redis", "display_options": {'show': {'operation': ['push', 'pop']}}},
            {"name": "tail", "type": NodeParameterType.BOOLEAN, "display_name": "Tail", "default": False, "description": "Whether to push or pop data from the end of the list", "display_options": {'show': {'operation': ['push', 'pop']}}}
        ],
        "credentials": [
            {"name": "redis", "required": True}
        ]
    }
    
    icon = "redis.svg"

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the node operations.
        
        SYNC-CELERY SAFE: All HTTP calls use timeout parameter.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list where outer list is output branches,
            inner list is items in that branch.
        """
        # Get input data from previous node
        input_data = self.get_input_data()
        
        # FIX #40: Handle empty input - create default item so nodes work from Start
        if not input_data:
            input_data = [NodeExecutionData(json_data={})]
        
        return_items: List[NodeExecutionData] = []

        for i, item in enumerate(input_data):
            try:
                operation = self.get_node_parameter("operation", i)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {})
                
                if operation == "delete":
                    result = self._delete(i, item_data)
                elif operation == "get":
                    result = self._get(i, item_data)
                elif operation == "incr":
                    result = self._incr(i, item_data)
                elif operation == "info":
                    result = self._info(i, item_data)
                elif operation == "keys":
                    result = self._keys(i, item_data)
                elif operation == "pop":
                    result = self._pop(i, item_data)
                elif operation == "publish":
                    result = self._publish(i, item_data)
                elif operation == "push":
                    result = self._push(i, item_data)
                elif operation == "set":
                    result = self._set(i, item_data)
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                    
            except Exception as e:
                logger.error(f"Error in operation {operation}: {e}")
                # Platform doesn't support continue_on_fail - always raise
                raise
        
        return [return_items]

    def _get_redis_client(self) -> "redis.Redis":
        """
        Create and return a Redis client using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        
        Returns:
            redis.Redis: Configured Redis client instance
        """
        credentials = self.get_credentials("redisApi")
        
        if not credentials:
            raise Exception("Redis credentials not configured")
        
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 6379))
        database = int(credentials.get("database", 0))
        user = credentials.get("user", "") or None
        password = credentials.get("password", "") or None
        ssl = credentials.get("ssl", False)
        connection_timeout = int(credentials.get("connectionTimeout", 10))
        socket_timeout = int(credentials.get("socketTimeout", 30))
        
        client = redis.Redis(
            host=host,
            port=port,
            db=database,
            username=user if user else None,
            password=password if password else None,
            ssl=ssl,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connection_timeout,
            decode_responses=True,
        )
        
        return client
    
    def _execute_redis_operation(
        self,
        operation: str,
        **kwargs,
    ) -> Any:
        """
        Execute a Redis operation with proper connection handling.
        
        SYNC-CELERY SAFE: All operations are synchronous.
        """
        client = self._get_redis_client()
        
        try:
            # Get the operation method
            op_method = getattr(client, operation, None)
            if not op_method:
                raise ValueError(f"Unknown Redis operation: {operation}")
            
            return op_method(**kwargs)
        finally:
            # Redis client doesn't need explicit close for single operations
            pass


    def _delete(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        delete operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Delete operation
        key = self.get_node_parameter("key", item_index, "")
        if not key:
            raise ValueError("Key is required for delete operation")
        
        client = self._get_redis_client()
        result = client.delete(key)
        
        return {
            "json": {"key": key, "deleted": result > 0, "count": result},
            "pairedItem": {"item": item_index},
        }


    def _get(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        get operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Get operation
        key = self.get_node_parameter("key", item_index, "")
        key_type = self.get_node_parameter("keyType", item_index, "automatic")
        property_name = self.get_node_parameter("propertyName", item_index, "propertyName")
        
        if not key:
            raise ValueError("Key is required for get operation")
        
        client = self._get_redis_client()
        
        # Detect key type if automatic
        if key_type == "automatic":
            key_type = client.type(key)
        
        # Get value based on type
        if key_type == "string":
            value = client.get(key)
        elif key_type == "hash":
            value = client.hgetall(key)
        elif key_type == "list":
            value = client.lrange(key, 0, -1)
        elif key_type == "set":
            value = list(client.smembers(key))
        elif key_type == "zset":
            value = client.zrange(key, 0, -1, withscores=True)
        else:
            value = client.get(key)
        
        return {
            "json": {property_name: value},
            "pairedItem": {"item": item_index},
        }


    def _incr(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        incr operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Increment operation
        key = self.get_node_parameter("key", item_index, "")
        value = self.get_node_parameter("value", item_index, 1)
        
        if not key:
            raise ValueError("Key is required for incr operation")
        
        client = self._get_redis_client()
        
        if value == 1:
            result = client.incr(key)
        else:
            result = client.incrby(key, int(value))
        
        return {
            "json": {"key": key, "value": result},
            "pairedItem": {"item": item_index},
        }


    def _info(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        info operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Info operation
        client = self._get_redis_client()
        info = client.info()
        
        return {
            "json": info,
            "pairedItem": {"item": item_index},
        }


    def _keys(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        keys operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Keys operation
        pattern = self.get_node_parameter("keyPattern", item_index, "*")
        
        client = self._get_redis_client()
        keys = client.keys(pattern)
        
        return {
            "json": {"keys": keys, "count": len(keys)},
            "pairedItem": {"item": item_index},
        }


    def _pop(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        pop operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Pop operation
        list_name = self.get_node_parameter("list", item_index, "")
        tail = self.get_node_parameter("tail", item_index, False)
        property_name = self.get_node_parameter("propertyName", item_index, "propertyName")
        
        if not list_name:
            raise ValueError("List name is required for pop operation")
        
        client = self._get_redis_client()
        
        if tail:
            value = client.rpop(list_name)
        else:
            value = client.lpop(list_name)
        
        return {
            "json": {property_name: value},
            "pairedItem": {"item": item_index},
        }


    def _publish(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        publish operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Publish operation
        channel = self.get_node_parameter("channel", item_index, "")
        message = self.get_node_parameter("messageData", item_index, "")
        
        if not channel:
            raise ValueError("Channel is required for publish operation")
        
        client = self._get_redis_client()
        result = client.publish(channel, message)
        
        return {
            "json": {"channel": channel, "subscribers": result},
            "pairedItem": {"item": item_index},
        }


    def _push(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        push operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Push operation
        list_name = self.get_node_parameter("list", item_index, "")
        values = self.get_node_parameter("messageData", item_index, "")
        tail = self.get_node_parameter("tail", item_index, False)
        
        if not list_name:
            raise ValueError("List name is required for push operation")
        
        client = self._get_redis_client()
        
        if tail:
            result = client.rpush(list_name, values)
        else:
            result = client.lpush(list_name, values)
        
        return {
            "json": {"list": list_name, "length": result},
            "pairedItem": {"item": item_index},
        }


    def _set(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        set operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
        """

        # Set operation
        key = self.get_node_parameter("key", item_index, "")
        value = self.get_node_parameter("value", item_index, "")
        key_type = self.get_node_parameter("keyType", item_index, "string")
        expire = self.get_node_parameter("expire", item_index, False)
        ttl = self.get_node_parameter("ttl", item_index, None)
        
        if not key:
            raise ValueError("Key is required for set operation")
        
        client = self._get_redis_client()
        
        if key_type == "string":
            if expire and ttl:
                client.setex(key, int(ttl), value)
            else:
                client.set(key, value)
        elif key_type == "hash":
            if isinstance(value, dict):
                client.hset(key, mapping=value)
            else:
                # Try to parse as JSON
                import json
                try:
                    value = json.loads(value)
                    client.hset(key, mapping=value)
                except json.JSONDecodeError:
                    client.set(key, value)
        elif key_type == "list":
            if isinstance(value, list):
                client.rpush(key, *value)
            else:
                client.rpush(key, value)
        elif key_type == "set":
            if isinstance(value, (list, set)):
                client.sadd(key, *value)
            else:
                client.sadd(key, value)
        else:
            client.set(key, value)
        
        return {
            "json": {"key": key, "success": True},
            "pairedItem": {"item": item_index},
        }


