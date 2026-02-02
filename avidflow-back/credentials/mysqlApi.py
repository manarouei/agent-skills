"""
MySQL credential for database connections
"""
from typing import Dict, Any
import pymysql
from .base import BaseCredential


class MySQLApiCredential(BaseCredential):
    """MySQL database credentials"""

    name = "mysqlApi"
    display_name = "MySQL"

    properties = [
        {
            "name": "host",
            "type": "string",
            "displayName": "Host",
            "default": "localhost",
            "required": True,
            "description": "MySQL server hostname or IP address"
        },
        {
            "name": "port",
            "type": "number",
            "displayName": "Port",
            "default": 3306,
            "required": True,
            "description": "MySQL server port (default: 3306)"
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
            "description": "MySQL username"
        },
        {
            "name": "password",
            "type": "string",
            "displayName": "Password",
            "default": "",
            "required": True,
            "type_options": {"password": True},
            "description": "MySQL password"
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
        Test the MySQL connection

        Returns:
            Dictionary with test results
        """
        try:
            # Build connection parameters
            conn_params = {
                "host": self.data.get("host", "localhost"),
                "port": self.data.get("port", 3306),
                "user": self.data.get("user", ""),
                "password": self.data.get("password", ""),
                "database": self.data.get("database", ""),
                "connect_timeout": self.data.get("connectionTimeout", 30),
                "ssl": self.data.get("ssl", False),
            }

            # Test connection
            with pymysql.connect(**conn_params) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT VERSION();")
                    version = cur.fetchone()

            return {
                "success": True,
                "message": f"Connection successful! MySQL version: {version[0] if version else 'Unknown'}"
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }