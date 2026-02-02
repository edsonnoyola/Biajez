"""
Scheduler Service - APScheduler setup for background jobs
"""
import os
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

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._scheduler = AsyncIOScheduler()
        return cls._instance

    @property
    def scheduler(self) -> AsyncIOScheduler:
        return self._scheduler

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

    async def _process_auto_checkins(self):
        """Job: Process pending auto check-ins"""
        print("Running job: process_auto_checkins")

        db = SessionLocal()
        try:
            from app.services.checkin_service import CheckinService
            service = CheckinService(db)
            result = await service.process_pending_checkins()
            print(f"Auto check-ins processed: {result}")
        except Exception as e:
            print(f"Error in process_auto_checkins job: {e}")
        finally:
            db.close()

    async def _refresh_visa_cache(self):
        """Job: Refresh visa requirements cache"""
        print("Running job: refresh_visa_cache")

        db = SessionLocal()
        try:
            from app.models.models import VisaRequirement
            from datetime import datetime, timedelta

            # Find stale cache entries (older than 30 days)
            stale_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            stale_entries = db.query(VisaRequirement).filter(
                VisaRequirement.last_updated < stale_date
            ).all()

            print(f"Found {len(stale_entries)} stale visa cache entries to refresh")

            # In production, you would re-fetch from the API
            # For now, just update the timestamp
            for entry in stale_entries:
                entry.last_updated = datetime.utcnow().isoformat()

            db.commit()
            print("Visa cache refresh complete")

        except Exception as e:
            print(f"Error in refresh_visa_cache job: {e}")
        finally:
            db.close()

    async def _send_trip_reminders(self):
        """Job: Send reminders for upcoming trips"""
        print("Running job: send_trip_reminders")

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
                        departure_city=trip.departure_city or "your departure city",
                        arrival_city=trip.arrival_city or "your destination",
                        departure_date=trip.departure_date.isoformat() if trip.departure_date else "tomorrow"
                    )

            print(f"Sent {len(upcoming_trips)} trip reminders")

        except Exception as e:
            print(f"Error in send_trip_reminders job: {e}")
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
