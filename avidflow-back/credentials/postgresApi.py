"""
PostgreSQL credential for database connections
"""
from typing import Dict, Any
import psycopg
from .base import BaseCredential


class PostgresApiCredential(BaseCredential):
    """PostgreSQL database credentials"""
    
    name = "postgresApi"
    display_name = "Postgres"
    
    properties = [
        {
            "name": "host",
            "type": "string",
            "displayName": "Host",
            "default": "localhost",
            "required": True,
            "description": "PostgreSQL server hostname or IP address"
        },
        {
            "name": "port",
            "type": "number",
            "displayName": "Port",
            "default": 5432,
            "required": True,
            "description": "PostgreSQL server port (default: 5432)"
        },
        {
            "name": "database",
            "type": "string",
            "displayName": "Database",
            "default": "",
            "required": True,
            "description": "Database name to connect to"
        },
        {
            "name": "user",
            "type": "string",
            "displayName": "User",
            "default": "",
            "required": True,
            "description": "PostgreSQL username"
        },
        {
            "name": "password",
            "type": "string",
            "displayName": "Password",
            "default": "",
            "required": True,
            "type_options": {"password": True},
            "description": "PostgreSQL password"
        },
        {
            "name": "ssl",
            "type": "boolean",
            "displayName": "SSL",
            "default": False,
            "description": "Use SSL for connection"
        },
        {
            "name": "connectionTimeout",
            "type": "number",
            "displayName": "Connection Timeout",
            "default": 30,
            "description": "Connection timeout in seconds"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the PostgreSQL connection
        
        Returns:
            Dictionary with test results
        """
        try:
            # Build connection string
            conn_string = self._build_connection_string()
            
            # Test connection
            with psycopg.connect(conn_string) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()
                    
            return {
                "success": True,
                "message": f"Connection successful! PostgreSQL version: {version[0] if version else 'Unknown'}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }
    
    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from credentials"""
        host = self.data.get("host", "localhost")
        port = self.data.get("port", 5432)
        database = self.data.get("database", "")
        user = self.data.get("user", "")
        password = self.data.get("password", "")
        ssl = self.data.get("ssl", False)
        timeout = self.data.get("connectionTimeout", 30)
        
        # Build connection string
        conn_parts = [
            f"host={host}",
            f"port={port}",
            f"dbname={database}",
            f"user={user}",
            f"password={password}",
            f"connect_timeout={timeout}"
        ]
        
        if ssl:
            conn_parts.append("sslmode=require")
        else:
            conn_parts.append("sslmode=prefer")
        
        return " ".join(conn_parts)