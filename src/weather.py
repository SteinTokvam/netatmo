# https://api.met.no/weatherapi/locationforecast/2.0/compact?altitude=353&lat=xx.xx&lon=yy.yy

import time
import os
import logging
import threading
import requests
import utils

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)  # Parent directory (project root)

CONFIG_DIR = os.path.join(BASE_DIR, "config")
DATA_DIR = os.path.join(BASE_DIR, "data")

weatherLogger = logging.getLogger(__name__)
weatherLogger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')


class WeatherServiceMetNo:
    """Service for fetching weather data from met.no API."""
    
    def __init__(self, config_filename=None, weather_data_filename=None):
        """Initialize the weather service.
        
        Args:
            config_filename: Path to config JSON file
            weather_data_filename: Path to output weather data JSON file
        """
        self.config_filename = config_filename or os.path.join(CONFIG_DIR, "config.json")
        self.weather_data_filename = weather_data_filename or os.path.join(DATA_DIR, "weather_data.json")
        self.config = utils.read_json(self.config_filename)
        self.stop_event = threading.Event()
        self.thread = None
    
    def get_weather_data(self):
        """Gets weather data from met.no API. Result: weather_data.json file."""
                
        params = {
            'altitude': self.config['location']['altitude'],
            'lat': round(self.config['location']['latitude'], 4), # Use 4 decimal places for lat/lon - see https://api.met.no/doc/TermsOfService 
            'lon': round(self.config['location']['longitude'], 4)
        }

        try:
            response = requests.get(
                "https://api.met.no/weatherapi/locationforecast/2.0/complete",
                params=params,
                headers={"User-Agent": "wgmv-weather/1.0"},
                timeout=30
            )
            
            weatherLogger.debug("%d %s", response.status_code, response.text)
            response.raise_for_status()
            weather_data = response.json()
            utils.write_json(weather_data, self.weather_data_filename)
        except requests.exceptions.HTTPError as e:
            weatherLogger.warning("get_weather_data() HTTPError")
            weatherLogger.warning("%d %s", e.response.status_code, e.response.text)
        except requests.exceptions.RequestException:
            weatherLogger.error("get_weather_data() RequestException:", exc_info=1)
        
    def start(self):
        """Starts periodic weather data retrieval in a background thread."""
        if self.thread is not None and self.thread.is_alive():
            weatherLogger.warning("Weather service is already running")
            return
        
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        weatherLogger.info("Weather service started in background")
    
    def stop(self):
        """Stops the weather data retrieval service."""
        if self.thread is None or not self.thread.is_alive():
            return
        
        weatherLogger.info("Stopping weather service...")
        self.stop_event.set()
        self.thread.join(timeout=5)
        weatherLogger.info("Weather service stopped")
    
    def _run(self):
        """Internal method that runs in the background thread."""
        while not self.stop_event.is_set():
            try:
                weatherLogger.info("Fetching new weather data.")
                self.get_weather_data()
            except Exception as e:
                weatherLogger.error("Error in weather service: %s", e, exc_info=True)
            
            # Sleep in small chunks so stop is responsive
            for _ in range(60 * 60):  # 60 minutes in seconds
                if self.stop_event.is_set():
                    break
                time.sleep(1)

if __name__ == '__main__':
    service = WeatherServiceMetNo()
    service.start()