#!/usr/bin/env python3
"""netatmo.py
NetAtmo weather station display
Every 10 minutes, gets the weather station data to a
local data.json file, and calls display.py.
"""

import requests
import time
import sys
import os
import logging
import display
import utils
import weather
import threading

netatmoLogger = logging.getLogger(__name__)
netatmoLogger.setLevel(logging.INFO)
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s')

stop_event = threading.Event()

# JSON file names
config_filename = "config/config.json"
token_filename = "config/token.json"
data_filename = "data/data.json"

# Global variables
g_config = dict()
g_config_default = '{"client_id": "xxxx", "client_secret": "xxxx", "device_id": "xxxx", "refresh_time": 600}, "location": {"longitude": 0.0, "latitude": 0.0, "altitude": 0}}'
g_token = dict()
g_token_default = '{"access_token": "xxxx", "refresh_token": "xxxx"}'
g_data = dict()

def get_new_token_info():
    """Instruct the user to authenticate on the dev portal and get a new token."""
    netatmoLogger.error('_______________________________________________________')
    netatmoLogger.error("Please generate a new access token, edit %s,", token_filename)
    netatmoLogger.error("and try again.")
    netatmoLogger.error(' - Go to https://dev.netatmo.com/apps/, authenticate')
    netatmoLogger.error('   if necessary, and select your app.')
    netatmoLogger.error(' - Under "Token generator", select the "read_station"')
    netatmoLogger.error('   scope and click "Generate Token".')
    netatmoLogger.error(' - It takes a while, but you will get a page where you')
    netatmoLogger.error('   have to authorize your app to access to your data.')
    netatmoLogger.error(' - Click "Yes I accept".')
    netatmoLogger.error('   You now have a new Access Token and a new Refresh')
    netatmoLogger.error('   token.')
    netatmoLogger.error(' - Click on the access token. It will copy it to your')
    netatmoLogger.error('   clipboard. Paste it in your %s file in place', token_filename)
    netatmoLogger.error('   of the access_token placeholder.')
    netatmoLogger.error(' - same thing for the refresh token.')
    netatmoLogger.error(' - save the %s file.', token_filename)
    netatmoLogger.error('_______________________________________________________')
    sys.exit(1)

def refresh_token():
    """NetAtmo API token refresh. Result: g_token and token.json file."""
    global g_token
    global g_config
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': g_token['refresh_token'],
        'client_id': g_config['client_id'],
        'client_secret': g_config['client_secret'],
    }
    try:
        response = requests.post("https://api.netatmo.com/oauth2/token", data=payload)
        netatmoLogger.debug("%d %s", response.status_code, response.text)
        response.raise_for_status()
        g_token = response.json()
        utils.write_json(g_token, token_filename)
        netatmoLogger.info("refresh_token() OK.")
    except requests.exceptions.HTTPError as e:
        netatmoLogger.warning("refresh_token() HTTPError")
        netatmoLogger.warning("%d %s", e.response.status_code, e.response.text)
        netatmoLogger.warning("refresh_token() failed. Need a new access token.")
        get_new_token_info()
        return
    except requests.exceptions.RequestException:
        netatmoLogger.error("refresh_token() RequestException", exc_info=1)

def get_station_data():
    """Gets Netatmo weather station data. Result: g_data and data.json file."""
    global g_token
    global g_config
    global g_data
    params = {
        'access_token': g_token['access_token'],
        'device_id': g_config['device_id']
    }
    try:
        response = requests.post("https://api.netatmo.com/api/getstationsdata", params=params)
        netatmoLogger.debug("%d %s", response.status_code, response.text)
        response.raise_for_status()
        g_data = response.json()
        utils.write_json(g_data, data_filename)

        if 'location' in g_data['body']['devices'][0]['place']:
            location = g_data['body']['devices'][0]['place']['location']
            altitude = g_data['body']['devices'][0]['place']['altitude']
            if 'location ' not in g_config:
                g_config['location'] = dict()
            if 'longitude' not in g_config['location'] or g_config['location']['longitude'] != location[0] or g_config['location']['latitude'] != location[1] or g_config['location']['altitude'] != altitude:
                g_config['location']['longitude'] = location[0]
                g_config['location']['latitude'] = location[1]
                g_config['location']['altitude'] = altitude
                utils.write_json(g_config, config_filename)
                netatmoLogger.warning("Station location updated in config.json: lon %f lat %f", g_config['location']['longitude'], g_config['location']['latitude'])

    except requests.exceptions.HTTPError as e:
        netatmoLogger.warning("get_station_data() HTTPError")
        netatmoLogger.warning("%d %s", e.response.status_code, e.response.text)
        if e.response.status_code == 403:
            netatmoLogger.info("get_station_data() calling refresh_token()")
            refresh_token()
            # retry
            netatmoLogger.info("get_station_data() retrying")
            get_station_data()
    except requests.exceptions.RequestException:
        netatmoLogger.error("get_station_data() RequestException:", exc_info=1)

