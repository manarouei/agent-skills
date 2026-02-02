#!/usr/bin/env python3
"""
TCP Client Backend Converter

Converts TCP/binary protocol nodes (Redis, Postgres, MySQL, MongoDB)
to Python BaseNode implementations.

These nodes use direct TCP connections via client libraries,
not HTTP requests.
"""

from __future__ import annotations
from typing import Any, Dict, List


# Library mappings for TCP nodes
TCP_LIBRARIES: Dict[str, Dict[str, Any]] = {
    "redis": {
        "library": "redis",
        "import": "import redis",
        "client_class": "redis.Redis",
        "connection_params": ["host", "port", "database", "password", "user", "ssl"],
    },
    "postgres": {
        "library": "psycopg",
        "import": "import psycopg\nfrom psycopg.rows import dict_row",
        "client_class": "psycopg.connect",
        "connection_params": ["host", "port", "database", "user", "password", "ssl"],
    },
    "mysql": {
        "library": "mysql-connector-python",
        "import": "import mysql.connector",
        "client_class": "mysql.connector.connect",
        "connection_params": ["host", "port", "database", "user", "password"],
    },
    "mongodb": {
        "library": "pymongo",
        "import": "from pymongo import MongoClient",
        "client_class": "MongoClient",
        "connection_params": ["host", "port", "database", "user", "password"],
    },
}


