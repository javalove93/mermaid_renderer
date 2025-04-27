# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Flask app and templates directory into the container at /app
COPY app.py .
COPY templates/ /app/templates/
COPY static/ /app/static/

# Port configuration
# Cloud Run will use PORT environment variable
ENV PORT=5000
EXPOSE $PORT

# Run the production server Gunicorn
# It binds to 0.0.0.0 on the port specified by the PORT environment variable
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app

