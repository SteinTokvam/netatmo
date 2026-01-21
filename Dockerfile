# Use official Python image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements if present
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/netatmo.py ./src/
COPY src/utils.py ./src/
COPY src/weather.py ./src/
COPY src/display.py ./src/
COPY scripts/server.py ./scripts/

# copy font
COPY free-sans.ttf ./

# Set default command (adjust as needed)
CMD ["python", "scripts/server.py"]