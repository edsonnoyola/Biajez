"""
Price Alert Service - Monitor prices and notify on drops
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.db.database import Base
import json

class PriceAlert(Base):
    """Price alert model"""
    __tablename__ = "price_alerts"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    phone_number = Column(String)  # For WhatsApp notifications

    # Search criteria
    search_type = Column(String)  # "flight" or "hotel"
    origin = Column(String)       # For flights
    destination = Column(String)
    departure_date = Column(String)
    return_date = Column(String)  # Optional

    # Price tracking
    target_price = Column(Float)          # Alert when price drops below this
    initial_price = Column(Float)         # Price when alert was created
    lowest_price = Column(Float)          # Lowest price seen
    current_price = Column(Float)         # Last checked price

    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_checked_at = Column(DateTime)
    notified_at = Column(DateTime)        # Last time user was notified
    notification_count = Column(Integer, default=0)

    # Extra data (JSON)
    extra_data = Column(Text)  # Store search preferences, etc.


class PriceAlertService:
    """Manage price alerts and notifications"""

    def __init__(self, db: Session):
        self.db = db

    def create_alert(
        self,
        user_id: str,
        phone_number: str,
        search_type: str,
        destination: str,
        departure_date: str,
        origin: str = None,
        return_date: str = None,
        target_price: float = None,
        current_price: float = None
    ) -> Dict:
        """Create a new price alert"""
        try:
            # If no target price, set to 10% below current
            if not target_price and current_price:
                target_price = current_price * 0.9

            alert = PriceAlert(
                user_id=user_id,
                phone_number=phone_number,
                search_type=search_type,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                target_price=target_price,
                initial_price=current_price,
                lowest_price=current_price,
                current_price=current_price,
                is_active=True
            )

            self.db.add(alert)
            self.db.commit()
            self.db.refresh(alert)

            return {
                "success": True,
                "alert_id": alert.id,
                "message": f"Alerta creada. Te avisaré cuando el precio baje de ${target_price:.2f}"
            }

        except Exception as e:
            print(f"Error creating alert: {e}")
            return {"success": False, "error": str(e)}

    def get_user_alerts(self, user_id: str, active_only: bool = True) -> List[Dict]:
        """Get all alerts for a user"""
        query = self.db.query(PriceAlert).filter(PriceAlert.user_id == user_id)

        if active_only:
            query = query.filter(PriceAlert.is_active == True)

        alerts = query.order_by(PriceAlert.created_at.desc()).all()

        return [
            {
                "id": a.id,
                "type": a.search_type,
                "route": f"{a.origin or ''} → {a.destination}".strip(" → "),
                "date": a.departure_date,
                "target_price": a.target_price,
                "current_price": a.current_price,
                "lowest_price": a.lowest_price,
                "is_active": a.is_active,
                "created_at": a.created_at.isoformat() if a.created_at else None
            }
            for a in alerts
        ]

    def deactivate_alert(self, alert_id: int, user_id: str = None) -> Dict:
        """Deactivate an alert"""
        query = self.db.query(PriceAlert).filter(PriceAlert.id == alert_id)
        if user_id:
            query = query.filter(PriceAlert.user_id == user_id)

        alert = query.first()

        if not alert:
            return {"success": False, "error": "Alerta no encontrada"}

        alert.is_active = False
        self.db.commit()

        return {"success": True, "message": "Alerta desactivada"}

    def update_price(self, alert_id: int, new_price: float) -> Dict:
        """Update the current price for an alert"""
        alert = self.db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()

        if not alert:
            return {"success": False, "error": "Alert not found"}

        alert.current_price = new_price
        alert.last_checked_at = datetime.utcnow()

        if new_price < alert.lowest_price:
            alert.lowest_price = new_price

        should_notify = new_price <= alert.target_price and alert.is_active

        self.db.commit()

        return {
            "success": True,
            "should_notify": should_notify,
            "price_dropped": new_price < alert.initial_price,
            "drop_percentage": ((alert.initial_price - new_price) / alert.initial_price * 100) if alert.initial_price else 0
        }

    def get_active_alerts_for_checking(self) -> List[PriceAlert]:
        """Get all active alerts that need price checking"""
        # Get alerts that haven't been checked in the last 6 hours
        cutoff = datetime.utcnow() - timedelta(hours=6)

        return self.db.query(PriceAlert).filter(
            PriceAlert.is_active == True,
            (PriceAlert.last_checked_at == None) | (PriceAlert.last_checked_at < cutoff)
        ).all()

    def format_alerts_for_whatsapp(self, alerts: List[Dict]) -> str:
        """Format alerts list for WhatsApp"""
        if not alerts:
            return "No tienes alertas de precio activas.\n\nPara crear una, busca un vuelo o hotel y di 'crear alerta'."

        msg = "*Tus alertas de precio*\n\n"

        for i, alert in enumerate(alerts, 1):
            status = "🟢" if alert['is_active'] else "⚪"
            msg += f"{status} *{i}. {alert['route']}*\n"
            msg += f"   {alert['date']}\n"
            msg += f"   Meta: ${alert['target_price']:.2f}\n"
            msg += f"   Actual: ${alert['current_price']:.2f}\n\n"

        msg += "_Responde con el número para desactivar una alerta_"

        return msg
