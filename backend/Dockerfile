FROM python:3.12-slim

WORKDIR /app

# Install build deps, pip install, then remove build deps in one layer to save space/memory
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build deps after pip install (runtime doesn't need them)
RUN apt-get purge -y --auto-remove gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
