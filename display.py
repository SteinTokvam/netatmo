#!/usr/bin/env python3
"""display.py
Displays NetAtmo weather station data on a local screen
input: data.json file, result of NetAtmo getstationsdata API
screen: PaPiRus ePaper / eInk Screen HAT for Raspberry Pi - 2.7"
output: copy of the screen in file: image.bmp
"""

import json
import os
import utils
import logging
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

displayLogger = logging.getLogger(__name__)

WHITE = 1
BLACK = 0
# Font file: path below if installed with
# sudo apt install fonts-freefont-ttf
font_file = './free-sans.ttf'
if not os.path.isfile(font_file):
    font_file = '../freefont/FreeSans.ttf'
    if not os.path.isfile(font_file):
        displayLogger.error("No font file")
        exit(1)
# File names
data_filename = 'data/data.json'
weather_data_filename = 'data/weather_data.json'
image_filename = 'image.bmp'
# Global variables
g_data = dict()
g_weather_data = dict()
g_image = None

def read_json(filename):
    """Read a JSON file to a dict object."""
    with open(filename, 'r') as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            data = dict()
    return data

def trend_symbol(trend):
    """Unicode symbol for temperature trend"""
    if trend == 'up':
        return '\u2197' # '↗' U+2197
    elif trend == 'down':
        return '\u2198' # '↘' U+2198
    elif trend == 'stable':
        return '\u2192' # '→' U+2192
    else:
        return ' '

def textsize(text, font):
    left, top, right, bottom = font.getbbox(text)
    width, height = int(right - left), int(bottom - top)
    return width, height