def display_console():
    """Displays weather data on the console. Input: g_data"""
    global g_data
    # console
    displaystr = "No data"
    if "body" in g_data:
        displaystr = "Time " + utils.timestr(g_data["time_server"])
        device = g_data["body"]["devices"][0]
        if "dashboard_data" in device:
            if "Pressure" in device["dashboard_data"]:
                displaystr += " | Pressure " + str(device["dashboard_data"]["Pressure"])
            if "Temperature" in device["dashboard_data"]:
                displaystr += " | Indoor " + str(device["dashboard_data"]["Temperature"])
        for module in device["modules"]:
            if "dashboard_data" in module:
                module_type = module["type"]
                if module_type == "NAModule1":
                    # Outdoor Module
                    if "Temperature" in module["dashboard_data"]:
                        displaystr += " | Outdoor " + str(module["dashboard_data"]["Temperature"])
                elif module_type == "NAModule2":
                    # Wind Gauge
                    if "WindStrength" in module["dashboard_data"]:
                        displaystr += " | Wind " + str(module["dashboard_data"]["WindStrength"])
                    if "WindAngle" in module["dashboard_data"]:
                        displaystr += " angle " + str(module["dashboard_data"]["WindAngle"])
                elif module_type == "NAModule3":
                    # Rain Gauge
                    if "Rain" in module["dashboard_data"]:
                        displaystr += " | Rain " + str(module["dashboard_data"]["Rain"])
                elif module_type == "NAModule4":
                    # Optional indoor module
                    if "module_name" in module:
                        module_name = module["module_name"]
                    else:
                        module_name = "Opt Indoor"
                    if "Temperature" in module["dashboard_data"]:
                        displaystr += " | " + module_name + " " + str(module["dashboard_data"]["Temperature"])
    netatmoLogger.info(displaystr)

def check_config():
    """Check configuration validity"""
    global g_token
    global g_config
    
    # check directories
    if not os.path.isdir("config"):
        os.mkdir("config")
    if not os.path.isdir("data"):
        os.mkdir("data")

    # read config
    if os.path.isfile(config_filename):
        g_config = utils.read_json(config_filename)
        if g_config['client_id'] == 'xxxx' or g_config['client_secret'] == 'xxxx' or g_config['device_id'] == 'xxxx':
            netatmoLogger.error("main() error:")
            netatmoLogger.error("Please edit %s and try again.", config_filename)
            sys.exit(1)
        if 'refresh_time' not in g_config or g_config['refresh_time'] < 60:
            g_config['refresh_time'] = 600 # default 10 minutes
    else:
        g_config = g_config_default
        utils.write_json(g_config, config_filename)
        netatmoLogger.error("main() error:")
        netatmoLogger.error("Please edit %s and try again.", config_filename)

    # read last token    
    if os.path.isfile(token_filename):
        g_token = utils.read_json(token_filename)
    else:
        g_token = g_token_default
        utils.write_json(g_token, token_filename)
        get_new_token_info()

def start_netatmo_service():
    """Main function"""
    global g_config
    global g_data

    check_config()

    print("Starting NetAtmo service...")
    print(g_config['refresh_time'], "seconds refresh time.")

    # read last data
    if os.path.isfile(data_filename):
        g_data = utils.read_json(data_filename)
    
    while not stop_event.is_set():
        get_station_data()
        weather.get_weather_data()
        display_console()
        display.main()

        # sleep in small chunks so shutdown is responsive
        for _ in range(g_config['refresh_time']):
            if stop_event.is_set():
                break
            time.sleep(1)

if __name__ == '__main__':
    start_netatmo_service()