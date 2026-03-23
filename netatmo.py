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

netatmoLogger = logging.getLogger(__name__)

REQUEST_TIMEOUT = (5, 30)
UPDATE_INTERVAL_SECONDS = 600

# JSON file names
token_filename = "config/token.json"
data_filename = "data/data.json"

# Global variables
g_token = dict()
g_data = dict()

def get_new_token():
    """Instruct the user to authenticate on the dev portal and get a new token."""
    if not os.path.isfile(token_filename):
        g_token = {"access_token": "xxxx", "refresh_token": "xxxx"}
        utils.write_json(g_token, token_filename)

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

def refresh_token(config):
    """NetAtmo API token refresh. Result: g_token and token.json file."""
    global g_token
    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': g_token['refresh_token'],
        'client_id': config['client_id'],
        'client_secret': config['client_secret'],
    }
    try:
        response = requests.post(
            "https://api.netatmo.com/oauth2/token",
            data=payload,
            timeout=REQUEST_TIMEOUT,
        )
        netatmoLogger.debug("%d %s", response.status_code, response.text)
        response.raise_for_status()
        g_token = response.json()
        utils.write_json(g_token, token_filename)
        netatmoLogger.info("refresh_token() OK.")
        return True
    except requests.exceptions.HTTPError as e:
        netatmoLogger.warning("refresh_token() HTTPError")
        netatmoLogger.warning("%d %s", e.response.status_code, e.response.text)
        netatmoLogger.warning("refresh_token() failed. Need a new access token.")
        get_new_token()
        return False
    except requests.exceptions.RequestException:
        netatmoLogger.error("refresh_token() RequestException", exc_info=1)
        return False

def get_station_data(config):
    """Gets Netatmo weather station data. Result: g_data and data.json file."""
    global g_token
    global g_data
    for attempt in range(2):
        params = {
            'access_token': g_token['access_token'],
            'device_id': config['device_id']
        }
        try:
            response = requests.post(
                "https://api.netatmo.com/api/getstationsdata",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            netatmoLogger.debug("%d %s", response.status_code, response.text)
            response.raise_for_status()
            g_data = response.json()
            utils.write_json(g_data, data_filename)
            return True
        except requests.exceptions.HTTPError as e:
            netatmoLogger.warning("get_station_data() HTTPError")
            netatmoLogger.warning("%d %s", e.response.status_code, e.response.text)
            if e.response.status_code == 403 and attempt == 0:
                netatmoLogger.info("get_station_data() calling refresh_token()")
                if refresh_token(config):
                    netatmoLogger.info("get_station_data() retrying")
                    continue
            return False
        except requests.exceptions.RequestException:
            netatmoLogger.error("get_station_data() RequestException:", exc_info=1)
            return False
    return False

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

def updater_thread(config):
    global g_token, g_data
    while True:
        cycle_started = time.monotonic()
        try:
            if get_station_data(config):
                display_console()
                try:
                    display.main()
                except Exception:
                    netatmoLogger.error("display.main() failed", exc_info=1)
        except Exception:
            netatmoLogger.error("updater_thread() unexpected failure", exc_info=1)

        elapsed = time.monotonic() - cycle_started
        time.sleep(max(0, UPDATE_INTERVAL_SECONDS - elapsed))

def startNetatmoService(config):
    """Main function"""
    global g_token
    global g_data

    # read last token    
    if os.path.isfile(token_filename):
        g_token = utils.read_json(token_filename)
    else:
        #authenticate()
        netatmoLogger.error("main() error:")
        netatmoLogger.error("Token file not found: creating an empty one.")
        get_new_token()
        return

    # read last data
    if os.path.isfile(data_filename):
        g_data = utils.read_json(data_filename)
    
    updater_thread(config)
