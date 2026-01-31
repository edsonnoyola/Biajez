"""
Webhook endpoints for receiving Duffel notifications
"""
from fastapi import APIRouter, Request, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.services.webhook_service import WebhookService
import os
import json

router = APIRouter()

@router.post("/webhooks/duffel")
async def handle_duffel_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_duffel_signature: str = Header(None)
):
    """
    Handle incoming webhooks from Duffel
    
    Events handled:
    - order.airline_initiated_change_detected
    - order.cancelled
    - order.changed
    - order.created
    - payment.failed
    
    Returns:
        200 OK if processed successfully
        400 Bad Request if signature invalid
        500 Internal Server Error if processing failed
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Parse JSON
        event_data = json.loads(body.decode())
        event_type = event_data.get("type")
        
        print(f"📨 Received webhook: {event_type}")
        
        # Initialize webhook service
        webhook_service = WebhookService(db)
        
        # Verify signature (if secret is configured)
        webhook_secret = os.getenv("DUFFEL_WEBHOOK_SECRET")
        if webhook_secret and x_duffel_signature:
            is_valid = webhook_service.verify_signature(
                payload=body,
                signature=x_duffel_signature,
                secret=webhook_secret
            )
            
            if not is_valid:
                print("❌ Invalid webhook signature")
                raise HTTPException(status_code=400, detail="Invalid signature")
        
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
        
        print(f"✅ Webhook processed successfully: {event_type}")
        
        # Return 200 OK to Duffel
        return {
            "status": "success",
            "event_id": webhook_event.id,
            "event_type": event_type,
            "processed": True
        }
        
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        
        # Still return 200 to prevent retries for unrecoverable errors
        # But log the error
        return {
            "status": "error",
            "error": str(e),
            "processed": False
        }

@router.get("/notifications/{user_id}")
async def get_user_notifications(
    user_id: str,
    include_read: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get notifications for a user
    
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
    """
    Mark a notification as read
    """
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
    """
    Get count of unread notifications for a user
    """
    from app.models.models import Notification
    
    count = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.read == 0
    ).count()
    
    return {
        "user_id": user_id,
        "unread_count": count
    }