def draw_image():
    """Draws the image in memory (g_image)"""
    global g_data
    global g_weather_data
    global g_image

    # prepare for drawing
    draw = ImageDraw.Draw(g_image)
    width, height = g_image.size

    # base font size on mono spaced font
    font_text = ImageFont.truetype(font_file, 25)
    font_temp = ImageFont.truetype(font_file, 50)
    font_time = ImageFont.truetype(font_file, 15)

    # read data
    if os.path.isfile(data_filename):
        g_data = read_json(data_filename)
    else:
        displayLogger.error("No data file")
        return
    if not ("body" in g_data):
        displayLogger.error("Bad data format")
        return
    
    # read weather data
    if os.path.isfile(weather_data_filename):
        g_weather_data = read_json(weather_data_filename)
    else:
        displayLogger.error("No weather data file")
        return
    if not ("properties" in g_weather_data):
        displayLogger.error("Bad weather data format")
        return

    # Units
    # see https://dev.netatmo.com/en-US/resources/technical/reference/weather/getstationsdata
    # for details
    user_admin = g_data["body"]["user"]["administrative"]
    unit_temp = ['°C', '°F'][user_admin["unit"]]
    unit_rain = ['mm/h', 'in/h'][user_admin["unit"]]
    unit_wind = ['kph', 'mph', 'm/s', 'beaufort', 'knot'][user_admin["windunit"]]
    unit_humidity = '%'
    unit_co2 = 'ppm'

    # get and format values
    indoor_temp_str = 'N/A'
    indoor_humidity_str = 'N/A'
    outdoor_humidity_str = 'N/A'
    indoor_co2_str = 'N/A'
    outdoor_temp_str = 'N/A'
    rain_str = 'N/A'
    wind_str = 'N/A'

    data_time_str = "Sist oppdatert: " + utils.timestr(g_data["time_server"])

    forecast_now = "N/A"
    forecast_6_hours = "N/A"
    forecast_12_hours = "N/A"
    forecast_18_hours = "N/A"
    forecast_24_hours = "N/A"

    # main module: indoor temperature (line 1) and pressure (not used)
    device = g_data["body"]["devices"][0]
    if "dashboard_data" in device:
        indoor_data = device["dashboard_data"]
        indoor_temp_str = '{0:.1f}'.format(indoor_data["Temperature"]) + " " + unit_temp
        indoor_humidity_str = '{0:.1f}'.format(indoor_data["Humidity"]) + " " + unit_humidity
        if "temp_trend" in indoor_data:
            indoor_temp_str += trend_symbol(indoor_data["temp_trend"])
        indoor_co2_str = '{0:.1f}'.format(indoor_data["CO2"]) + " " + unit_co2
        if "pressure_trend" in indoor_data:
            indoor_co2_str += trend_symbol(indoor_data["pressure_trend"])

    # other modules: outdoor temperature, rain (lines 2 & 3), wind (unused), optional indoor (unused)
    for module in device["modules"]:
        if "dashboard_data" in module:
            module_type = module["type"]
            module_data = module["dashboard_data"]
            if module_type == "NAModule1":
                # Outdoor Module
                outdoor_temp_str = '{0:.1f}'.format(module_data["Temperature"]) + " " + unit_temp
                outdoor_humidity_str = '{0:.1f}'.format(module_data["Humidity"]) + " " + unit_humidity
                if "temp_trend" in module_data:
                    outdoor_temp_str += trend_symbol(module_data["temp_trend"])
            elif module_type == "NAModule2":
                # Wind Gauge
                wind_str = '{0:.1f}'.format(module_data["WindStrength"]) + " " + unit_wind
            elif module_type == "NAModule3":
                # Rain Gauge
                if module_data["sum_rain_24"] is not None:
                    rain_str = '{0:.1f}'.format(module_data["sum_rain_24"]) + " mm"
            elif module_type == "NAModule4":
                # Optional indoor module
                pass
    
    # weather forecast
    if "properties" in g_weather_data:
        timeseries = g_weather_data["properties"]["timeseries"]
        if len(timeseries) > 23:
            forecast_now = timeseries[0]
            forecast_now_details = forecast_now["data"]["next_6_hours"]["details"]
            forecast_6_hours = timeseries[5]
            forecast_6_hours_details = forecast_6_hours["data"]["next_6_hours"]["details"]
            forecast_12_hours = timeseries[11]
            forecast_12_hours_details = forecast_12_hours["data"]["next_6_hours"]["details"]
            forecast_18_hours = timeseries[17]
            forecast_18_hours_details = forecast_18_hours["data"]["next_6_hours"]["details"]
            forecast_24_hours = timeseries[23]
            forecast_24_hours_details = forecast_24_hours["data"]["next_6_hours"]["details"]


    # width and height of strings
    (width_indoor, height_indoor) = textsize(indoor_temp_str, font=font_temp)
    (width_outdoor, height_outdoor) = textsize(outdoor_temp_str, font=font_temp)
    (width_rain, height_rain) = textsize(rain_str, font=font_temp)
    (width_time, height_time) = textsize(data_time_str, font=font_time)

    # which is bigger?
    txtwidth, txtheight = width_indoor, height_indoor
    if width_outdoor > txtwidth:
        txtwidth = width_outdoor
    if width_rain > txtwidth:
        txtwidth = width_rain

    first_window_x = int(width/8)
    first_window_y = int(height/8)
    second_window_x = int((width/2)+width/6)
    second_window_y = int(height/8)
    bottom_window_x = int(10)
    bottom_window_y = int(height/2+150)

    # Draws rectangle and lines
    draw.rectangle((2, 2, width - 2, height - 2), fill=WHITE, outline=BLACK)
    draw.line((width/2,2, width/2,height/2), fill=BLACK, width=2)
    draw.line((2,height/2, width-2,height/2), fill=BLACK, width=2)

    # lines for bottom window
    draw.line((width/4,height/2, width/4,height-2), fill=BLACK, width=2)
    draw.line(((width/4)+(width/4),height/2, (width/4)+(width/4),height-2), fill=BLACK, width=2)
    draw.line(((width/4)+(width/4)+(width/4),height/2, (width/4)+(width/4)+(width/4),height-2), fill=BLACK, width=2)
    draw.line(((width/4)+(width/4)+(width/4)+(width/4),height/2, (width/4)+(width/4)+(width/4)+(width/4),height-2), fill=BLACK, width=2)

    # temperatures
    draw.text((first_window_x, first_window_y), indoor_temp_str, fill=BLACK, font=font_temp)
    draw.text((first_window_x, first_window_y + txtheight+5), outdoor_temp_str, fill=BLACK, font = font_temp)

    # indoor humidity and CO2
    draw.text((first_window_x, second_window_y + (4*(txtheight))), indoor_humidity_str + " / " + indoor_co2_str, fill=BLACK, font = font_text)

    # rain and wind
    draw.text((second_window_x, second_window_y), rain_str, fill=BLACK, font = font_temp)
    if wind_str != 'N/A':
        draw.text((second_window_x, second_window_y + txtheight + 5), wind_str, fill=BLACK, font = font_temp)
    
    # outdoor humidity
    draw.text((second_window_x, second_window_y + (4*(txtheight))), outdoor_humidity_str, fill=BLACK, font = font_text)

    # time
    draw.text((width - width_time - 5, 5), data_time_str, fill = BLACK, font = font_time)

    # weather forecast
    weather_symbol_0 = Image.open("symbols/" + forecast_now["data"]["next_6_hours"]["summary"]["symbol_code"] + ".png")
    weather_symbol_0 = weather_symbol_0.resize((100,100))
    g_image.paste(weather_symbol_0, (60,300), mask=weather_symbol_0)
    draw.text((bottom_window_x, bottom_window_y), utils.format_time_str(forecast_6_hours["time"]), fill=BLACK, font = font_text)
    draw.text((bottom_window_x, bottom_window_y+30), '{0:.1f}'.format(forecast_now_details["air_temperature_min"]) + unit_temp + " / " + '{0:.1f}'.format(forecast_now_details["air_temperature_max"]) + unit_temp, fill=BLACK, font = font_text)

    weather_symbol_1 = Image.open("symbols/" + forecast_6_hours["data"]["next_6_hours"]["summary"]["symbol_code"] + ".png")
    weather_symbol_1 = weather_symbol_1.resize((100,100))
    g_image.paste(weather_symbol_1, (300,300), mask=weather_symbol_1)
    draw.text((bottom_window_x+(width/4), bottom_window_y), utils.format_time_str(forecast_12_hours["time"]), fill=BLACK, font = font_text)
    draw.text((bottom_window_x+(width/4), bottom_window_y+30), '{0:.1f}'.format(forecast_12_hours_details["air_temperature_min"]) + unit_temp + " / " + '{0:.1f}'.format(forecast_12_hours_details["air_temperature_max"]) + unit_temp, fill=BLACK, font = font_text)

    weather_symbol_2 = Image.open("symbols/" + forecast_12_hours["data"]["next_6_hours"]["summary"]["symbol_code"] + ".png")
    weather_symbol_2 = weather_symbol_2.resize((100,100))
    g_image.paste(weather_symbol_2, (540,300), mask=weather_symbol_2)
    draw.text((bottom_window_x+((width/4)*2), bottom_window_y), utils.format_time_str(forecast_18_hours["time"]), fill=BLACK, font = font_text)
    draw.text((bottom_window_x+((width/4)*2), bottom_window_y+30), '{0:.1f}'.format(forecast_18_hours_details["air_temperature_min"]) + unit_temp + " / " + '{0:.1f}'.format(forecast_18_hours_details["air_temperature_max"]) + unit_temp, fill=BLACK, font = font_text)

    weather_symbol_3 = Image.open("symbols/" + forecast_18_hours["data"]["next_6_hours"]["summary"]["symbol_code"] + ".png")
    weather_symbol_3 = weather_symbol_3.resize((100,100))
    g_image.paste(weather_symbol_3, (780,300), mask=weather_symbol_3)
    draw.text((bottom_window_x+((width/4)*3), bottom_window_y), utils.format_time_str(forecast_24_hours["time"]), fill=BLACK, font = font_text)
    draw.text((bottom_window_x+((width/4)*3), bottom_window_y+30), '{0:.1f}'.format(forecast_24_hours_details["air_temperature_min"]) + unit_temp + " / " + '{0:.1f}'.format(forecast_24_hours_details["air_temperature_max"]) + unit_temp, fill=BLACK, font = font_text)

def main():
    """Main function"""
    global g_image

    g_image = Image.new('1', (960, 540), WHITE)
    draw_image()
    humidity = Image.open("symbols/humidity.png")
    #img1 = Image.open("output_bw/01d.png")
    #img2 = Image.open("symbols/rainy.png")
    #img3 = Image.open("symbols/cloudy.png")
    #img4 = Image.open("symbols/snowy.png")
    #img1 = img1.resize((100,100))
    #img2 = img2.resize((100,100))
    #img3 = img3.resize((100,100))
    #img4 = img4.resize((100,100))
    g_image.paste(humidity, (600,225), mask=humidity)
    #g_image.paste(img1, (60,300), mask=img1)
    #g_image.paste(img2, (300,300), mask=img2)
    #g_image.paste(img3, (540,300), mask=img3)
    #g_image.paste(img4, (780,300), mask=img4)
    g_image.save(image_filename)

# main
if __name__ == '__main__':
    main()
