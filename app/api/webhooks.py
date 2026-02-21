"""
Webhook endpoints for receiving Duffel notifications.

FIXED:
- Added idempotency check for duplicate events
- Added admin endpoint to register webhook with Duffel API
- Added admin endpoint to list/delete webhooks
- Added ping test endpoint
- Improved error handling and logging
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Header, Query
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.webhook_service import WebhookService
import os
import json
import requests as http_requests

router = APIRouter()


@router.post("/webhooks/duffel")
async def handle_duffel_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_duffel_signature: str = Header(None, alias="X-Duffel-Signature")
):
    """
    Handle incoming webhooks from Duffel.

    Events handled:
    - order.airline_initiated_change_detected: Airline changed the flight
    - order.updated: Order was updated
    - order.created: Order successfully booked
    - order.creation_failed: Order booking failed (after 202 acceptance)
    - payment.created: Payment for hold order
    - ping.triggered: Webhook test ping

    Returns:
        200 OK always (to prevent Duffel retries for processed events)
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Parse JSON
        event_data = json.loads(body.decode())
        event_type = event_data.get("type", "unknown")
        event_id = event_data.get("id", "unknown")

        print(f"📨 Received webhook: {event_type} (ID: {event_id})")

        # Initialize webhook service
        webhook_service = WebhookService(db)

        # Verify signature (if secret is configured)
        webhook_secret = os.getenv("DUFFEL_WEBHOOK_SECRET")
        if webhook_secret and x_duffel_signature:
            is_valid = webhook_service.verify_signature(
                payload=body,
                signature_header=x_duffel_signature,
                secret=webhook_secret
            )

            if not is_valid:
                print(f"❌ Invalid webhook signature for event {event_id}")
                raise HTTPException(status_code=400, detail="Invalid signature")
        elif webhook_secret and not x_duffel_signature:
            print(f"⚠️  No signature header on event {event_id} (secret is configured)")
            # Don't reject - might be a ping or test

        # Check for duplicate events (idempotency)
        if webhook_service.is_duplicate_event(event_data):
            print(f"⚠️  Skipping duplicate event: {event_id}")
            return {
                "status": "duplicate",
                "event_id": event_id,
                "event_type": event_type,
                "message": "Event already processed"
            }

        # Store event in database
        webhook_event = webhook_service.store_event(event_type, event_data)

        # Process event
        result = webhook_service.process_event(event_type, event_data)

        # Mark as processed
        webhook_service.mark_event_processed(
            event_id=webhook_event.id,
            success=result.get("success", False),
            error=result.get("error")
        )

        print(f"✅ Webhook processed: {event_type} → {result.get('success', False)}")

        # Always return 200 OK to Duffel
        return {
            "status": "success",
            "event_id": webhook_event.id,
            "event_type": event_type,
            "processed": True
        }

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    except HTTPException:
        raise  # Re-raise HTTP exceptions (like 400 for bad signature)

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()

        # Still return 200 to prevent Duffel from retrying unrecoverable errors
        return {
            "status": "error",
            "error": str(e),
            "processed": False
        }


# ===== ADMIN: WEBHOOK MANAGEMENT =====

@router.post("/admin/webhooks/register")
async def register_duffel_webhook(
    admin_secret: str = Query(...),
    webhook_url: str = Query(None),
):
    """
    Register a webhook with Duffel API.

    This creates a webhook subscription in Duffel that will send events
    to our /webhooks/duffel endpoint.

    Args:
        admin_secret: Admin authentication secret
        webhook_url: Override webhook URL (defaults to production URL)

    Returns:
        Webhook ID and secret (save the secret in DUFFEL_WEBHOOK_SECRET!)
    """
    expected_secret = os.getenv("ADMIN_SECRET")
    if admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not duffel_token:
        raise HTTPException(status_code=500, detail="DUFFEL_ACCESS_TOKEN not configured")

    # Default to production URL
    if not webhook_url:
        base_url = os.getenv("BASE_URL", "https://biajez.onrender.com")
        webhook_url = f"{base_url}/webhooks/duffel"

    # Duffel valid event types (from API docs)
    events = [
        "order.created",
        "order.creation_failed",
        "order.airline_initiated_change_detected",
        "air.order.changed",
        "order_cancellation.created",
        "order_cancellation.confirmed",
        "payment.created",
    ]

    print(f"🔧 Registering webhook: {webhook_url}")
    print(f"   Events: {events}")

    try:
        response = http_requests.post(
            "https://api.duffel.com/air/webhooks",
            headers={
                "Authorization": f"Bearer {duffel_token}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "data": {
                    "url": webhook_url,
                    "events": events
                }
            },
            timeout=30
        )

        if response.status_code in (200, 201):
            data = response.json().get("data", {})
            webhook_id = data.get("id")
            webhook_secret = data.get("secret")

            print(f"✅ Webhook registered!")
            print(f"   ID: {webhook_id}")
            print(f"   Secret: {webhook_secret}")
            print(f"   ⚠️  SAVE THE SECRET! Set it as DUFFEL_WEBHOOK_SECRET env var")

            return {
                "success": True,
                "webhook_id": webhook_id,
                "webhook_secret": webhook_secret,
                "url": webhook_url,
                "events": events,
                "message": "IMPORTANT: Save the webhook_secret as DUFFEL_WEBHOOK_SECRET environment variable!"
            }
        else:
            error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            print(f"❌ Duffel webhook registration failed: {response.status_code}")
            print(f"   Response: {error_detail}")

            return {
                "success": False,
                "status_code": response.status_code,
                "error": error_detail
            }

    except Exception as e:
        print(f"❌ Error registering webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/webhooks/list")
