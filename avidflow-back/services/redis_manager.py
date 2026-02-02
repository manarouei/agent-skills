import json
from redis import asyncio as aioredis
from typing import Dict, Any, Optional
from config import settings
import logging

logger = logging.getLogger(__name__)

class RedisManager:
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
    
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.aclose()

    async def set_test_webhook_state(self, state: str, data: Dict[str, Any], expire_seconds: int = None) -> bool:
        """Store test webhook state"""
        if not self.redis:
            return False

        try:
            expire_seconds = expire_seconds or settings.TEST_WEBHOOK_STATE_EXPIRE_SECONDS
            key = f"test_webhook_state:{state}"
            value = json.dumps(data)

            await self.redis.setex(key, expire_seconds, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store test webhook state: {e}")
            return False

    async def get_test_webhook_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Get test webhook state"""
        if not self.redis:
            return None

        try:
            key = f"test_webhook_state:{state}"
            value = await self.redis.get(key)

            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get test webhook state: {e}")
            return None

    async def delete_test_webhook_state(self, state: str) -> bool:
        """Delete test webhook state"""
        if not self.redis:
            return False

        try:
            key = f"test_webhook_state:{state}"
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete test webhook state: {e}")
            return False

    async def set_oauth_state(self, state: str, data: Dict[str, Any], expire_seconds: int = None) -> bool:
        """Store OAuth2 CSRF state"""
        if not self.redis:
            return False
        
        try:
            expire_seconds = expire_seconds or settings.OAUTH_STATE_EXPIRE_SECONDS
            key = f"oauth_state:{state}"
            value = json.dumps(data)
            
            await self.redis.setex(key, expire_seconds, value)
            return True
        except Exception as e:
            logger.error(f"Failed to store OAuth state: {e}")
            return False
    
    async def get_oauth_state(self, state: str) -> Optional[Dict[str, Any]]:
        """Get OAuth2 CSRF state"""
        if not self.redis:
            return None
        
        try:
            key = f"oauth_state:{state}"
            value = await self.redis.get(key)
            
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Failed to get OAuth state: {e}")
            return None
    
    async def delete_oauth_state(self, state: str) -> bool:
        """Delete OAuth2 CSRF state"""
        if not self.redis:
            return False
        
        try:
            key = f"oauth_state:{state}"
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error(f"Failed to delete OAuth state: {e}")
            return False
    
    async def cleanup_expired_states(self):
        """Clean up expired OAuth states (Redis handles this automatically with TTL)"""
        if not self.redis:
            return
        
        try:
            # Get all oauth state keys
            pattern = "oauth_state:*"
            keys = await self.redis.keys(pattern)
            
            expired_count = 0
            for key in keys:
                ttl = await self.redis.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    expired_count += 1

            if expired_count > 0:
                logger.info(f"Found {expired_count} expired OAuth states (auto-cleaned by Redis)")
        except Exception as e:
            logger.error(f"Failed to check expired states: {e}")