FROM local-base:latest

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install Python and system dependencies for OpenCV, sound alert, video encoding
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libsndfile1 \
    libportaudio2 \
    portaudio19-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Alias python to python3
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Upgrade pip
RUN pip3 install --no-cache-dir --upgrade pip

# Install dependencies from requirements.txt
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Ensure data directories exist
RUN mkdir -p data/logs data/violations

# Ports used by Dashboard (4000 or 5001 depending on .env)
EXPOSE 4000 5001

CMD ["python3", "main.py"]
