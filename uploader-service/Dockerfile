# Using slim stable version for ARM64
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code files into the image layer
COPY . /app/

# Keep the container running persistently in the background for Jenkins triggers
CMD ["tail", "-f", "/dev/null"]