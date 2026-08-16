FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DOWNLOAD_DIR=/app/downloads

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
RUN mkdir -p /app/downloads

CMD ["python", "run.py"]
