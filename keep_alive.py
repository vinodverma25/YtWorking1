
import requests
import time
import threading
import logging
import os
from datetime import datetime

class KeepAlive:
    def __init__(self, app_url=None, interval=300):  # 5 minutes default
        self.logger = logging.getLogger(__name__)
        self.app_url = app_url or self._get_app_url()
        self.interval = interval
        self.running = False
        self.thread = None
        
    def _get_app_url(self):
        """Get the app URL from environment variables"""
        # Try to get from Replit domain
        replit_domain = os.environ.get("REPLIT_DEV_DOMAIN")
        if replit_domain:
            return f"https://{replit_domain}"
        
        # Try to get from Render domain
        render_domain = os.environ.get("RENDER_EXTERNAL_URL")
        if render_domain:
            return render_domain
            
        # Default fallback
        return "http://localhost:5000"
    
    def start(self):
        """Start the keep-alive service"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
            self.thread.start()
            self.logger.info(f"Keep-alive service started for {self.app_url}")
    
    def stop(self):
        """Stop the keep-alive service"""
        self.running = False
        if self.thread:
            self.thread.join()
        self.logger.info("Keep-alive service stopped")
    
    def _keep_alive_loop(self):
        """Main keep-alive loop"""
        while self.running:
            try:
                # Make a simple GET request to keep the app alive
                response = requests.get(
                    self.app_url,
                    timeout=30,
                    headers={'User-Agent': 'KeepAlive/1.0'}
                )
                
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                if response.status_code == 200:
                    self.logger.info(f"Keep-alive ping successful at {current_time}")
                else:
                    self.logger.warning(f"Keep-alive ping returned status {response.status_code} at {current_time}")
                    
            except requests.exceptions.RequestException as e:
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.logger.error(f"Keep-alive ping failed at {current_time}: {e}")
            
            # Wait for the specified interval
            time.sleep(self.interval)
    
    def ping_now(self):
        """Manually trigger a keep-alive ping"""
        try:
            response = requests.get(
                self.app_url,
                timeout=30,
                headers={'User-Agent': 'KeepAlive/1.0'}
            )
            return response.status_code == 200
        except:
            return False

# Global keep-alive instance
keep_alive_service = KeepAlive()
