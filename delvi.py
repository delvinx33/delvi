"""
Stream Automation Bot

A professional automation tool for monitoring and interacting with live streams.
Handles browser automation, geolocation spoofing, and user interaction simulation.
"""

import base64
import logging
import random
import time
from typing import Tuple, Optional
from dataclasses import dataclass

import requests
from seleniumbase import SB


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class GeoLocation:
    """Geolocation data from IP-based lookup."""
    latitude: float
    longitude: float
    timezone: str
    language_code: str

    @classmethod
    def from_ip_lookup(cls) -> 'GeoLocation':
        """Fetch geolocation data from IP API."""
        try:
            response = requests.get("http://ip-api.com/json/", timeout=10)
            response.raise_for_status()
            geo_data = response.json()
            
            return cls(
                latitude=geo_data["lat"],
                longitude=geo_data["lon"],
                timezone=geo_data["timezone"],
                language_code=geo_data["countryCode"].lower()
            )
        except requests.RequestException as e:
            logger.error(f"Proxy request failed: {e}")
            raise


@dataclass
class StreamConfig:
    """Configuration for stream automation."""
    channel_name: str
    proxy_str: bool = False
    locale: str = "en"
    min_watch_time: int = 450
    max_watch_time: int = 800


class StreamAutomationBot:
    """Handles automated stream viewing and interaction."""
    
    INITIAL_WAIT = 2
    STREAM_WAIT = 12
    ACTION_WAIT = 10
    TIMEOUT = 4
    
    def __init__(self, config: StreamConfig, geo_location: GeoLocation):
        """
        Initialize the automation bot.
        
        Args:
            config: Stream automation configuration
            geo_location: Geolocation data for the session
        """
        self.config = config
        self.geo_location = geo_location
        self.stream_url = self._build_stream_url()
        
    def _build_stream_url(self) -> str:
        """Build the stream URL from the channel name."""
        decoded_name = base64.b64decode(self.config.channel_name).decode("utf-8")
        return f"https://www.twitch.tv/{decoded_name}"
    
    def _accept_cookie_consent(self, driver: SB) -> None:
        """Accept cookie/terms consent if present."""
        try:
            if driver.is_element_present('button:contains("Accept")'):
                driver.cdp.click('button:contains("Accept")', timeout=self.TIMEOUT)
                logger.info("Cookie consent accepted")
        except Exception as e:
            logger.warning(f"Failed to handle consent: {e}")
    
    def _click_start_watching(self, driver: SB) -> bool:
        """
        Click the 'Start Watching' button if present.
        
        Returns:
            True if button was clicked, False otherwise
        """
        try:
            if driver.is_element_present('button:contains("Start Watching")'):
                driver.cdp.click('button:contains("Start Watching")', timeout=self.TIMEOUT)
                logger.info("Started watching")
                return True
        except Exception as e:
            logger.warning(f"Failed to click 'Start Watching': {e}")
        return False
    
    def _initialize_stream(self, driver: SB) -> None:
        """
        Initialize stream view with consent handling.
        
        Args:
            driver: SeleniumBase driver instance
        """
        driver.sleep(self.INITIAL_WAIT)
        self._accept_cookie_consent(driver)
        driver.sleep(self.INITIAL_WAIT)
    
    def _is_stream_live(self, driver: SB) -> bool:
        """
        Check if stream is currently live.
        
        Returns:
            True if live stream element is present
        """
        return driver.is_element_present("#live-channel-stream-information")
    
    def _watch_with_secondary_driver(self, primary_driver: SB) -> None:
        """
        Launch and manage secondary driver for concurrent viewing.
        
        Args:
            primary_driver: Primary SeleniumBase driver instance
        """
        try:
            logger.info("Initializing secondary driver")
            driver2 = primary_driver.get_new_driver(undetectable=True)
            driver2.activate_cdp_mode(
                self.stream_url,
                tzone=self.geo_location.timezone,
                geoloc=(self.geo_location.latitude, self.geo_location.longitude)
            )
            
            driver2.sleep(self.ACTION_WAIT)
            self._click_start_watching(driver2)
            driver2.sleep(self.ACTION_WAIT)
            self._accept_cookie_consent(driver2)
            
            logger.info("Secondary driver session initialized")
            
        except Exception as e:
            logger.error(f"Secondary driver error: {e}", exc_info=True)
    
    def _run_watch_session(self, driver: SB) -> bool:
        """
        Run a single stream watching session.
        
        Args:
            driver: SeleniumBase driver instance
            
        Returns:
            True if stream was live and session completed, False if stream ended
        """
        try:
            rnd = random.randint(self.config.min_watch_time, self.config.max_watch_time)
            
            driver.activate_cdp_mode(
                self.stream_url,
                tzone=self.geo_location.timezone,
                geoloc=(self.geo_location.latitude, self.geo_location.longitude)
            )
            
            self._initialize_stream(driver)
            driver.sleep(self.STREAM_WAIT)
            self._click_start_watching(driver)
            driver.sleep(self.ACTION_WAIT)
            self._accept_cookie_consent(driver)
            
            if self._is_stream_live(driver):
                logger.info("Stream is live, starting watch session")
                self._accept_cookie_consent(driver)
                self._watch_with_secondary_driver(driver)
                driver.sleep(rnd)
                logger.info(f"Watch session completed: {rnd} seconds")
                return True
            else:
                logger.info("Stream is not live, ending session")
                return False
                
        except Exception as e:
            logger.error(f"Error during watch session: {e}", exc_info=True)
            raise
    
    def run_automation_loop(self) -> None:
        """
        Main automation loop for continuous stream monitoring.
        Runs indefinitely until stream is no longer live.
        """
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.info(f"Starting iteration {iteration}")
                
                with SB(
                    uc=True,
                    locale=self.config.locale,
                    ad_block=True,
                    chromium_arg='--disable-webgl',
                    proxy=self.config.proxy_str
                ) as driver:
                    try:
                        stream_live = self._run_watch_session(driver)
                        if not stream_live:
                            logger.info("Stream is no longer live, stopping automation")
                            break
                        
                    except Exception as e:
                        logger.error(f"Session error in iteration {iteration}: {e}")
                        break
                
                logger.info(f"Iteration {iteration} completed successfully")
                
        except KeyboardInterrupt:
            logger.info("Automation loop interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in automation loop: {e}", exc_info=True)


def main():
    """Main entry point for the stream automation bot."""
    try:
        # Fetch geolocation
        logger.info("Fetching geolocation data...")
        geo_location = GeoLocation.from_ip_lookup()
        logger.info(f"Geolocation: {geo_location.timezone} ({geo_location.language_code})")
        
        # Configure stream automation
        config = StreamConfig(
            channel_name="YnJ1dGFsbGVz",  # base64 encoded channel name
            proxy_str=False,
            locale="en"
        )
        
        # Initialize and run bot
        bot = StreamAutomationBot(config, geo_location)
        logger.info(f"Starting automation for: {bot.stream_url}")
        bot.run_automation_loop()
        
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
