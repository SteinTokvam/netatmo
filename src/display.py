#!/usr/bin/env python3
"""display.py
Displays NetAtmo weather station data on a local screen
input: data.json file, result of NetAtmo getstationsdata API
screen: Waveshare ePaper / eInk Screen HAT for Raspberry Pi
output: copy of the screen in file: image.bmp

Usage Examples:

# Basic usage with defaults (file-only mode):
display = WeatherDisplay()
display.generate()

# With Waveshare 2.7" e-paper display:
display = WeatherDisplay(screen_type='epd2in7')
display.generate()

# With Waveshare 5.83" e-paper display:
display = WeatherDisplay(screen_type='epd5in83')
display.generate()

# Custom configuration:
display = WeatherDisplay(
    data_filename='custom/data.json',
    weather_data_filename='custom/weather.json',
    image_filename='my_display.bmp',
    symbols_dir='custom_symbols',
    image_width=1200,
    image_height=600,
    screen_type='epd5in83'
)
display.generate()

# Configure via config.json by adding "screen_type" field:
# {
#   "client_id": "...",
#   "screen_type": "epd2in7"  // Options: "epd2in7", "epd5in83", or null
# }

# Supported screen_type values:
# - None or null: File-only mode (default)
# - 'epd2in7': Waveshare 2.7" e-paper HAT
# - 'epd5in83': Waveshare 5.83" e-paper HAT
"""

import os
import logging
import sys
import importlib
from datetime import datetime, timedelta

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import utils

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)  # Parent directory (project root)

# Constants
WHITE = 1
BLACK = 0
RED = 2

DEFAULT_FONT_FILE = os.path.join(BASE_DIR, 'assets', 'fonts', 'free-sans.ttf')

DEFAULT_DATA_FILENAME = os.path.join(BASE_DIR, 'data', 'data.json')
DEFAULT_WEATHER_DATA_FILENAME = os.path.join(BASE_DIR, 'data', 'weather_data.json')
DEFAULT_IMAGE_FILENAME = os.path.join(BASE_DIR, 'image.bmp')
DEFAULT_SYMBOLS_DIR = os.path.join(BASE_DIR, 'assets', 'symbols')

DEFAULT_IMAGE_WIDTH = 960
DEFAULT_IMAGE_HEIGHT = 540

FONT_SIZE_TEXT = 25
FONT_SIZE_TEMP = 50
FONT_SIZE_TIME = 15

TREND_SYMBOLS = {
    'up': '\u2197',     # ↗
    'down': '\u2198',   # ↘
    'stable': '\u2192'  # →
}

WEATHER_SYMBOL_SIZE = (100, 100)

# Unit options based on Netatmo API settings
UNIT_OPTIONS = {
    'temperature': ['°C', '°F'],
    'rain': ['mm/h', 'in/h'],
    'wind': ['kph', 'mph', 'm/s', 'beaufort', 'knot'],
    'pressure': ['mbar', 'inHg', 'mmHg']
}

displayLogger = logging.getLogger(__name__)


