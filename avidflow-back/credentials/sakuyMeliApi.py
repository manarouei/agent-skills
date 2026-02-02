from credentials.base import BaseCredential


class SakuyMeliApiCredential(BaseCredential):
    """
    Credential for Iranian National Platform (سکوی ملی) API access
    Provided by Sharif University AI Platform
    """
    
    name = "sakuyMeliApi"
    display_name = "سکوی ملی API"
    icon = "file:iran.svg"
    
    properties =[
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "required": True,
            "description": "Your Qwen API key"
        }
    ]
    
    async def test(self) -> dict:
        """Test the credential by making a simple API call"""
        import aiohttp
        import asyncio
        
        # Validate required fields first
        api_key = self.data.get("apiKey")
        if not api_key:
            return {"success": False, "message": "API key is required"}
        
        try:
            # Test with a simple chat completion request
            url = "https://alphapi.aip.sharif.ir/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "model": "GPT-OSS-120B",
                "messages": [{"role": "user", "content": "سلام"}],
                "max_tokens": 10
            }
            
            # Set timeout
            timeout = aiohttp.ClientTimeout(total=10)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "✓ Connection successful to سکوی ملی API"
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "✗ Authentication failed - Invalid API key"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"✗ API returned status {response.status}: {error_text[:200]}"
                        }
                
        except asyncio.TimeoutError:
            return {
                "success": False,
                "message": "✗ Connection timeout - Server may be blocking external requests to alphapi.aip.sharif.ir"
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"✗ Network error: {type(e).__name__} - {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"✗ Connection failed: {type(e).__name__} - {str(e)}"
            }
