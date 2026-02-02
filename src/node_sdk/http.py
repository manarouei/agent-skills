"""
HTTP Client - Timeout-bounded HTTP requests for nodes.

All HTTP calls MUST use timeouts (sync-Celery requirement).
This module provides a simple wrapper around requests with
sensible defaults and structured responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

import requests
from requests.exceptions import Timeout, RequestException


logger = logging.getLogger(__name__)

# Default timeout in seconds (REQUIRED for sync-Celery)
DEFAULT_TIMEOUT = 30


class NodeTimeoutError(Exception):
    """Raised when an HTTP request times out."""
    
    def __init__(self, message: str, timeout: float, url: str):
        self.timeout = timeout
        self.url = url
        super().__init__(message)


class HttpApiError(Exception):
    """Error from HTTP request."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        url: Optional[str] = None,
        method: Optional[str] = None,
    ):
        self.status_code = status_code
        self.response_body = response_body
        self.url = url
        self.method = method
        super().__init__(message)


class HttpResponse:
    """
    Wrapper for HTTP response with convenient accessors.
    """
    
    def __init__(self, response: requests.Response):
        self._response = response
    
    @property
    def status_code(self) -> int:
        return self._response.status_code
    
    @property
    def headers(self) -> Dict[str, str]:
        return dict(self._response.headers)
    
    @property
    def text(self) -> str:
        return self._response.text
    
    @property
    def content(self) -> bytes:
        return self._response.content
    
    def json(self) -> Any:
        """Parse response as JSON."""
        return self._response.json()
    
    @property
    def ok(self) -> bool:
        """True if status code is 2xx."""
        return self._response.ok
    
    def raise_for_status(self) -> None:
        """Raise HttpApiError if status code indicates error."""
        if not self.ok:
            raise HttpApiError(
                message=f"HTTP {self.status_code}: {self._response.reason}",
                status_code=self.status_code,
                response_body=self.text[:1000] if self.text else None,
                url=str(self._response.url),
                method=self._response.request.method if self._response.request else None,
            )


class HttpClient:
    """
    HTTP client with timeout enforcement and credential injection.
    
    SYNC-CELERY SAFE: All requests have explicit timeouts.
    
    Usage:
        client = HttpClient(base_url="https://api.example.com")
        response = client.get("/users", params={"limit": 10})
        data = response.json()
    """
    
    def __init__(
        self,
        base_url: str = "",
        default_headers: Optional[Dict[str, str]] = None,
        timeout: float = DEFAULT_TIMEOUT,
        auth: Optional[tuple] = None,
        bearer_token: Optional[str] = None,
        api_key: Optional[str] = None,
        api_key_header: str = "X-API-Key",
    ):
        """
        Initialize HTTP client.
        
        Args:
            base_url: Base URL for all requests
            default_headers: Headers to include in all requests
            timeout: Default timeout in seconds (REQUIRED)
            auth: Basic auth tuple (username, password)
            bearer_token: Bearer token for Authorization header
            api_key: API key value
            api_key_header: Header name for API key
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.auth = auth
        
        # Build default headers
        self.headers: Dict[str, str] = default_headers or {}
        
        if bearer_token:
            self.headers["Authorization"] = f"Bearer {bearer_token}"
        
        if api_key:
            self.headers[api_key_header] = api_key
    
    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """
        Make HTTP request with timeout enforcement.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            endpoint: URL endpoint (appended to base_url)
            params: Query parameters
            json: JSON body (auto-serialized)
            data: Form data or raw body
            headers: Additional headers (merged with defaults)
            timeout: Override default timeout
            **kwargs: Additional arguments to requests.request
            
        Returns:
            HttpResponse wrapper
            
        Raises:
            NodeTimeoutError: If request times out
            NodeApiError: If request fails
        """
        # Build full URL
        url = f"{self.base_url}{endpoint}" if self.base_url else endpoint
        
        # Merge headers
        request_headers = {**self.headers, **(headers or {})}
        
        # Enforce timeout
        request_timeout = timeout or self.timeout
        
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json,
                data=data,
                headers=request_headers,
                auth=self.auth,
                timeout=request_timeout,  # REQUIRED for sync-Celery
                **kwargs,
            )
            return HttpResponse(response)
            
        except Timeout as e:
            raise NodeTimeoutError(
                message=f"Request timed out after {request_timeout}s",
                timeout=request_timeout,
                url=url,
            ) from e
            
        except RequestException as e:
            raise HttpApiError(
                message=f"Request failed: {e}",
                url=url,
                method=method,
            ) from e
    
    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make GET request."""
        return self.request("GET", endpoint, params=params, **kwargs)
    
    def post(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make POST request."""
        return self.request("POST", endpoint, json=json, data=data, **kwargs)
    
    def put(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make PUT request."""
        return self.request("PUT", endpoint, json=json, data=data, **kwargs)
    
    def patch(
        self,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], str, bytes]] = None,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make PATCH request."""
        return self.request("PATCH", endpoint, json=json, data=data, **kwargs)
    
    def delete(
        self,
        endpoint: str,
        **kwargs: Any,
    ) -> HttpResponse:
        """Make DELETE request."""
        return self.request("DELETE", endpoint, **kwargs)
