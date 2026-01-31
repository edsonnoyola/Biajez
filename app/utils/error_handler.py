"""
Error Handler - Centralized error handling for the application
"""
from fastapi import HTTPException
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class DuffelAPIError(Exception):
    """Custom exception for Duffel API errors"""
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class StripeAPIError(Exception):
    """Custom exception for Stripe API errors"""
    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

def handle_duffel_error(e: Exception, context: str = "") -> HTTPException:
    """
    Handle Duffel API errors with proper logging and user-friendly messages
    
    Args:
        e: The exception that occurred
        context: Additional context about where the error occurred
    
    Returns:
        HTTPException with appropriate status code and message
    """
    error_msg = str(e)
    logger.error(f"Duffel API Error [{context}]: {error_msg}")
    
    # Parse common Duffel errors
    if "401" in error_msg or "Unauthorized" in error_msg:
        return HTTPException(
            status_code=401,
            detail="Invalid API credentials. Please contact support."
        )
    elif "404" in error_msg or "not found" in error_msg.lower():
        return HTTPException(
            status_code=404,
            detail="The requested resource was not found."
        )
    elif "429" in error_msg or "rate limit" in error_msg.lower():
        return HTTPException(
            status_code=429,
            detail="Too many requests. Please try again later."
        )
    elif "timeout" in error_msg.lower():
        return HTTPException(
            status_code=504,
            detail="Request timeout. Please try again."
        )
    else:
        return HTTPException(
            status_code=502,
            detail="Error communicating with booking service. Please try again."
        )

def handle_stripe_error(e: Exception, context: str = "") -> HTTPException:
    """
    Handle Stripe API errors with proper logging and user-friendly messages
    
    Args:
        e: The exception that occurred
        context: Additional context about where the error occurred
    
    Returns:
        HTTPException with appropriate status code and message
    """
    error_msg = str(e)
    logger.error(f"Stripe API Error [{context}]: {error_msg}")
    
    # Parse common Stripe errors
    if "card" in error_msg.lower() and "declined" in error_msg.lower():
        return HTTPException(
            status_code=402,
            detail="Your card was declined. Please try a different payment method."
        )
    elif "insufficient" in error_msg.lower():
        return HTTPException(
            status_code=402,
            detail="Insufficient funds. Please try a different payment method."
        )
    elif "expired" in error_msg.lower():
        return HTTPException(
            status_code=402,
            detail="Your card has expired. Please use a different payment method."
        )
    elif "Invalid API Key" in error_msg:
        logger.critical("Stripe API key is invalid or not configured!")
        return HTTPException(
            status_code=500,
            detail="Payment system configuration error. Please contact support."
        )
    else:
        return HTTPException(
            status_code=502,
            detail="Payment processing error. Please try again."
        )

def handle_database_error(e: Exception, context: str = "") -> HTTPException:
    """
    Handle database errors
    """
    error_msg = str(e)
    logger.error(f"Database Error [{context}]: {error_msg}")
    
    return HTTPException(
        status_code=500,
        detail="Database error. Please try again or contact support."
    )

def log_info(message: str, context: str = ""):
    """Log info message with context"""
    if context:
        logger.info(f"[{context}] {message}")
    else:
        logger.info(message)

def log_warning(message: str, context: str = ""):
    """Log warning message with context"""
    if context:
        logger.warning(f"[{context}] {message}")
    else:
        logger.warning(message)

def log_error(message: str, context: str = "", exc_info: bool = False):
    """Log error message with context"""
    if context:
        logger.error(f"[{context}] {message}", exc_info=exc_info)
    else:
        logger.error(message, exc_info=exc_info)
