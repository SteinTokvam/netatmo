# https://api.met.no/weatherapi/locationforecast/2.0/compact?altitude=353&lat=60.70833400000004&lon=10.611503000000067
import requests
import utils
import logging
import time
import logging

weatherLogger = logging.getLogger(__name__)

weather_data_filename = "data/weather_data.json"

def get_weather_data():
    """Gets weather data from met.no API. Result: weather_data.json file."""
    
    global weather_data_filename

    params = {
        'altitude': '353',
        'lat': '60.70833400000004',
        'lon': '10.611503000000067'
    }
    try:
        response = requests.get("https://api.met.no/weatherapi/locationforecast/2.0/complete", params=params, headers={"User-Agent": "netatmo-weather-app/1.0"})
        weatherLogger.debug("%d %s", response.status_code, response.text)
        response.raise_for_status()
        weather_data = response.json()
        utils.write_json(weather_data, weather_data_filename)    
    except requests.exceptions.HTTPError as e:
        weatherLogger.warning("get_weather_data() HTTPError")
        weatherLogger.warning("%d %s", e.response.status_code, e.response.text)
    except requests.exceptions.RequestException:
        weatherLogger.error("get_weather_data() RequestException:", exc_info=1)

def startWeatherService():
    """Starts periodic weather data retrieval."""
    while True:
        weatherLogger.info("Fetching new weather data.")
        get_weather_data()
        time.sleep(60*60)  # Sleep for 60 min

if __name__ == '__main__':
    startWeatherService()