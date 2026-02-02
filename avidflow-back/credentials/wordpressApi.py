"""
WordPress API credential for accessing WordPress REST API with OAuth2 support.
"""

from typing import Dict, Any, List, ClassVar
import logging
import os
from .oAuth2Api import OAuth2ApiCredential

# Setup logger
logger = logging.getLogger(__name__)


class WordpressApiCredential(OAuth2ApiCredential):
    """WordPress API credential implementation using standard OAuth2 flow for WordPress.com"""

    name = "wordpressApi"
    display_name = "WordPress API"
    documentationUrl = "wordpress"

    # WordPress.com scopes
    _scopes = ["global"]

    # Override the parent method with a simpler implementation

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build WordPress-specific properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = [
            "authUrl",
            "accessTokenUrl",
            "authQueryParameters",
            "authentication",
            "grantType",
        ]
        base_data = [
            {"authUrl": "https://public-api.wordpress.com/oauth2/authorize"},
            {"accessTokenUrl": "https://public-api.wordpress.com/oauth2/token"},
            {"authQueryParameters": ""},
            {"authentication": "body"},
            {"grantType": "authorizationCode"},
        ]
        modified_props: List[Dict[str, Any]] = []
        for prop in parent_props:
            prop_copy = prop.copy()

            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"

            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({"type": "hidden", "default": "global"})

            modified_props.append(prop_copy)

        # Add WordPress.com site URL field
        modified_props.append({
            "name": "url",
            "displayName": "WordPress URL",
            "type": "string",
            "required": True,
            "placeholder": "yoursite.wordpress.com",
            "description": "The URL of your WordPress.com site (e.g. yoursite.wordpress.com)"
        })

        # Apply defaults for hidden fields
        [
            current.update({"default": value})
            for current in modified_props
            for d in base_data
            for key, value in d.items()
            if current["name"] == key
        ]

        return modified_props

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()

    def __init__(self, data: Dict[str, Any]):
        super().__init__(data)

    def get_base_url(self) -> str:
        """Get WordPress.com site URL from credential data"""
        url = self.data.get("url", "").strip().rstrip("/")
        print(f"WordPress base URL: {url}")
        return url
    
    def get_api_url(self) -> str:
        """Get WordPress.com API URL for testing connection"""
        base_url = self.get_base_url()
        if not base_url:
            print("No WordPress base URL found")
            return ""
        
        # Use WordPress.com REST API v2 format
        if "wordpress.com" in base_url:
            # Direct WordPress.com site
            site_slug = base_url.replace("https://", "").replace("http://", "").split(".")[0]
            api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{site_slug}"
        else:
            # Self-hosted WordPress with Jetpack
            api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{base_url}"
        
        print(f"WordPress API URL: {api_url}")
        return api_url

    async def test(self) -> Dict[str, Any]:
        """Test WordPress.com OAuth2 credential by calling WordPress.com API"""
        # First check OAuth2 token status using parent test
        print(f"Testing WordPress.com OAuth2 credential")
        oauth_test = await super().test()

        if not oauth_test["success"]:
            print(f"OAuth2 token test failed: {oauth_test['message']}")
            return oauth_test

        # Check if site URL is provided
        base_url = self.get_base_url()
        if not base_url:
            print("Missing WordPress.com site URL")
            return {
                "success": False,
                "message": "Missing WordPress.com site URL"
            }

        # If OAuth2 is valid, test actual WordPress.com API access
        try:
            oauth_data = self.data.get("oauthTokenData")
            if not oauth_data or not oauth_data.get("access_token"):
                print("No access token available for WordPress.com API")
                return {
                    "success": False,
                    "message": "No access token available for WordPress.com API",
                }

            import aiohttp
            
            # Test WordPress.com API access
            test_url = self.get_api_url()
            print(f"Testing WordPress.com API with URL: {test_url}")
            
            # Create custom connector with SSL workarounds
            try:
                import ssl
                ssl_context = ssl.create_default_context()
                # Uncomment if needed for SSL issues
                # ssl_context.check_hostname = False
                # ssl_context.verify_mode = ssl.CERT_NONE
                print("Created custom SSL context for WordPress API test")
                
                connector = aiohttp.TCPConnector(
                    limit=1, 
                    ssl=ssl_context,
                    family=0
                )
                
                timeout = aiohttp.ClientTimeout(total=30)
                
                async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                    headers = {"Authorization": f"Bearer {oauth_data['access_token']}"}
                    print(f"Sending WordPress API test request with token: {oauth_data['access_token'][:10]}...")

                    # Check for proxy settings
                    proxy_settings = {}
                    if 'https_proxy' in os.environ:
                        print(f"Using proxy for WordPress API test: {os.environ.get('https_proxy')}")
                        proxy_settings['proxy'] = os.environ.get('https_proxy')

                    async with session.get(test_url, headers=headers, **proxy_settings) as response:
                        print(f"WordPress.com API test response status: {response.status}")
                        if response.status == 200:
                            site_data = await response.json()
                            site_name = site_data.get("name", "Unknown")
                            print(f"WordPress.com API test successful for site: {site_name}")
                            return {
                                "success": True,
                                "message": f"WordPress.com API connection successful. Connected site: {site_name}",
                            }
                        else:
                            error_data = await response.text()
                            print(f"WordPress.com API test failed with status {response.status}: {error_data}")
                            return {
                                "success": False,
                                "message": f"WordPress.com API test failed with status {response.status}: {error_data}",
                            }
            except Exception as inner_e:
                print(f"Error during WordPress API aiohttp test: {str(inner_e)}")
                # Fall back to requests library if available
               
        except Exception as e:
            print(f"WordPress.com API test error: {str(e)}")
            return {"success": False, "message": f"WordPress.com API test error: {str(e)}"}

