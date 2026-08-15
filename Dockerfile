FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOWNLOAD_DIR=/app/downloads

# Set working directory
WORKDIR /app

# Install system dependencies (lxml, network tools, and Playwright Chromium requirements)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    curl \
    nss \
    nspr \
    atk \
    at-spi2-atk \
    cups \
    drm \
    dbus \
    x11-xserver-utils \
    xcomposite \
    xdamage \
    xfixes \
    xrandr \
    gbm \
    pango \
    cairo \
    asound2 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies & Playwright Chromium browser
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium --with-deps

# Copy application files
COPY . /app/

# Create downloads directory
RUN mkdir -p /app/downloads

# Entry point command
CMD ["python", "run.py"]
