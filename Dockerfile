FROM python:3.11-slim

# ── Iranize inject ──────────────────────────────────────────────────────────────
RUN . /etc/os-release && \
    echo "deb http://mirror-linux.runflare.com/debian $VERSION_CODENAME main" > /etc/apt/sources.list && \
    echo "deb http://mirror-linux.runflare.com/debian-security $VERSION_CODENAME-security main" >> /etc/apt/sources.list

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── App setup ────────────────────────────────────────────────────────────────
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt .
RUN pip install -i https://mirror-pypi.runflare.com/simple --no-cache-dir --upgrade pip \
    && pip install -i https://mirror-pypi.runflare.com/simple --no-cache-dir -r requirements.txt

COPY . .

# ── Entrypoint ───────────────────────────────────────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