async def list_duffel_webhooks(
    admin_secret: str = Query(...)
):
    """List all registered webhooks in Duffel."""
    expected_secret = os.getenv("ADMIN_SECRET")
    if admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not duffel_token:
        raise HTTPException(status_code=500, detail="DUFFEL_ACCESS_TOKEN not configured")

    try:
        response = http_requests.get(
            "https://api.duffel.com/air/webhooks",
            headers={
                "Authorization": f"Bearer {duffel_token}",
                "Duffel-Version": "v2",
                "Accept": "application/json",
            },
            timeout=15
        )

        if response.status_code == 200:
            webhooks = response.json().get("data", [])
            return {
                "success": True,
                "webhooks": webhooks,
                "count": len(webhooks)
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/webhooks/{webhook_id}")
async def delete_duffel_webhook(
    webhook_id: str,
    admin_secret: str = Query(...)
):
    """Delete a webhook from Duffel."""
    expected_secret = os.getenv("ADMIN_SECRET")
    if admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not duffel_token:
        raise HTTPException(status_code=500, detail="DUFFEL_ACCESS_TOKEN not configured")

    try:
        response = http_requests.delete(
            f"https://api.duffel.com/air/webhooks/{webhook_id}",
            headers={
                "Authorization": f"Bearer {duffel_token}",
                "Duffel-Version": "v2",
            },
            timeout=15
        )

        if response.status_code in (200, 204):
            return {"success": True, "deleted": webhook_id}
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/admin/webhooks/ping/{webhook_id}")
async def ping_duffel_webhook(
    webhook_id: str,
    admin_secret: str = Query(...)
):
    """Send a test ping to a webhook."""
    expected_secret = os.getenv("ADMIN_SECRET")
    if admin_secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    duffel_token = os.getenv("DUFFEL_ACCESS_TOKEN")
    if not duffel_token:
        raise HTTPException(status_code=500, detail="DUFFEL_ACCESS_TOKEN not configured")

    try:
        response = http_requests.post(
            f"https://api.duffel.com/air/webhooks/{webhook_id}/actions/ping",
            headers={
                "Authorization": f"Bearer {duffel_token}",
                "Duffel-Version": "v2",
            },
            timeout=15
        )

        return {
            "success": response.status_code in (200, 201, 204),
            "status_code": response.status_code,
            "response": response.text[:500] if response.text else "OK"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== NOTIFICATION ENDPOINTS =====

@router.get("/notifications/{user_id}")
async def get_user_notifications(
    user_id: str,
    include_read: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get notifications for a user.

    Args:
        user_id: User ID
        include_read: Include read notifications (default: False)

    Returns:
        List of notifications
    """
    from app.models.models import Notification

    query = db.query(Notification).filter(Notification.user_id == user_id)

    if not include_read:
        query = query.filter(Notification.read == 0)

    notifications = query.order_by(Notification.created_at.desc()).all()

    return {
        "notifications": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "message": n.message,
                "read": bool(n.read),
                "action_required": bool(n.action_required),
                "related_order_id": n.related_order_id,
                "extra_data": json.loads(n.extra_data) if n.extra_data else None,
                "created_at": n.created_at
            }
            for n in notifications
        ],
        "count": len(notifications)
    }

@router.post("/notifications/{notification_id}/mark-read")
async def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    from app.models.models import Notification

    notification = db.query(Notification).filter(Notification.id == notification_id).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read = 1
    db.commit()

    return {
        "success": True,
        "notification_id": notification_id,
        "read": True
    }

@router.get("/notifications/unread-count/{user_id}")
async def get_unread_count(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Get count of unread notifications for a user."""
    from app.models.models import Notification

    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == 0
    ).count()

    return {
        "user_id": user_id,
        "unread_count": count
    }
