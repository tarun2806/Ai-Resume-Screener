#!/bin/bash

# Remove existing deploy folder if it exists
rm -rf hf_deploy
mkdir -p hf_deploy

# Copy backend files to root of deploy folder (HF Spaces expects flat structure)
cp -r backend/* hf_deploy/
cp backend/.env.example hf_deploy/.env 2>/dev/null || true

# Clean up local venv or cache if accidentally copied
rm -rf hf_deploy/venv
rm -rf hf_deploy/__pycache__

# Create a simplified README for the Space
echo "# AI Resume Screener API" > hf_deploy/README.md
echo "Backend API for AI Resume Screener. Deployed via Hugging Face Spaces." >> hf_deploy/README.md

# Update Dockerfile in deploy folder to be HF compatible (permission adjustment)
# Hugging Face runs as a randomized user ID, so we need 777 permissions on /app for temp files
sed -i '' 's|CMD|RUN chmod -R 777 /app\nCMD|g' hf_deploy/Dockerfile

echo "✅ Deployment folder 'hf_deploy' created!"
echo "If Render fails, simply upload the contents of 'hf_deploy' to your Hugging Face space."
