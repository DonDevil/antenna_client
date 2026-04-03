"""
HealthMonitor - Periodic health checking for server and CST

Responsible for:
- Checking server and CST availability at startup
- Periodic health checks every 30 seconds
- Updating status when connectivity changes
- Handling disconnections gracefully
"""

import asyncio
from PySide6.QtCore import QThread, Signal, QTimer
from utils.connection_checker import ConnectionChecker
from utils.logger import get_logger


logger = get_logger(__name__)


class HealthMonitorWorker(QThread):
    """Worker thread for periodic health checks"""
    
    # Signal emitted when health check completes
    health_updated = Signal(dict)  # Emits result dict
    
    def __init__(self, interval_sec: int = 30):
        super().__init__()
        self.interval_sec = interval_sec
        self.running = True
    
    def run(self):
        """Run periodic health checks"""
        logger.info(f"Health monitor started (interval: {self.interval_sec}s)")
        
        while self.running:
            try:
                # Run async check_all() in new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ConnectionChecker.check_all())
                    self.health_updated.emit(result)
                    logger.debug(f"Health check completed: {list(result.keys())}")
                finally:
                    loop.close()  # Properly close event loop
            except Exception as e:
                logger.error(f"Health monitor error: {type(e).__name__} - {str(e)}")
                self.health_updated.emit({"error": str(e)})
            
            # Sleep but check if we should stop (allows graceful shutdown)
            for _ in range(self.interval_sec * 10):  # Check 10x per second
                if not self.running:
                    break
                self.msleep(100)  # Sleep 100ms at a time
    
    def stop(self):
        """Stop the health monitor"""
        self.running = False
        logger.info("Health monitor stopped")


class HealthMonitor:
    """Manages periodic health checking"""
    
    def __init__(self, status_bar, check_interval_sec: int = 30):
        """Initialize health monitor
        
        Args:
            status_bar: Reference to AppStatusBar
            check_interval_sec: Interval between health checks in seconds
        """
        self.status_bar = status_bar
        self.check_interval_sec = check_interval_sec
        self.worker = None
        self.last_status = {"server": (False, "Unknown"), "cst": (False, "Unknown")}
        
        logger.info(f"HealthMonitor initialized (interval: {check_interval_sec}s)")
    
    def start(self):
        """Start periodic health monitoring"""
        logger.info("Starting health monitor...")
        
        # Create and start worker thread
        self.worker = HealthMonitorWorker(self.check_interval_sec)
        self.worker.health_updated.connect(self.on_health_updated)
        self.worker.start()
        
        logger.info("Health monitor started")
    
    def stop(self):
        """Stop health monitoring"""
        if self.worker:
            self.worker.stop()
            self.worker.wait()  # Wait for thread to finish
            logger.info("Health monitor stopped")
    
    def on_health_updated(self, result: dict):
        """Handle health check result
        
        Args:
            result: Dict with connection status
        """
        if "error" in result:
            logger.warning(f"Health check error: {result['error']}")
            return
        
        # Extract results
        server_ok, server_msg = result.get("server", (False, "Unknown"))
        cst_ok, cst_msg = result.get("cst", (False, "Unknown"))
        
        # Store current status
        current_status = {
            "server": (server_ok, server_msg),
            "cst": (cst_ok, cst_msg)
        }
        
        # Check if status changed
        status_changed = current_status != self.last_status
        
        if status_changed:
            logger.info(
                f"Health status changed - Server: {server_ok}, CST: {cst_ok}"
            )
        
        # Update status bar
        self.status_bar.set_server_connected(server_ok)
        self.status_bar.set_cst_available(cst_ok)
        
        # Update last known status
        self.last_status = current_status
        
        # Log connection loss if detected
        if status_changed:
            if not server_ok and self.last_status.get("server", (False,))[0]:
                logger.warning("🔴 Server connection LOST")
            elif server_ok and not self.last_status.get("server", (False,))[0]:
                logger.info("🟢 Server connection RESTORED")
            
            if not cst_ok and self.last_status.get("cst", (False,))[0]:
                logger.warning("🔴 CST connection LOST")
            elif cst_ok and not self.last_status.get("cst", (False,))[0]:
                logger.info("🟢 CST connection RESTORED")