def convert_tcp_client_node(
    node_name: str,
    node_schema: Dict[str, Any],
    ts_code: str,
    properties: List[Dict[str, Any]],
    execution_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert a TCP/binary protocol node to Python.
    
    Args:
        node_name: Node type name
        node_schema: Complete inferred schema
        ts_code: Raw TypeScript source code
        properties: Node parameters
        execution_contract: The node's execution contract
    
    Returns:
        Dict with python_code, imports, helpers, conversion_notes
    """
    node_name_lower = node_name.lower().replace("-", "").replace("_", "")
    connection = execution_contract.get("connection", {})
    credentials = execution_contract.get("credentials", {})
    
    # Get library configuration
    lib_config = TCP_LIBRARIES.get(node_name_lower, {})
    library = lib_config.get("library", connection.get("library", ""))
    import_stmt = lib_config.get("import", f"import {library}")
    client_class = lib_config.get("client_class", "")
    conn_params = lib_config.get("connection_params", [])
    
    # Credential type
    cred_type = credentials.get("type", f"{node_name_lower}Api")
    
    # Generate client factory method based on node type
    if node_name_lower == "redis":
        client_factory = _generate_redis_client_factory(cred_type)
    elif node_name_lower in ("postgres", "postgresql"):
        client_factory = _generate_postgres_client_factory(cred_type)
    elif node_name_lower == "mysql":
        client_factory = _generate_mysql_client_factory(cred_type)
    elif node_name_lower == "mongodb":
        client_factory = _generate_mongodb_client_factory(cred_type)
    else:
        # Generic TCP client factory
        client_factory = _generate_generic_client_factory(
            node_name_lower, cred_type, client_class, conn_params
        )
    
    # Generate imports
    # Generate operation handlers for Redis
    operation_handlers = []
    if node_name_lower == "redis":
        operations = node_schema.get("properties", {}).get("parameters", [])
        for param in operations:
            if param.get("name") == "operation" and "options" in param:
                for opt in param["options"]:
                    op_value = opt.get("value", "")
                    op_handler = _generate_redis_operation_handler(op_value)
                    if op_handler:
                        operation_handlers.append(("", op_value, op_handler))
    
    imports = [
        import_stmt,
        "import logging",
        "from typing import Any, Dict, List, Optional",
    ]
    
    conversion_notes = [
        f"Using tcp_client backend for {node_name}",
        f"Library: {library}",
        f"Credential type: {cred_type}",
        f"Connection params: {conn_params}",
    ]
    
    return {
        "python_code": "",
        "imports": imports,
        "helpers": client_factory,
        "conversion_notes": conversion_notes,
        "library": library,
        "credential_type": cred_type,
        "operation_handlers": operation_handlers,
    }


def _generate_redis_client_factory(cred_type: str) -> str:
    """Generate Redis client factory method."""
    return f'''
    def _get_redis_client(self) -> "redis.Redis":
        """
        Create and return a Redis client using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        
        Returns:
            redis.Redis: Configured Redis client instance
        """
        credentials = self.get_credentials("{cred_type}")
        
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
                raise ValueError(f"Unknown Redis operation: {{operation}}")
            
            return op_method(**kwargs)
        finally:
            # Redis client doesn't need explicit close for single operations
            pass
'''


def _generate_postgres_client_factory(cred_type: str) -> str:
    """Generate Postgres client factory method."""
    return f'''
    def _get_postgres_connection(self):
        """
        Create and return a Postgres connection using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        
        Returns:
            psycopg.Connection: Configured Postgres connection
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("Postgres credentials not configured")
        
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 5432))
        database = credentials.get("database", "postgres")
        user = credentials.get("user", "postgres")
        password = credentials.get("password", "")
        ssl = credentials.get("ssl", False)
        
        # Build connection string
        conn_params = {{
            "host": host,
            "port": port,
            "dbname": database,
            "user": user,
            "password": password,
            "connect_timeout": 30,
        }}
        
        if ssl:
            conn_params["sslmode"] = "require"
        
        return psycopg.connect(**conn_params, row_factory=dict_row)
    
    def _execute_query(
        self,
        query: str,
        params: tuple | None = None,
        fetch: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query with proper connection handling.
        
        SYNC-CELERY SAFE: All operations are synchronous.
        """
        with self._get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if fetch:
                    return cur.fetchall()
                else:
                    conn.commit()
                    return [{{"affected_rows": cur.rowcount}}]
'''


def _generate_mysql_client_factory(cred_type: str) -> str:
    """Generate MySQL client factory method."""
    return f'''
    def _get_mysql_connection(self):
        """
        Create and return a MySQL connection using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("MySQL credentials not configured")
        
        return mysql.connector.connect(
            host=credentials.get("host", "localhost"),
            port=int(credentials.get("port", 3306)),
            database=credentials.get("database", ""),
            user=credentials.get("user", "root"),
            password=credentials.get("password", ""),
            connection_timeout=30,
        )
    
    def _execute_query(
        self,
        query: str,
        params: tuple | None = None,
        fetch: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a SQL query with proper connection handling.
        
        SYNC-CELERY SAFE: All operations are synchronous.
        """
        conn = self._get_mysql_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params)
            
            if fetch:
                return cursor.fetchall()
            else:
                conn.commit()
                return [{{"affected_rows": cursor.rowcount}}]
        finally:
            conn.close()
'''


def _generate_mongodb_client_factory(cred_type: str) -> str:
    """Generate MongoDB client factory method."""
    return f'''
    def _get_mongodb_client(self):
        """
        Create and return a MongoDB client using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("MongoDB credentials not configured")
        
        host = credentials.get("host", "localhost")
        port = int(credentials.get("port", 27017))
        user = credentials.get("user", "")
        password = credentials.get("password", "")
        database = credentials.get("database", "test")
        
        if user and password:
            uri = f"mongodb://{{user}}:{{password}}@{{host}}:{{port}}/{{database}}"
        else:
            uri = f"mongodb://{{host}}:{{port}}/{{database}}"
        
        return MongoClient(uri, serverSelectionTimeoutMS=30000)
    
    def _get_collection(self, collection_name: str):
        """Get a MongoDB collection."""
        credentials = self.get_credentials("{cred_type}")
        database = credentials.get("database", "test")
        
        client = self._get_mongodb_client()
        return client[database][collection_name]
'''


def _generate_generic_client_factory(
    node_name: str,
    cred_type: str,
    client_class: str,
    conn_params: List[str],
) -> str:
    """Generate a generic TCP client factory method."""
    param_extraction = "\n        ".join([
        f'{param} = credentials.get("{param}", "")'
        for param in conn_params
    ])
    
    return f'''
    def _get_{node_name}_client(self):
        """
        Create and return a {node_name} client using configured credentials.
        
        SYNC-CELERY SAFE: Synchronous connection with timeout.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("{node_name} credentials not configured")
        
        {param_extraction}
        
        # Create client - customize based on actual library
        # This is a generic template that may need adjustment
        return {client_class}(
            host=host,
            port=int(port) if port else None,
        )
'''


def _generate_redis_operation_handler(operation: str) -> str:
    """Generate handler code for a specific Redis operation."""
    handlers = {
        "delete": '''
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
''',
        "get": '''
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
''',
        "set": '''
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
''',
        "incr": '''
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
''',
        "keys": '''
        # Keys operation
        pattern = self.get_node_parameter("keyPattern", item_index, "*")
        
        client = self._get_redis_client()
        keys = client.keys(pattern)
        
        return {
            "json": {"keys": keys, "count": len(keys)},
            "pairedItem": {"item": item_index},
        }
''',
        "info": '''
        # Info operation
        client = self._get_redis_client()
        info = client.info()
        
        return {
            "json": info,
            "pairedItem": {"item": item_index},
        }
''',
        "push": '''
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
''',
        "pop": '''
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
''',
        "publish": '''
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
''',
    }
    
    return handlers.get(operation, "")

