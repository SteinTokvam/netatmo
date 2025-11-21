import http.server
import socketserver
import json
import threading
import netatmo
import weather
import logging
import os 

logging.basicConfig()
logging.root.setLevel(logging.INFO)

serverLogger = logging.getLogger("server")

class WeatherHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/weather.json":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(weather_data).encode('utf-8'))
        elif self.path == "/image.bmp":
            if os.path.exists("image.bmp"):
                with open("image.bmp", "rb") as f:
                    bmp_data = f.read()
                self.send_response(200)
                self.send_header("Content-type", "image/bmp")
                self.send_header("Content-Length", str(len(bmp_data)))
                self.end_headers()
                self.wfile.write(bmp_data)
        else:
            self.send_response(404)
            self.end_headers()

def main():
    serverLogger.info("Starting server...")

    # Start netatmo service in background thread
    netatmo_thread = threading.Thread(target=netatmo.startNetatmoService, daemon=True)
    netatmo_thread.start()
    serverLogger.info("Netatmo service started.")

    # Start weather data retrieval in background thread
    weather_thread = threading.Thread(target=weather.startWeatherService, daemon=True)
    weather_thread.start()
    serverLogger.info("Weather service started.")

    # start web server
    PORT = 8000
    serverLogger.info(f"Serving at http://0.0.0.0:{PORT}/weather.json")
    with socketserver.TCPServer(("", PORT), WeatherHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    main()