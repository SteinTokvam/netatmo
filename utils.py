import json
import logging
import os
import tempfile
import time

utilsLogger = logging.getLogger(__name__)

def read_json(filename):
    """Read a JSON file to a dict object."""
    with open(filename, 'r') as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            utilsLogger.warning("read_json() JSONDecodeError", exc_info=1)
            data = dict()
    return data

def write_json(data, filename, ensure_ascii=True):
    """Write a dict object to a JSON file atomically."""
    directory = os.path.dirname(filename) or "."
    os.makedirs(directory, exist_ok=True)

    with tempfile.NamedTemporaryFile('w', dir=directory, delete=False, encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)
        f.flush()
        os.fsync(f.fileno())
        temp_filename = f.name

    os.replace(temp_filename, filename)

def timestr(t):
    return time.strftime("%H:%M",time.localtime(t))

def format_time_str(t):
    return t.split("T")[0] + " " + t.split("T")[1][0:5]
