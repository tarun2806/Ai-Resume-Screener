#!/bin/bash
echo "Setting up AI Resume Screener Backend..."

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download Spacy model
python3 -m spacy download en_core_web_md

echo "Setup complete. Run 'source venv/bin/activate && python3 main.py' to start the server."
