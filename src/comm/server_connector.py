"""
ServerConnector - Async HTTP client for antenna_server communication

Responsible for:
- HTTP connection management via httpx
- Connection pooling
- SSL/TLS support
- Timeout and retry logic
"""

import asyncio
from typing import Optional, Dict, Any

import httpx
from utils.logger import get_logger


logger = get_logger(__name__)


class ServerConnector:
    """Async HTTP client for communicating with antenna_server"""
    
    def __init__(self, base_url: str, timeout_sec: float = 60.0,
                 retry_count: int = 3, retry_backoff: float = 2.0):
        """Initialize server connector
        
        Args:
            base_url: Base URL of antenna_server (e.g., http://192.168.1.100:8000)
            timeout_sec: Request timeout in seconds
            retry_count: Number of retry attempts on failure
            retry_backoff: Backoff multiplier for retries
        """
        self.base_url = base_url.rstrip('/')
        self.timeout_sec = timeout_sec
        self.retry_count = retry_count
        self.retry_backoff = retry_backoff
        self.client = None
    
    async def __aenter__(self):
        """Context manager entry - create client"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_sec),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        """Context manager exit - close client"""
        if self.client:
            await self.client.aclose()
    
    async def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request with retry logic
        
        Args:
            endpoint: API endpoint (e.g., /api/v1/health)
            params: Query parameters
            
        Returns:
            Response JSON as dict
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        return await self._retry_request('GET', url, params=params)
    
    async def post(self, endpoint: str, data: Optional[Dict] = None,
                   json: Optional[Dict] = None) -> Dict[str, Any]:
        """Make POST request with retry logic
        
        Args:
            endpoint: API endpoint
            data: Form data
            json: JSON body
            
        Returns:
            Response JSON as dict
            
        Raises:
            httpx.HTTPError: If all retries fail
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use async context manager.")
        
        url = f"{self.base_url}{endpoint}"
        return await self._retry_request('POST', url, data=data, json=json)
    
    async def _retry_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Execute request with exponential backoff retry
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL
            **kwargs: Additional httpx request parameters
            
        Returns:
            Response JSON as dict
        """
        last_error = None
        
        for attempt in range(self.retry_count):
            try:
                response = await self.client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                last_error = e
                status_code = e.response.status_code
                response_text = e.response.text
                try:
                    response_json = e.response.json()
                except Exception:
                    response_json = None

                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.retry_count}): "
                    f"HTTPStatusError - {status_code} - {response_json or response_text or str(e)}"
                )

                if 400 <= status_code < 500:
                    raise

                if attempt < self.retry_count - 1:
                    wait_time = self.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
            except Exception as e:
                last_error = e
                
                error_type = type(e).__name__
                error_msg = str(e) if str(e) else "Unknown error"
                logger.warning(
                    f"Request failed (attempt {attempt + 1}/{self.retry_count}): "
                    f"{error_type} - {error_msg}"
                )
                
                if attempt < self.retry_count - 1:
                    wait_time = self.retry_backoff ** attempt
                    logger.info(f"Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
        
        logger.error(f"All retry attempts failed: {last_error}")
        raise last_error
    
    async def is_alive(self) -> bool:
        """Check if server is reachable
        
        Returns:
            True if server responds to health check
        """
        try:
            await self.get("/api/v1/health")
            return True
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
