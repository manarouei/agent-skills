"""
Redis credential for cache and memory storage connections.

This credential type supports Redis connections for:
- AI Agent conversation memory (MemoryRedisChat equivalent)
- Session storage and caching
- Pub/Sub messaging

Based on n8n's Redis.credentials.ts implementation.
"""
from typing import Dict, Any
import logging

from .base import BaseCredential

logger = logging.getLogger(__name__)


class RedisApiCredential(BaseCredential):
    """
    Redis connection credentials.
    
    Supports both password-only auth and user/password auth (Redis ACL).
    Compatible with Redis 5.x+ and Redis Cluster configurations.
    """
    
    name = "redisApi"
    display_name = "Redis API"
    
    properties = [
        {
            "name": "host",
            "type": "string",
            "displayName": "Host",
            "default": "localhost",
            "required": True,
            "description": "Redis server hostname or IP address"
        },
        {
            "name": "port",
            "type": "number",
            "displayName": "Port",
            "default": 6379,
            "required": True,
            "description": "Redis server port (default: 6379)"
        },
        {
            "name": "database",
            "type": "number",
            "displayName": "Database Number",
            "default": 0,
            "required": False,
            "description": "Redis database index (0-15, default: 0)"
        },
        {
            "name": "user",
            "type": "string",
            "displayName": "User",
            "default": "",
            "required": False,
            "description": "Redis username (leave blank for password-only auth)"
        },
        {
            "name": "password",
            "type": "string",
            "displayName": "Password",
            "default": "",
            "required": False,
            "type_options": {"password": True},
            "description": "Redis password"
        },
        {
            "name": "ssl",
            "type": "boolean",
            "displayName": "SSL/TLS",
            "default": False,
            "required": False,
            "description": "Use SSL/TLS for secure connection"
        },
        {
            "name": "connectionTimeout",
            "type": "number",
            "displayName": "Connection Timeout",
            "default": 10,
            "required": False,
            "description": "Connection timeout in seconds (default: 10)"
        },
        {
            "name": "socketTimeout",
            "type": "number",
            "displayName": "Socket Timeout",
            "default": 30,
            "required": False,
            "description": "Socket read/write timeout in seconds (default: 30)"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Redis connection.
        
        Attempts to connect to Redis and execute a PING command.
        
        Returns:
            Dictionary with test results:
            - success: bool indicating if connection was successful
            - message: Human-readable status message
        """
        try:
            # Import redis here to avoid import errors if not installed
            import redis
            
            # Build connection parameters
            host = self.data.get("host", "localhost")
            port = int(self.data.get("port", 6379))
            database = int(self.data.get("database", 0))
            user = self.data.get("user", "") or None
            password = self.data.get("password", "") or None
            ssl = self.data.get("ssl", False)
            connection_timeout = int(self.data.get("connectionTimeout", 10))
            socket_timeout = int(self.data.get("socketTimeout", 30))
            
            # Create Redis client with proper auth configuration
            # NOTE: username requires Redis 6.0+ with ACL support
            client = redis.Redis(
                host=host,
                port=port,
                db=database,
                username=user if user else None,
                password=password if password else None,
                ssl=ssl,
                socket_timeout=socket_timeout,
                socket_connect_timeout=connection_timeout,
                decode_responses=True
            )
            
            # Test connection with PING
            response = client.ping()
            
            if response:
                # Get Redis server info for additional context
                info = client.info("server")
                redis_version = info.get("redis_version", "Unknown")
                
                client.close()
                
                return {
                    "success": True,
                    "message": f"Connection successful! Redis version: {redis_version}"
                }
            else:
                client.close()
                return {
                    "success": False,
                    "message": "PING command failed - unexpected response"
                }
                
        except ImportError:
            return {
                "success": False,
                "message": "Redis package not installed. Run: pip install redis"
            }
        except redis.AuthenticationError as e:
            logger.error(f"Redis authentication failed: {e}")
            return {
                "success": False,
                "message": f"Authentication failed: {str(e)}"
            }
        except redis.ConnectionError as e:
            logger.error(f"Redis connection failed: {e}")
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }
        except redis.TimeoutError as e:
            logger.error(f"Redis connection timeout: {e}")
            return {
                "success": False,
                "message": f"Connection timeout: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Redis test failed: {e}")
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }
    
    def get_connection_url(self) -> str:
        """
        Build Redis connection URL from credentials.
        
        Format: redis://[user:password@]host:port/database
        With SSL: rediss://[user:password@]host:port/database
        
        Returns:
            Redis connection URL string
        """
        host = self.data.get("host", "localhost")
        port = int(self.data.get("port", 6379))
        database = int(self.data.get("database", 0))
        user = self.data.get("user", "")
        password = self.data.get("password", "")
        ssl = self.data.get("ssl", False)
        
        # Determine protocol based on SSL setting
        protocol = "rediss" if ssl else "redis"
        
        # Build auth string
        if user and password:
            auth = f"{user}:{password}@"
        elif password:
            auth = f":{password}@"
        else:
            auth = ""
        
        return f"{protocol}://{auth}{host}:{port}/{database}"
    
    def get_client_kwargs(self) -> Dict[str, Any]:
        """
        Get keyword arguments for creating a Redis client.
        
        Returns:
            Dictionary of kwargs for redis.Redis() or redis.StrictRedis()
        """
        host = self.data.get("host", "localhost")
        port = int(self.data.get("port", 6379))
        database = int(self.data.get("database", 0))
        user = self.data.get("user", "")
        password = self.data.get("password", "")
        ssl = self.data.get("ssl", False)
        connection_timeout = int(self.data.get("connectionTimeout", 10))
        socket_timeout = int(self.data.get("socketTimeout", 30))
        
        kwargs = {
            "host": host,
            "port": port,
            "db": database,
            "ssl": ssl,
            "socket_timeout": socket_timeout,
            "socket_connect_timeout": connection_timeout,
            "decode_responses": True,
        }
        
        # Only add auth if provided
        if user:
            kwargs["username"] = user
        if password:
            kwargs["password"] = password
        
        return kwargs
