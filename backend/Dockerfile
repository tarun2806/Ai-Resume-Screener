FROM python:3.9-slim

WORKDIR /app

# Optimize memory for Free Tier
ENV PYTHONUNBUFFERED=1 \
    SCIKIT_LEARN_NO_OPENMP=1 \
    OMP_NUM_THREADS=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .

# Upgrade pip
RUN pip install --upgrade pip

# Install CPU-only PyTorch with 1000s timeout
RUN pip install --no-cache-dir --default-timeout=1000 torch --index-url https://download.pytorch.org/whl/cpu

# Install other dependencies with 1000s timeout
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Download Spacy model
RUN python -m spacy download en_core_web_sm

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8000

# Run the application
# Run the application with dynamic port for Railway/Heroku
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
