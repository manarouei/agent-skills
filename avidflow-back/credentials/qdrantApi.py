"""
Qdrant Vector Database API credential for vector storage and similarity search.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class QdrantApiCredential(BaseCredential):
    """Qdrant API credential implementation"""
    
    name = "qdrantApi"
    display_name = "Qdrant API"
    properties = [
        {
            "name": "qdrantUrl",
            "displayName": "Qdrant URL",
            "type": "string",
            "required": True,
            "default": "http://localhost:6333",
            "description": "The URL of your Qdrant instance (e.g., http://localhost:6333 or https://your-cluster.qdrant.io)"
        },
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "required": False,
            "description": "API key for authentication (required for Qdrant Cloud, optional for local instances)"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Qdrant API credential by checking API access
        
        Returns:
            Dictionary with test results
        """
        # Validate required fields first
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
            # Get connection info to test credential
            qdrant_url = self.data.get("qdrantUrl", "").rstrip("/")
            api_key = self.data.get("apiKey", "")
            
            # Build headers
            headers = {
                "Content-Type": "application/json"
            }
            
            if api_key:
                headers["api-key"] = api_key
            
            # Test connection by checking if we can access the API
            url = f"{qdrant_url}/collections"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return {
                            "success": True,
                            "message": f"Successfully connected to Qdrant. Found {len(result.get('result', {}).get('collections', []))} collections."
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "Authentication failed. Please check your API key."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Qdrant API error (status {response.status}): {error_text}"
                        }
                        
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "message": f"Cannot connect to Qdrant at {qdrant_url}. Please check the URL and ensure Qdrant is running."
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Qdrant API credential: {str(e)}"
            }
