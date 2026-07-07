FROM python:3.11-slim

# Install system deps (ffmpeg, sox, ImageMagick, curl, git)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    sox \
    imagemagick \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create app dir
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the repository
COPY . /app

# Unbuffered output for logs
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "-u", "bot/ihtx_bot.py"]
