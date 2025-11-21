# Use official Python image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements if present
COPY requirements.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY netatmo.py ./
COPY utils.py ./
COPY weather.py ./
COPY display.py ./
COPY server.py ./

# copy font
COPY free-sans.ttf ./

# Set default command (adjust as needed)
CMD ["python", "netatmo.py"]