class WeatherDisplay:
    """Class to handle weather display rendering"""
    
    def __init__(self, 
                 data_filename=DEFAULT_DATA_FILENAME,
                 weather_data_filename=DEFAULT_WEATHER_DATA_FILENAME,
                 image_filename=DEFAULT_IMAGE_FILENAME,
                 symbols_dir=DEFAULT_SYMBOLS_DIR,
                 image_width=DEFAULT_IMAGE_WIDTH,
                 image_height=DEFAULT_IMAGE_HEIGHT,
                 screen_type=None):
        """Initialize the WeatherDisplay
        
        Args:
            data_filename: Path to netatmo data JSON file
            weather_data_filename: Path to weather forecast JSON file
            image_filename: Output image filename
            symbols_dir: Directory containing weather symbol images
            image_width: Width of output image in pixels
            image_height: Height of output image in pixels
            screen_type: Screen type ('epd2in7', 'epd5in83', None for file only)
        """
        self.data_filename = data_filename
        self.weather_data_filename = weather_data_filename
        self.image_filename = image_filename
        self.symbols_dir = symbols_dir
        self.image_width = image_width
        self.image_height = image_height
        self.screen_type = screen_type
        self.epd = None
        self.units = {}  # Will be populated when data is loaded

        #Check/create symbols directory
        if not os.path.isfile(data_filename):
            displayLogger.error("No data file found: %s", data_filename)
            exit(1)

        if not os.path.isfile(weather_data_filename):
            displayLogger.error("No forecast data file found: %s", weather_data_filename)
            exit(1)

        if not os.path.isfile(DEFAULT_FONT_FILE):
            displayLogger.error("No font file found: %s", DEFAULT_FONT_FILE)
            exit(1)
        
        # Data storage
        self.data = {}
        self.weather_data = {}
        self.image = None

    def _load_data(self):
        """Load data from JSON files
        
        Returns:
            bool: True if data loaded successfully
        """
        # Read netatmo data
        if os.path.isfile(self.data_filename):
            self.data = utils.read_json(self.data_filename)
        else:
            displayLogger.error("No data file")
            return False
        
        if "body" not in self.data:
            displayLogger.error("Bad data format")
            return False
        
        # Read weather data
        if os.path.isfile(self.weather_data_filename):
            self.weather_data = utils.read_json(self.weather_data_filename)
        else:
            displayLogger.error("No weather data file")
            return False
        
        if "properties" not in self.weather_data:
            displayLogger.error("Bad weather data format")
            return False
        
        return True
    
    def _get_units(self):
        """Extract units from user settings.
        
        Returns:
            dict: Dictionary with unit strings for different measurements
        """
        user_admin = self.data["body"]["user"]["administrative"]
        
        return {
            'temp': UNIT_OPTIONS['temperature'][user_admin["unit"]],
            'rain': UNIT_OPTIONS['rain'][user_admin["unit"]],
            'wind': UNIT_OPTIONS['wind'][user_admin["windunit"]],
            'pressure': UNIT_OPTIONS['pressure'][user_admin.get("pressureunit", 0)],
            'humidity': '%',
            'co2': 'ppm'
        }
    
    def draw_image(self):
        """Draw the weather display image"""
        # Load data
        if not self._load_data():
            return
        
        # Prepare for drawing
        draw = ImageDraw.Draw(self.image)
        width, height = self.image.size

        # Load fonts
        font_text = ImageFont.truetype(DEFAULT_FONT_FILE, FONT_SIZE_TEXT)
        font_temp = ImageFont.truetype(DEFAULT_FONT_FILE, FONT_SIZE_TEMP)
        font_time = ImageFont.truetype(DEFAULT_FONT_FILE, FONT_SIZE_TIME)

        # Get units from user settings
        self.units = self._get_units()

        # Battery percentage
        battery = self.data['body']['devices'][0]['modules'][0]['battery_percent']
        battery_percent = f'Bateria: {battery} |'

        # Extract and format sensor values
        indoor_temp_str, indoor_humidity_str, indoor_co2_str = self._get_indoor_data()
        outdoor_temp_str, outdoor_humidity_str, rain_str, wind_str = self._get_outdoor_data()
        
        data_time_str = f"Aktualizowano  : {utils.timestr(self.data['time_server'])}"
        
        # Get weather forecast data
        forecast_data = self._get_forecast_data()

        # Calculate text dimensions
        (width_indoor, height_indoor) = utils.textsize(indoor_temp_str, font=font_temp)
        (width_outdoor, height_outdoor) = utils.textsize(outdoor_temp_str, font=font_temp)
        (width_rain, height_rain) = utils.textsize(rain_str, font=font_temp)
        (width_time, height_time) = utils.textsize(data_time_str, font=font_time)
        (width_battery, height_battery) = utils.textsize(battery_percent, font=font_time)

        # Maximum text width
        txtwidth = max(width_indoor, width_outdoor, width_rain)
        txtheight = height_indoor

        # Calculate window positions
        left_x = width // 8
        right_x = width // 2 + width // 6
        top_y = height // 8
        bottom_x = 10
        bottom_y = height // 2 + 150

        # Draw layout structure
        self._draw_layout(draw, width, height)

        # Draw temperatures
        draw.text((left_x, top_y), indoor_temp_str, fill=BLACK, font=font_temp)
        draw.text((right_x, top_y), outdoor_temp_str, fill=BLACK, font=font_temp)

        # Draw indoor humidity and CO2
        draw.text((right_x, top_y + (4 * txtheight)), 
                  f"{indoor_humidity_str} / {indoor_co2_str}", fill=BLACK, font=font_text)

        # Draw time and battery
        draw.text((width - width_time - 5, 5), data_time_str, fill=BLACK, font=font_time)
        draw.text((width - width_time - width_battery - 10, 5), battery_percent, fill=BLACK, font=font_time)

        # Draw weather forecast
        if forecast_data:
            self._draw_forecast(forecast_data, bottom_x, bottom_y, width, font_text)
    
    def _get_indoor_data(self):
        """Extract indoor sensor data
        
        Returns:
            tuple: (temperature_str, humidity_str, co2_str)
        """
        indoor_temp_str = 'N/A'
        indoor_humidity_str = 'N/A'
        indoor_co2_str = 'N/A'
        
        device = self.data["body"]["devices"][0]
        if "dashboard_data" in device:
            data = device["dashboard_data"]
            temp = data["Temperature"]
            humidity = data["Humidity"]
            co2 = data["CO2"]
            
            indoor_temp_str = f"{temp:.1f} {self.units['temp']}"
            if "temp_trend" in data:
                indoor_temp_str += TREND_SYMBOLS.get(data["temp_trend"], '')
            
            indoor_humidity_str = f"{humidity:.1f} {self.units['humidity']}"
            
            indoor_co2_str = f"{co2:.1f} {self.units['co2']}"
            if "pressure_trend" in data:
                indoor_co2_str += TREND_SYMBOLS.get(data["pressure_trend"], '')
        
        return indoor_temp_str, indoor_humidity_str, indoor_co2_str
    
    def _get_outdoor_data(self):
        """Extract outdoor sensor data
        
        Returns:
            tuple: (temperature_str, humidity_str, rain_str, wind_str)
        """
        outdoor_temp_str = 'N/A'
        outdoor_humidity_str = 'N/A'
        rain_str = 'N/A'
        wind_str = 'N/A'
        
        device = self.data["body"]["devices"][0]
        for module in device["modules"]:
            if "dashboard_data" not in module:
                continue
                
            module_type = module["type"]
            data = module["dashboard_data"]
            
            if module_type == "NAModule1":  # Outdoor Module
                temp = data["Temperature"]
                humidity = data["Humidity"]
                outdoor_temp_str = f"{temp:.1f} {self.units['temp']}"
                if "temp_trend" in data:
                    outdoor_temp_str += TREND_SYMBOLS.get(data["temp_trend"], '')
                outdoor_humidity_str = f"{humidity:.1f} {self.units['humidity']}"
                
            elif module_type == "NAModule2":  # Wind Gauge
                wind = data.get("WindStrength", 0)
                wind_str = f"{wind:.1f} {self.units['wind']}"
                
            elif module_type == "NAModule3":  # Rain Gauge
                rain = data.get("sum_rain_24", 0)
                rain_str = f"{rain:.1f} mm"
        
        return outdoor_temp_str, outdoor_humidity_str, rain_str, wind_str
    
    def _get_forecast_data(self):
        """Extract weather forecast data from instant section for each hour.
        
        Returns:
            list: List of forecast dictionaries with hourly temperature and 6-hour symbols
        """
        if "properties" not in self.weather_data:
            return None
        
        timeseries = self.weather_data["properties"]["timeseries"]
        if len(timeseries) < 10:
            return None
        
        forecast_data = []
        
       
        for index in range(0,24):
            if index >= len(timeseries):
                continue
                
            forecast = timeseries[index]
            
            # Get temperature from instant section (current hour)
            instant_details = forecast["data"]["instant"]["details"]
            temp = instant_details.get("air_temperature", 0)
            
            # Get weather symbol from 3-hour forecast if available, fallback to 1-hour
            symbol_code = None
            if "next_3_hours" in forecast["data"]:
                symbol_code = forecast["data"]["next_3_hours"]["summary"]["symbol_code"]
            elif "next_1_hours" in forecast["data"]:
                symbol_code = forecast["data"]["next_1_hours"]["summary"]["symbol_code"]
            
            if symbol_code:
                # Convert UTC time to local timezone
                forecast_time = datetime.fromisoformat(forecast["time"].replace('Z', '+00:00'))
                local_time = forecast_time.astimezone()
                
                forecast_data.append({
                    'time': local_time.isoformat(),
                    'symbol_code': symbol_code,
                    'temp': temp
                })
        print(forecast_data)
        return forecast_data
    
    def _draw_layout(self, draw, width, height):
        """Draw the basic layout structure
        
        Args:
            draw: ImageDraw object
            width: Image width
            height: Image height
        """
        # Outer rectangle
        draw.rectangle((2, 2, width - 2, height - 2), fill=WHITE, outline=BLACK)
        
        # Main dividing lines
        mid_x = width // 2
        mid_y = height // 2
        draw.line((mid_x, 2, mid_x, mid_y), fill=BLACK, width=2)
        draw.line((2, mid_y, width - 2, mid_y), fill=BLACK, width=2)

        # Bottom window divisions (5 equal sections)
        for i in range(1, 5):
            x = i * width // 4
            draw.line((x, mid_y, x, height - 2), fill=BLACK, width=2)
    
    def _draw_forecast(self, forecast_data, bottom_window_x, bottom_window_y, width, font_text):
        """Draw weather forecast section
        
        Args:
            forecast_data: List of forecast dictionaries
            bottom_window_x: X position of bottom window
            bottom_window_y: Y position of bottom window
            width: Image width
            font_text: Font for text
        """
        draw = ImageDraw.Draw(self.image)
        
        for i, forecast in enumerate(forecast_data):
            # Load and resize weather symbol
            symbol_file = f"{forecast['symbol_code']}.png"
            symbol_path = os.path.join(self.symbols_dir, symbol_file)
            
            if os.path.isfile(symbol_path):
                symbol = Image.open(symbol_path).resize(WEATHER_SYMBOL_SIZE)
                x_symbol = 60 + i * 240
                self.image.paste(symbol, (x_symbol, 300), mask=symbol)
            
            # Draw time and temperature
            x_text = bottom_window_x + i * (width // 4)
            time_str = utils.format_time_str(forecast['time'])
            draw.text((x_text, bottom_window_y), time_str, fill=BLACK, font=font_text)
            
            temp = forecast['temp']
            temp_str = f"{temp:.1f}{self.units['temp']}"
            draw.text((x_text, bottom_window_y + 30), temp_str, fill=BLACK, font=font_text)
    
    
    def _init_screen(self):
        """Initialize the e-paper display based on screen_type
        
        Returns:
            tuple: (width, height) for the screen, or None if file-only mode
        """
        if self.screen_type is None:
            return None
        
        try:
            libdir = os.path.realpath(os.getenv('HOME', '.') + '/e-Paper/RaspberryPi_JetsonNano/python/lib')
            if libdir not in sys.path:
                sys.path.append(libdir)
            
            # Import the module dynamically based on screen_type
            module = importlib.import_module(f'waveshare_epd.{self.screen_type}')
            epd = module.EPD()
            epd.init()
            self.epd = epd
            return (epd.height, epd.width)
        
        except Exception as e:
            displayLogger.error(f"Failed to initialize {self.screen_type}: {e}", exc_info=True)
            return None
    
    def _display_on_screen(self):
        """Display the image on the physical e-paper screen"""
        if self.epd is None:
            return
        
        try:
            # All waveshare displays use the same method
            self.epd.display(self.epd.getbuffer(self.image))
            self.epd.sleep()
            
            displayLogger.info(f"Image displayed on {self.screen_type}")
        
        except Exception as e:
            displayLogger.error(f"Failed to display on {self.screen_type}: {e}", exc_info=True)
    
    def generate(self):
        """Generate the complete weather display image
        
        This is the main method to create and save the display
        """
        # Initialize screen if specified
        screen_size = self._init_screen()
        if screen_size:
            self.image_width, self.image_height = screen_size
            displayLogger.info(f"Using screen {self.screen_type} with size {screen_size}")
        
        # Create blank image
        self.image = Image.new('1', (self.image_width, self.image_height), WHITE)
        
        # Draw the weather data
        self.draw_image()
        
        # Save the result
        self.image.save(self.image_filename)
        displayLogger.info("Image saved to %s", self.image_filename)
        
        # Display on physical screen if available
        if self.epd is not None:
            self._display_on_screen()


def main():
    """Main function"""
    # Try to read screen_type from config
    config_file = os.path.join(BASE_DIR, 'config', 'config.json')
    screen_type = None
    
    if os.path.isfile(config_file):
        try:
            config = utils.read_json(config_file)
            screen_type = config.get('screen_type', None)
        except Exception as e:
            displayLogger.warning(f"Could not read screen_type from config: {e}")
    
    display = WeatherDisplay(screen_type=screen_type)
    display.generate()


# main
if __name__ == '__main__':
    main()
