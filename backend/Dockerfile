# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies needed for PyMuPDF and other NLP libs
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
# Note: We use --no-cache-dir to keep the image size small
RUN pip install --no-cache-dir -r requirements.txt

# Download the SpaCy model (Small model for production efficiency)
RUN python -m spacy download en_core_web_md

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on (Railway/Render usually provide $PORT)
EXPOSE 8000

# Command to run the application
# Use sh -c to expand the $PORT variable from the environment
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
