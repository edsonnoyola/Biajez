"""
Stripe Payment Service for Biajez Platform

Handles all Stripe payment operations including:
- Creating payment intents
- Confirming payments
- Processing refunds
- Webhook validation
"""

import stripe
import os
from datetime import datetime
from typing import Optional, Dict, Any
from decimal import Decimal

# Initialize Stripe with API key
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class StripePaymentService:
    """Service for handling Stripe payment operations"""
    
    def __init__(self):
        self.api_key = os.getenv("STRIPE_SECRET_KEY")
        if not self.api_key or self.api_key == "sk_test_placeholder_please_updateplaceholder_please_update":
            print("WARNING: Stripe API key not configured. Payments will fail.")
    
    def create_payment_intent(
        self,
        amount: float,
        currency: str = "USD",
        user_id: str = None,
        offer_id: str = None,
        provider: str = None,
        customer_email: str = None
    ) -> Dict[str, Any]:
        """
        Create a Stripe Payment Intent
        
        Args:
            amount: Amount in dollars (will be converted to cents)
            currency: Currency code (default: USD)
            user_id: User identifier
            offer_id: Flight offer ID
            provider: Provider name (DUFFEL, AMADEUS, etc.)
            customer_email: Customer email for receipt
            
        Returns:
            Dict with payment_intent_id, client_secret, and status
        """
        try:
            # Convert dollars to cents (Stripe uses smallest currency unit)
            amount_cents = int(float(amount) * 100)
            
            # Create metadata for tracking
            metadata = {
                "user_id": user_id or "unknown",
                "offer_id": offer_id or "unknown",
                "provider": provider or "unknown",
                "platform": "biajez"
            }
            
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata=metadata,
                receipt_email=customer_email,
                description=f"Flight booking - {offer_id}",
                automatic_payment_methods={"enabled": True}
            )
            
            print(f"✅ Payment Intent created: {intent.id} for ${amount} {currency}")
            
            return {
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status,
                "amount": amount,
                "currency": currency
            }
            
        except stripe.error.StripeError as e:
            print(f"❌ Stripe Error: {e}")
            return {
                "error": str(e),
                "type": e.__class__.__name__
            }
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")
            return {
                "error": str(e),
                "type": "UnexpectedError"
            }
    
    def confirm_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirm a payment intent and check its status
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Dict with status and payment details
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            return {
                "payment_intent_id": intent.id,
                "status": intent.status,
                "amount": intent.amount / 100,  # Convert cents to dollars
                "currency": intent.currency.upper(),
                "metadata": intent.metadata,
                "succeeded": intent.status == "succeeded"
            }
            
        except stripe.error.StripeError as e:
            print(f"❌ Stripe Error retrieving payment: {e}")
            return {
                "error": str(e),
                "succeeded": False
            }
    
    def create_refund(
        self,
        payment_intent_id: str,
        amount: Optional[float] = None,
        reason: str = "requested_by_customer"
    ) -> Dict[str, Any]:
        """
        Create a refund for a payment
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            amount: Amount to refund in dollars (None = full refund)
            reason: Reason for refund
            
        Returns:
            Dict with refund details
        """
        try:
            refund_params = {
                "payment_intent": payment_intent_id,
                "reason": reason
            }
            
            if amount is not None:
                refund_params["amount"] = int(float(amount) * 100)
            
            refund = stripe.Refund.create(**refund_params)
            
            print(f"✅ Refund created: {refund.id} for payment {payment_intent_id}")
            
            return {
                "refund_id": refund.id,
                "status": refund.status,
                "amount": refund.amount / 100,
                "currency": refund.currency.upper(),
                "succeeded": True
            }
            
        except stripe.error.StripeError as e:
            print(f"❌ Stripe Refund Error: {e}")
            return {
                "error": str(e),
                "succeeded": False
            }
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        webhook_secret: str
    ) -> Optional[Dict[str, Any]]:
        """
        Validate Stripe webhook signature and parse event
        
        Args:
            payload: Raw request body
            signature: Stripe-Signature header
            webhook_secret: Webhook signing secret
            
        Returns:
            Parsed event dict or None if invalid
        """
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            return event
        except ValueError:
            print("❌ Invalid webhook payload")
            return None
        except stripe.error.SignatureVerificationError:
            print("❌ Invalid webhook signature")
            return None
    
    def get_payment_status(self, payment_intent_id: str) -> str:
        """
        Get current status of a payment intent
        
        Args:
            payment_intent_id: Stripe Payment Intent ID
            
        Returns:
            Status string (succeeded, processing, requires_action, etc.)
        """
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return intent.status
        except stripe.error.StripeError as e:
            print(f"❌ Error getting payment status: {e}")
            return "error"
    
    def create_customer(
        self,
        email: str,
        name: str = None,
        user_id: str = None
    ) -> Optional[str]:
        """
        Create a Stripe customer for repeat payments
        
        Args:
            email: Customer email
            name: Customer name
            user_id: Internal user ID
            
        Returns:
            Stripe customer ID or None
        """
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id} if user_id else {}
            )
            print(f"✅ Stripe customer created: {customer.id}")
            return customer.id
        except stripe.error.StripeError as e:
            print(f"❌ Error creating customer: {e}")
            return None
