"""
Redis Session Manager for WhatsApp
Persistent session storage with TTL
"""

import redis
import json
import os
from typing import Dict, Optional
from datetime import datetime

class RedisSessionManager:
    """Manage WhatsApp user sessions with Redis"""
    
    def __init__(self):
        """Initialize Redis connection"""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print("✅ Redis connected successfully")
            self.enabled = True
        except Exception as e:
            print(f"⚠️ Redis not available: {e}")
            print("   Falling back to in-memory sessions")
            self.enabled = False
            self.fallback_storage = {}
    
    def get_session(self, phone_number: str) -> Dict:
        """
        Get session for a phone number
        
        Args:
            phone_number: User's phone number
            
        Returns:
            Session dict or new session if not found
        """
        key = f"whatsapp:session:{phone_number}"
        
        if self.enabled:
            try:
                data = self.redis_client.get(key)
                if data:
                    session = json.loads(data)
                    print(f"📦 Loaded session for {phone_number} from Redis")
                    return session
            except Exception as e:
                print(f"❌ Redis get error: {e}")
        else:
            # Fallback to in-memory
            if phone_number in self.fallback_storage:
                return self.fallback_storage[phone_number]
        
        # Create new session
        return self._create_new_session()
    
    def save_session(self, phone_number: str, session: Dict, ttl: int = 3600):
        """
        Save session with TTL
        
        Args:
            phone_number: User's phone number
            session: Session data to save
            ttl: Time to live in seconds (default 1 hour)
        """
        key = f"whatsapp:session:{phone_number}"
        
        # Add last updated timestamp
        session["last_updated"] = datetime.now().isoformat()
        
        if self.enabled:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(session, default=str)
                )
                print(f"💾 Saved session for {phone_number} (TTL: {ttl}s)")
            except Exception as e:
                print(f"❌ Redis save error: {e}")
                # Fallback
                self.fallback_storage[phone_number] = session
        else:
            # In-memory fallback
            self.fallback_storage[phone_number] = session
    
    def delete_session(self, phone_number: str):
        """Delete a session"""
        key = f"whatsapp:session:{phone_number}"
        
        if self.enabled:
            try:
                self.redis_client.delete(key)
                print(f"🗑️ Deleted session for {phone_number}")
            except Exception as e:
                print(f"❌ Redis delete error: {e}")
        else:
            self.fallback_storage.pop(phone_number, None)
    
    def extend_ttl(self, phone_number: str, ttl: int = 3600):
        """Extend session TTL"""
        key = f"whatsapp:session:{phone_number}"
        
        if self.enabled:
            try:
                self.redis_client.expire(key, ttl)
            except Exception as e:
                print(f"❌ Redis expire error: {e}")
    
    def _create_new_session(self) -> Dict:
        """Create a new empty session"""
        return {
            "messages": [],
            "user_id": None,
            "pending_flights": [],
            "selected_flight": None,
            "pending_hotels": [],
            "selected_hotel": None,
            "created_at": datetime.now().isoformat()
        }


class RateLimiter:
    """Rate limiting for WhatsApp messages"""
    
    def __init__(self, max_messages: int = 10, window_seconds: int = 60):
        """
        Initialize rate limiter
        
        Args:
            max_messages: Maximum messages allowed in window
            window_seconds: Time window in seconds
        """
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        
        self.max_messages = max_messages
        self.window_seconds = window_seconds
        
        try:
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.redis_client.ping()
            self.enabled = True
            print("✅ Rate limiter initialized with Redis")
        except Exception as e:
            print(f"⚠️ Rate limiter fallback to in-memory: {e}")
            self.enabled = False
            self.fallback_storage = {}
    
    def is_allowed(self, phone_number: str) -> tuple[bool, int]:
        """
        Check if user is rate limited
        
        Args:
            phone_number: User's phone number
            
        Returns:
            (allowed: bool, remaining: int)
        """
        key = f"whatsapp:ratelimit:{phone_number}"
        
        if self.enabled:
            try:
                # Increment counter
                count = self.redis_client.incr(key)
                
                # Set expiry on first message
                if count == 1:
                    self.redis_client.expire(key, self.window_seconds)
                
                remaining = max(0, self.max_messages - count)
                allowed = count <= self.max_messages
                
                if not allowed:
                    ttl = self.redis_client.ttl(key)
                    print(f"🚫 Rate limited: {phone_number} ({count}/{self.max_messages}, reset in {ttl}s)")
                
                return (allowed, remaining)
                
            except Exception as e:
                print(f"❌ Rate limit check error: {e}")
                return (True, self.max_messages)  # Fail open
        else:
            # In-memory fallback
            now = datetime.now().timestamp()
            
            if phone_number not in self.fallback_storage:
                self.fallback_storage[phone_number] = []
            
            # Clean old timestamps
            cutoff = now - self.window_seconds
            self.fallback_storage[phone_number] = [
                ts for ts in self.fallback_storage[phone_number] if ts > cutoff
            ]
            
            count = len(self.fallback_storage[phone_number])
            
            if count >= self.max_messages:
                return (False, 0)
            
            # Add new timestamp
            self.fallback_storage[phone_number].append(now)
            return (True, self.max_messages - count - 1)
    
    def reset(self, phone_number: str):
        """Reset rate limit for a user"""
        key = f"whatsapp:ratelimit:{phone_number}"
        
        if self.enabled:
            try:
                self.redis_client.delete(key)
                print(f"♻️ Reset rate limit for {phone_number}")
            except Exception as e:
                print(f"❌ Rate limit reset error: {e}")
        else:
            self.fallback_storage.pop(phone_number, None)


# Global instances
session_manager = RedisSessionManager()
rate_limiter = RateLimiter(max_messages=10, window_seconds=60)
