"""
Scheduler Service - APScheduler setup for background jobs
"""
import os
import traceback
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from app.db.database import SessionLocal


class SchedulerService:
    """Background job scheduler using APScheduler"""

    _instance = None
    _scheduler = None
    _job_errors = {}  # Track consecutive failures per job

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scheduler = AsyncIOScheduler()
            cls._job_errors = {}
        return cls._instance

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler

    def _log_job_error(self, job_id: str, error: Exception):
        """Track job failures and alert on consecutive errors"""
        if job_id not in self._job_errors:
            self._job_errors[job_id] = {"count": 0, "last_error": None}

        self._job_errors[job_id]["count"] += 1
        self._job_errors[job_id]["last_error"] = datetime.utcnow().isoformat()
        count = self._job_errors[job_id]["count"]

        print(f"🚨 SCHEDULER ERROR [{job_id}] (failure #{count}): {error}")
        if count >= 3:
            print(f"🚨 ALERT: Job '{job_id}' has failed {count} consecutive times!")
            self._send_failure_alert(job_id, count, str(error))

    def _log_job_success(self, job_id: str):
        """Reset failure counter on success"""
        if job_id in self._job_errors:
            self._job_errors[job_id] = {"count": 0, "last_error": None}

    def _send_failure_alert(self, job_id: str, count: int, error_msg: str):
        """Send alert when a job keeps failing (WhatsApp to admin)"""
        try:
            admin_phone = os.getenv("ADMIN_PHONE")
            if not admin_phone:
                return
            from app.services.push_notification_service import PushNotificationService
            import asyncio
            push_svc = PushNotificationService()
            msg = (
                f"🚨 *Alerta Scheduler*\n\n"
                f"Job: {job_id}\n"
                f"Fallos consecutivos: {count}\n"
                f"Error: {error_msg[:200]}"
            )
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(push_svc.send_message(admin_phone, msg))
                else:
                    loop.run_until_complete(push_svc.send_message(admin_phone, msg))
            except RuntimeError:
                pass
        except Exception as alert_err:
            print(f"⚠️ Failed to send scheduler alert: {alert_err}")

    def start(self):
        """Start the scheduler and register all jobs"""
        if self._scheduler.running:
            print("Scheduler already running")
            return

        # Register jobs
        self._register_jobs()

        # Start scheduler
        self._scheduler.start()
        print("Scheduler started with jobs:")
        for job in self._scheduler.get_jobs():
            print(f"  - {job.id}: {job.trigger}")

    def shutdown(self):
        """Shutdown the scheduler"""
        if self._scheduler.running:
            self._scheduler.shutdown()
            print("Scheduler shutdown complete")

    def _register_jobs(self):
        """Register all background jobs"""

        # Auto check-in processing - every 15 minutes
        self._scheduler.add_job(
            self._process_auto_checkins,
            trigger=IntervalTrigger(minutes=15),
            id="process_auto_checkins",
            name="Process Auto Check-ins",
            replace_existing=True
        )

        # Price alerts checking - every 6 hours
        self._scheduler.add_job(
            self._check_price_alerts,
            trigger=IntervalTrigger(hours=6),
            id="check_price_alerts",
            name="Check Price Alerts",
            replace_existing=True
        )

        # Refresh visa cache - daily at 3 AM
        self._scheduler.add_job(
            self._refresh_visa_cache,
            trigger=CronTrigger(hour=3),
            id="refresh_visa_cache",
            name="Refresh Visa Cache",
            replace_existing=True
        )

        # Send upcoming trip reminders - daily at 8 AM
        self._scheduler.add_job(
            self._send_trip_reminders,
            trigger=CronTrigger(hour=8),
            id="send_trip_reminders",
            name="Send Trip Reminders",
            replace_existing=True
        )

    async def _check_price_alerts(self):
        """Job: Check active price alerts and notify on price drops"""
        job_id = "check_price_alerts"
        print(f"Running job: {job_id}")

        db = SessionLocal()
        try:
            from app.services.price_alert_service import PriceAlertService, PriceAlert
            from app.services.flight_engine import FlightAggregator
            from app.services.push_notification_service import PushNotificationService

            alert_service = PriceAlertService(db)
            flight_aggregator = FlightAggregator()
            push_service = PushNotificationService()

            # Get alerts that need checking
            alerts = alert_service.get_active_alerts_for_checking()
            print(f"Checking {len(alerts)} price alerts")

            for alert in alerts:
                try:
                    # Search for current price
                    if alert.search_type == "flight":
                        results = await flight_aggregator.search_all_providers(
                            origin=alert.origin,
                            destination=alert.destination,
                            date=alert.departure_date,
                            passengers=1
                        )

                        if results:
                            # Get lowest price
                            new_price = min(float(r.price) for r in results)

                            # Update alert
                            update_result = alert_service.update_price(alert.id, new_price)

                            # Notify if price dropped below target
                            if update_result.get("should_notify") and alert.phone_number:
                                drop_pct = update_result.get("drop_percentage", 0)
                                message = (
                                    f"*Bajo el precio!*\n\n"
                                    f"{alert.origin} → {alert.destination}\n"
                                    f"{alert.departure_date}\n\n"
                                    f"Antes: ${alert.initial_price:.0f}\n"
                                    f"Ahora: ${new_price:.0f}\n"
                                    f"Ahorro: {drop_pct:.0f}%\n\n"
                                    f"Escribe 'buscar vuelo {alert.origin} a {alert.destination}' para reservar"
                                )
                                await push_service.send_message(alert.phone_number, message)

                                # Mark as notified
                                alert.notified_at = datetime.utcnow()
                                alert.notification_count += 1
                                db.commit()

                except Exception as e:
                    print(f"Error checking alert {alert.id}: {e}")

            self._log_job_success(job_id)
            print("Price alerts check complete")

        except Exception as e:
            self._log_job_error(job_id, e)
        finally:
            db.close()

    async def _process_auto_checkins(self):
        """Job: Process pending auto check-ins"""
        job_id = "process_auto_checkins"
        print(f"Running job: {job_id}")

        db = SessionLocal()
        try:
            from app.services.checkin_service import CheckinService
            service = CheckinService(db)
            result = await service.process_pending_checkins()
            self._log_job_success(job_id)
            print(f"Auto check-ins processed: {result}")
        except Exception as e:
            self._log_job_error(job_id, e)
        finally:
            db.close()

    async def _refresh_visa_cache(self):
        """Job: Refresh visa requirements cache using Sherpa API or local map"""
        job_id = "refresh_visa_cache"
        print(f"Running job: {job_id}")

        db = SessionLocal()
        try:
            from app.models.models import VisaRequirement
            from app.services.visa_service import VisaService
            from datetime import datetime, timedelta

            visa_service = VisaService(db)

            # Find stale cache entries (older than 30 days)
            stale_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            stale_entries = db.query(VisaRequirement).filter(
                VisaRequirement.last_updated < stale_date
            ).all()

            print(f"Found {len(stale_entries)} stale visa cache entries to refresh")

            refreshed = 0
            for entry in stale_entries:
                try:
                    # Re-check using the service (tries Sherpa API first, then local map)
                    result = visa_service.check_visa_requirement(
                        passport_country=entry.passport_country,
                        destination=entry.destination_country
                    )
                    if result.get("success"):
                        entry.visa_required = result.get("visa_required", entry.visa_required)
                        entry.visa_on_arrival = result.get("visa_on_arrival", entry.visa_on_arrival)
                        entry.e_visa_available = result.get("e_visa_available", entry.e_visa_available)
                        entry.notes = result.get("notes", entry.notes)
                        entry.last_updated = datetime.utcnow().isoformat()
                        refreshed += 1
                except Exception as entry_err:
                    print(f"Error refreshing visa {entry.passport_country}->{entry.destination_country}: {entry_err}")

            db.commit()
            self._log_job_success(job_id)
            print(f"Visa cache refresh complete: {refreshed}/{len(stale_entries)} updated")

        except Exception as e:
            self._log_job_error(job_id, e)
        finally:
            db.close()

    async def _send_trip_reminders(self):
        """Job: Send reminders for upcoming trips"""
        job_id = "send_trip_reminders"
        print(f"Running job: {job_id}")

        db = SessionLocal()
        try:
            from app.models.models import Trip, Profile, TripStatusEnum
            from app.services.push_notification_service import PushNotificationService
            from datetime import datetime, timedelta

            # Find trips departing in 24-48 hours
            tomorrow = datetime.now().date() + timedelta(days=1)
            day_after = datetime.now().date() + timedelta(days=2)

            upcoming_trips = db.query(Trip).filter(
                Trip.departure_date >= tomorrow,
                Trip.departure_date < day_after,
                Trip.status != TripStatusEnum.CANCELLED
            ).all()

            push_service = PushNotificationService()

            for trip in upcoming_trips:
                profile = db.query(Profile).filter(
                    Profile.user_id == trip.user_id
                ).first()

                if profile and profile.phone_number:
                    await push_service.send_trip_reminder(
                        phone_number=profile.phone_number,
                        trip_pnr=trip.booking_reference,
                        departure_city=trip.departure_city or "tu ciudad",
                        arrival_city=trip.arrival_city or "tu destino",
                        departure_date=trip.departure_date.isoformat() if trip.departure_date else "mañana"
                    )

            self._log_job_success(job_id)
            print(f"Sent {len(upcoming_trips)} trip reminders")

        except Exception as e:
            self._log_job_error(job_id, e)
        finally:
            db.close()

    def run_job_now(self, job_id: str):
        """Manually trigger a job to run immediately"""
        job = self._scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            print(f"Job {job_id} scheduled to run immediately")
        else:
            print(f"Job {job_id} not found")

    def get_jobs_status(self) -> list:
        """Get status of all scheduled jobs"""
        return [{
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger)
        } for job in self._scheduler.get_jobs()]


# Global scheduler instance
scheduler_service = SchedulerService()
