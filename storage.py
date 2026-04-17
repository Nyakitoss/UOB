import os
import json
import redis
from datetime import datetime
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

class StorageManager:
    def __init__(self):
        self.use_redis = os.getenv("USE_REDIS", "false").lower() == "true"
        
        if self.use_redis:
            self.redis_client = self._create_redis_client()
            self._test_redis_connection()
        else:
            self.redis_client = None
            self._local_storage = {}
    
    def _create_redis_client(self):
        """Create Redis client from URL or individual parameters"""
        redis_url = os.getenv("REDIS_URL")
        
        if redis_url:
            # Use REDIS_URL (Railway format: redis://user:pass@host:port)
            print(f"**LOG: Connecting to Redis via URL: {redis_url.split('@')[1] if '@' in redis_url else redis_url}**")
            return redis.from_url(redis_url, decode_responses=True)
        else:
            # Use individual parameters (fallback)
            host = os.getenv("REDIS_HOST", "localhost")
            port = int(os.getenv("REDIS_PORT", 6379))
            password = os.getenv("REDIS_PASSWORD")
            
            print(f"**LOG: Connecting to Redis via host: {host}:{port}**")
            return redis.Redis(
                host=host,
                port=port,
                password=password,
                decode_responses=True
            )
    
    def _test_redis_connection(self):
        try:
            self.redis_client.ping()
            print("**LOG: Redis connected successfully**")
        except Exception as e:
            print(f"**LOG: Redis connection failed: {e}**")
            print("**LOG: Falling back to local storage**")
            self.use_redis = False
            self.redis_client = None
            self._local_storage = {}
    
    def get_chat_configs(self) -> Dict[str, Any]:
        """Get all chat configurations"""
        if self.use_redis and self.redis_client:
            try:
                data = self.redis_client.get("chat_configs")
                return json.loads(data) if data else {}
            except Exception as e:
                print(f"**LOG: Redis read error: {e}**")
                return {}
        else:
            return self._local_storage.get("chat_configs", {})
    
    def save_chat_configs(self, configs: Dict[str, Any]) -> bool:
        """Save all chat configurations"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.set("chat_configs", json.dumps(configs, ensure_ascii=False))
                return True
            except Exception as e:
                print(f"**LOG: Redis write error: {e}**")
                return False
        else:
            self._local_storage["chat_configs"] = configs
            return True
    
    def get_chat_config(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for specific chat"""
        configs = self.get_chat_configs()
        return configs.get(chat_id)
    
    def save_chat_config(self, chat_id: str, config: Dict[str, Any]) -> bool:
        """Save configuration for specific chat"""
        configs = self.get_chat_configs()
        configs[chat_id] = config
        return self.save_chat_configs(configs)
    
    def delete_chat_config(self, chat_id: str) -> bool:
        """Delete configuration for specific chat"""
        configs = self.get_chat_configs()
        if chat_id in configs:
            del configs[chat_id]
            return self.save_chat_configs(configs)
        return False
    
    def get_pinned_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get tracked pinned messages for chat"""
        if self.use_redis and self.redis_client:
            try:
                data = self.redis_client.get(f"pinned_messages:{chat_id}")
                return json.loads(data) if data else []
            except Exception as e:
                print(f"**LOG: Redis read error for pinned messages: {e}**")
                return []
        else:
            return self._local_storage.get(f"pinned_messages:{chat_id}", [])
    
    def save_pinned_messages(self, chat_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Save tracked pinned messages for chat"""
        if self.use_redis and self.redis_client:
            try:
                self.redis_client.set(f"pinned_messages:{chat_id}", json.dumps(messages, ensure_ascii=False))
                return True
            except Exception as e:
                print(f"**LOG: Redis write error for pinned messages: {e}**")
                return False
        else:
            self._local_storage[f"pinned_messages:{chat_id}"] = messages
            return True
    
    def add_pinned_message(self, chat_id: str, message_info: Dict[str, Any]) -> bool:
        """Add a pinned message to tracking"""
        messages = self.get_pinned_messages(chat_id)
        messages.append(message_info)
        return self.save_pinned_messages(chat_id, messages)
    
    def remove_pinned_message(self, chat_id: str, message_id: int) -> bool:
        """Remove a pinned message from tracking"""
        messages = self.get_pinned_messages(chat_id)
        messages = [msg for msg in messages if msg.get("message_id") != message_id]
        return self.save_pinned_messages(chat_id, messages)

# Глобальный экземпляр для совместимости с существующим кодом
storage = StorageManager()
