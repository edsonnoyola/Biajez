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

        # Always initialize fallback storage (used as backup even when Redis works)
        self.fallback_storage = {}

        # Support TLS connections (rediss://) for Render external Redis
        redis_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        }
        if redis_url.startswith("rediss://"):
            import ssl
            redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE

        try:
            self.redis_client = redis.from_url(
                redis_url,
                **redis_kwargs
            )
            # Test connection
            self.redis_client.ping()
            print("✅ Redis connected successfully")
            self.enabled = True
        except Exception as e:
            print(f"⚠️ Redis not available: {e}")
            print("   Falling back to in-memory sessions")
            self.enabled = False
    
    def get_session(self, phone_number: str) -> Dict:
        """
        Get session for a phone number

        Args:
            phone_number: User's phone number

        Returns:
            Session dict or new session if not found
        """
        key = f"whatsapp:session:{phone_number}"

        # Try Redis first (with retry)
        if self.enabled:
            for attempt in range(2):
                try:
                    # Verify connection is still alive
                    self.redis_client.ping()
                    data = self.redis_client.get(key)
                    if data:
                        session = json.loads(data)
                        pending_flights = len(session.get('pending_flights', []))
                        print(f"📦 REDIS GET {phone_number}: pending_flights={pending_flights}")
                        return session
                    else:
                        print(f"📦 REDIS GET {phone_number}: no session found, creating new")
                        return self._create_new_session()
                except Exception as e:
                    print(f"❌ Redis get error (attempt {attempt+1}): {e}")
                    if attempt == 0:
                        # Try to reconnect
                        try:
                            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                            rkw = {"decode_responses": True}
                            if redis_url.startswith("rediss://"):
                                import ssl
                                rkw["ssl_cert_reqs"] = ssl.CERT_NONE
                            self.redis_client = redis.from_url(redis_url, **rkw)
                            self.redis_client.ping()
                            print("🔄 Redis reconnected")
                        except:
                            self.enabled = False
                            print("⚠️ Redis reconnect failed, switching to fallback")

        # Fallback to in-memory
        print(f"⚠️ FALLBACK GET {phone_number} (Redis enabled={self.enabled})")
        if phone_number in self.fallback_storage:
            session = self.fallback_storage[phone_number]
            pending_flights = len(session.get('pending_flights', []))
            print(f"   Found in fallback: pending_flights={pending_flights}")
            return session

        # Create new session
        print(f"   Creating new session in fallback")
        return self._create_new_session()
    
    def save_session(self, phone_number: str, session: Dict, ttl: int = 14400):
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
        pending_flights = len(session.get('pending_flights', []))

        # Try Redis first (with retry)
        if self.enabled:
            for attempt in range(2):
                try:
                    # Verify connection is still alive
                    self.redis_client.ping()
                    self.redis_client.setex(
                        key,
                        ttl,
                        json.dumps(session, default=str)
                    )
                    print(f"💾 REDIS SAVE {phone_number}: pending_flights={pending_flights}")
                    return  # Success
                except Exception as e:
                    print(f"❌ Redis save error (attempt {attempt+1}): {e}")
                    if attempt == 0:
                        # Try to reconnect
                        try:
                            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
                            rkw = {"decode_responses": True}
                            if redis_url.startswith("rediss://"):
                                import ssl
                                rkw["ssl_cert_reqs"] = ssl.CERT_NONE
                            self.redis_client = redis.from_url(redis_url, **rkw)
                            self.redis_client.ping()
                            print("🔄 Redis reconnected for save")
                        except:
                            self.enabled = False
                            print("⚠️ Redis reconnect failed, switching to fallback")

        # Fallback to in-memory (always save to fallback as backup)
        print(f"⚠️ FALLBACK SAVE {phone_number}: pending_flights={pending_flights}")
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

        # Support TLS connections (rediss://) for Render external Redis
        redis_kwargs = {
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        }
        if redis_url.startswith("rediss://"):
            import ssl
            redis_kwargs["ssl_cert_reqs"] = ssl.CERT_NONE

        try:
            self.redis_client = redis.from_url(
                redis_url,
                **redis_kwargs
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


class DuffelCircuitBreaker:
    """Circuit breaker for Duffel API — stops hammering when the API is down"""

    # States: closed (normal), open (blocked), half_open (testing)
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        """
        Args:
            failure_threshold: consecutive failures before opening circuit
            recovery_timeout: seconds to wait before trying again (half-open)
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = self.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._redis_key = "duffel:circuit_breaker"

    def _get_state_from_redis(self, redis_client) -> dict:
        """Read circuit breaker state from Redis (shared across workers)"""
        try:
            data = redis_client.get(self._redis_key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"⚠️ Circuit breaker Redis read failed: {e}")
        return {"state": self.CLOSED, "failures": 0, "last_failure": 0.0}

    def _save_state_to_redis(self, redis_client, state: str, failures: int, last_failure: float):
        """Persist circuit breaker state to Redis"""
        try:
            redis_client.setex(
                self._redis_key,
                self.recovery_timeout * 3,  # TTL = 3x recovery so it auto-clears
                json.dumps({"state": state, "failures": failures, "last_failure": last_failure})
            )
        except Exception as e:
            print(f"⚠️ Circuit breaker Redis save failed: {e}")

    def can_request(self, redis_client=None) -> bool:
        """Check if a request is allowed through the circuit breaker"""
        now = datetime.now().timestamp()

        if redis_client:
            cb = self._get_state_from_redis(redis_client)
            state = cb["state"]
            failures = cb["failures"]
            last_failure = cb["last_failure"]
        else:
            state = self._state
            failures = self._failure_count
            last_failure = self._last_failure_time

        if state == self.CLOSED:
            return True
        elif state == self.OPEN:
            # Check if recovery timeout has passed → half-open
            if now - last_failure >= self.recovery_timeout:
                return True  # Allow one test request
            return False
        elif state == self.HALF_OPEN:
            return True  # Allow test request
        return True

    def record_success(self, redis_client=None):
        """Record a successful API call — reset the circuit"""
        self._state = self.CLOSED
        self._failure_count = 0
        if redis_client:
            self._save_state_to_redis(redis_client, self.CLOSED, 0, 0.0)

    def record_failure(self, redis_client=None):
        """Record a failed API call — may trip the circuit"""
        now = datetime.now().timestamp()
        self._failure_count += 1
        self._last_failure_time = now

        if redis_client:
            cb = self._get_state_from_redis(redis_client)
            failures = cb["failures"] + 1
        else:
            failures = self._failure_count

        if failures >= self.failure_threshold:
            self._state = self.OPEN
            print(f"🔴 CIRCUIT BREAKER OPEN — Duffel API down ({failures} consecutive failures). Blocking for {self.recovery_timeout}s")
            if redis_client:
                self._save_state_to_redis(redis_client, self.OPEN, failures, now)
        else:
            if redis_client:
                self._save_state_to_redis(redis_client, self.CLOSED, failures, now)

    def get_status(self, redis_client=None) -> dict:
        """Get current circuit breaker status"""
        if redis_client:
            cb = self._get_state_from_redis(redis_client)
            return {"state": cb["state"], "failures": cb["failures"]}
        return {"state": self._state, "failures": self._failure_count}


# Global instances
session_manager = RedisSessionManager()
rate_limiter = RateLimiter(max_messages=10, window_seconds=60)
duffel_breaker = DuffelCircuitBreaker(failure_threshold=5, recovery_timeout=60)
