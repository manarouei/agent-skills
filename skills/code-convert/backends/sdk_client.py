#!/usr/bin/env python3
"""
SDK Client Backend Converter

Converts SDK-based nodes (OpenAI, Google APIs, Supabase, etc.)
to Python BaseNode implementations.

These nodes use SDK client libraries that abstract away HTTP details.
"""

from __future__ import annotations
from typing import Any, Dict, List


# SDK library mappings
SDK_LIBRARIES: Dict[str, Dict[str, Any]] = {
    "openai": {
        "library": "openai",
        "import": "from openai import OpenAI",
        "client_class": "OpenAI",
        "init_params": {"api_key": "apiKey"},
    },
    "deepseek": {
        "library": "openai",
        "import": "from openai import OpenAI",
        "client_class": "OpenAI",
        "init_params": {"api_key": "apiKey", "base_url": "https://api.deepseek.com"},
    },
    "gemini": {
        "library": "google-generativeai",
        "import": "import google.generativeai as genai",
        "client_class": "genai",
        "init_params": {"api_key": "apiKey"},
    },
    "supabase": {
        "library": "supabase",
        "import": "from supabase import create_client, Client",
        "client_class": "create_client",
        "init_params": {"url": "url", "key": "apiKey"},
    },
    "qdrantvectorstore": {
        "library": "qdrant-client",
        "import": "from qdrant_client import QdrantClient",
        "client_class": "QdrantClient",
        "init_params": {"url": "url", "api_key": "apiKey"},
    },
    "telegram": {
        "library": "requests",
        "import": "import requests",
        "client_class": None,  # Uses direct HTTP calls
        "base_url": "https://api.telegram.org/bot{token}",
        "init_params": {"token": "accessToken"},
    },
    "bale": {
        "library": "requests",
        "import": "import requests",
        "client_class": None,
        "base_url": "https://tapi.bale.ai/bot{token}",
        "init_params": {"token": "accessToken"},
    },
}


