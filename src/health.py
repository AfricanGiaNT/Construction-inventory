"""Health check endpoints for monitoring the bot status."""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class HealthChecker:
    """Health check service for monitoring bot status."""
    
    def __init__(self, bot_instance):
        """Initialize health checker with bot instance."""
        self.bot = bot_instance
        self.start_time = datetime.now()
    
    async def check_health(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        try:
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "uptime": str(datetime.now() - self.start_time),
                "services": {}
            }
            
            # Check bot status
            try:
                bot_info = await self.bot.get_me()
                health_status["services"]["telegram_bot"] = {
                    "status": "healthy",
                    "username": bot_info.username,
                    "id": bot_info.id
                }
            except Exception as e:
                logger.error(f"Telegram bot health check failed: {e}")
                health_status["services"]["telegram_bot"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
            
            # Check Airtable connection
            try:
                # Simple test query to verify connection
                test_result = await self.bot.airtable_client.test_connection()
                health_status["services"]["airtable"] = {
                    "status": "healthy" if test_result else "unhealthy",
                    "connected": test_result
                }
                if not test_result:
                    health_status["status"] = "degraded"
            except Exception as e:
                logger.error(f"Airtable health check failed: {e}")
                health_status["services"]["airtable"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
            
            # Check scheduler status
            try:
                scheduler_running = self.bot.scheduler.running
                health_status["services"]["scheduler"] = {
                    "status": "healthy" if scheduler_running else "unhealthy",
                    "running": scheduler_running,
                    "jobs_count": len(self.bot.scheduler.get_jobs())
                }
                if not scheduler_running:
                    health_status["status"] = "degraded"
            except Exception as e:
                logger.error(f"Scheduler health check failed: {e}")
                health_status["services"]["scheduler"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
                health_status["status"] = "degraded"
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    def get_simple_status(self) -> str:
        """Get simple status string for basic monitoring."""
        try:
            uptime = datetime.now() - self.start_time
            return f"Bot running for {uptime}"
        except Exception:
            return "Status unknown"


# Global health checker instance
health_checker = None


def init_health_checker(bot_instance):
    """Initialize the global health checker."""
    global health_checker
    health_checker = HealthChecker(bot_instance)


def get_health_checker():
    """Get the global health checker instance."""
    return health_checker