def convert_sdk_client_node(
    node_name: str,
    node_schema: Dict[str, Any],
    ts_code: str,
    properties: List[Dict[str, Any]],
    execution_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert an SDK-based node to Python.
    
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
    sdk_config = execution_contract.get("sdk_config", {})
    
    # Get library configuration
    lib_config = SDK_LIBRARIES.get(node_name_lower, {})
    library = lib_config.get("library", connection.get("library", ""))
    import_stmt = lib_config.get("import", f"import {library}")
    client_class = lib_config.get("client_class", sdk_config.get("client_class", ""))
    init_params = lib_config.get("init_params", sdk_config.get("init_from_credentials", {}))
    
    # Credential type
    cred_type = credentials.get("type", f"{node_name_lower}Api")
    
    # Generate client factory method based on node type
    if node_name_lower == "openai":
        client_factory = _generate_openai_client_factory(cred_type)
    elif node_name_lower == "deepseek":
        client_factory = _generate_deepseek_client_factory(cred_type)
    elif node_name_lower == "gemini":
        client_factory = _generate_gemini_client_factory(cred_type)
    elif node_name_lower == "supabase":
        client_factory = _generate_supabase_client_factory(cred_type)
    elif node_name_lower in ("telegram", "bale"):
        base_url = lib_config.get("base_url", "")
        client_factory = _generate_bot_api_factory(node_name_lower, cred_type, base_url)
    elif node_name_lower == "qdrantvectorstore":
        client_factory = _generate_qdrant_client_factory(cred_type)
    else:
        # Generic SDK client factory
        client_factory = _generate_generic_sdk_factory(
            node_name_lower, cred_type, client_class, init_params
        )
    
    # Generate imports
    imports = [
        import_stmt,
        "import logging",
        "from typing import Any, Dict, List, Optional",
    ]
    
    conversion_notes = [
        f"Using sdk_client backend for {node_name}",
        f"Library: {library}",
        f"Client class: {client_class}",
        f"Credential type: {cred_type}",
    ]
    
    return {
        "python_code": "",  # Operation handlers generated separately
        "imports": imports,
        "helpers": client_factory,
        "conversion_notes": conversion_notes,
        "library": library,
        "credential_type": cred_type,
    }


def _generate_openai_client_factory(cred_type: str) -> str:
    """Generate OpenAI client factory method."""
    return f'''
    def _get_openai_client(self) -> "OpenAI":
        """
        Create and return an OpenAI client using configured credentials.
        
        SYNC-CELERY SAFE: Client creation is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("OpenAI credentials not configured")
        
        api_key = credentials.get("apiKey", credentials.get("api_key", ""))
        organization = credentials.get("organization", None)
        
        return OpenAI(
            api_key=api_key,
            organization=organization,
            timeout=60.0,
        )
    
    def _call_openai(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an OpenAI chat completion call.
        
        SYNC-CELERY SAFE: Uses synchronous OpenAI client.
        """
        client = self._get_openai_client()
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        
        return {{
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "model": response.model,
            "usage": {{
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }},
        }}
'''


def _generate_deepseek_client_factory(cred_type: str) -> str:
    """Generate DeepSeek client factory method (OpenAI-compatible)."""
    return f'''
    def _get_deepseek_client(self) -> "OpenAI":
        """
        Create and return a DeepSeek client using configured credentials.
        
        DeepSeek uses OpenAI-compatible API.
        SYNC-CELERY SAFE: Client creation is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("DeepSeek credentials not configured")
        
        api_key = credentials.get("apiKey", credentials.get("api_key", ""))
        
        return OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=60.0,
        )
    
    def _call_deepseek(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make a DeepSeek chat completion call.
        
        SYNC-CELERY SAFE: Uses synchronous OpenAI-compatible client.
        """
        client = self._get_deepseek_client()
        
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs,
        )
        
        return {{
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "model": response.model,
        }}
'''


def _generate_gemini_client_factory(cred_type: str) -> str:
    """Generate Google Gemini client factory method."""
    return f'''
    def _configure_gemini(self) -> None:
        """
        Configure Gemini with API key.
        
        SYNC-CELERY SAFE: Configuration is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("Gemini credentials not configured")
        
        api_key = credentials.get("apiKey", credentials.get("api_key", ""))
        genai.configure(api_key=api_key)
    
    def _call_gemini(
        self,
        model: str,
        prompt: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make a Gemini generation call.
        
        SYNC-CELERY SAFE: Uses synchronous Gemini client.
        """
        self._configure_gemini()
        
        model_instance = genai.GenerativeModel(model)
        response = model_instance.generate_content(prompt, **kwargs)
        
        return {{
            "content": response.text,
            "model": model,
        }}
'''


def _generate_supabase_client_factory(cred_type: str) -> str:
    """Generate Supabase client factory method."""
    return f'''
    def _get_supabase_client(self) -> "Client":
        """
        Create and return a Supabase client using configured credentials.
        
        SYNC-CELERY SAFE: Client creation is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("Supabase credentials not configured")
        
        url = credentials.get("url", credentials.get("supabaseUrl", ""))
        key = credentials.get("apiKey", credentials.get("supabaseKey", ""))
        
        return create_client(url, key)
'''


def _generate_qdrant_client_factory(cred_type: str) -> str:
    """Generate Qdrant client factory method."""
    return f'''
    def _get_qdrant_client(self) -> "QdrantClient":
        """
        Create and return a Qdrant client using configured credentials.
        
        SYNC-CELERY SAFE: Client creation is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("Qdrant credentials not configured")
        
        url = credentials.get("url", credentials.get("qdrantUrl", ""))
        api_key = credentials.get("apiKey", None)
        
        if api_key:
            return QdrantClient(url=url, api_key=api_key, timeout=30)
        else:
            return QdrantClient(url=url, timeout=30)
'''


def _generate_bot_api_factory(node_name: str, cred_type: str, base_url: str) -> str:
    """Generate bot API (Telegram/Bale) factory method."""
    return f'''
    def _get_bot_base_url(self) -> str:
        """
        Get the bot API base URL with token.
        
        SYNC-CELERY SAFE: Pure computation.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("{node_name} credentials not configured")
        
        token = credentials.get("accessToken", credentials.get("token", ""))
        return "{base_url}".format(token=token)
    
    def _bot_api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make a bot API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        base_url = self._get_bot_base_url()
        url = f"{{base_url}}/{{endpoint}}"
        
        response = requests.request(
            method=method,
            url=url,
            json=body,
            timeout=30,
        )
        response.raise_for_status()
        
        result = response.json()
        if not result.get("ok", False):
            raise Exception(f"Bot API error: {{result.get('description', 'Unknown error')}}")
        
        return result.get("result", {{}})
'''


def _generate_generic_sdk_factory(
    node_name: str,
    cred_type: str,
    client_class: str,
    init_params: Dict[str, str],
) -> str:
    """Generate a generic SDK client factory method."""
    param_mapping = "\n        ".join([
        f'{sdk_param}=credentials.get("{cred_param}", "")'
        for sdk_param, cred_param in init_params.items()
    ])
    
    return f'''
    def _get_{node_name}_client(self):
        """
        Create and return a {node_name} client using configured credentials.
        
        SYNC-CELERY SAFE: Client creation is synchronous.
        """
        credentials = self.get_credentials("{cred_type}")
        
        if not credentials:
            raise Exception("{node_name} credentials not configured")
        
        return {client_class}(
            {param_mapping}
        )
'''
