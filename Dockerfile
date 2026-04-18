FROM python:3.11-slim

# ── Iranize inject ──────────────────────────────────────────────────────────────
RUN UBUNTU_CODENAME=$(lsb_release -cs) && tee /etc/apt/sources.list > /dev/null <<EOF
deb https://mirror.mobinhost.com/ubuntu $UBUNTU_CODENAME main restricted universe multiverse
deb https://mirror.mobinhost.com/ubuntu $UBUNTU_CODENAME-updates main restricted universe multiverse
deb https://mirror.mobinhost.com/ubuntu $UBUNTU_CODENAME-backports main restricted universe multiverse
deb https://mirror.mobinhost.com/ubuntu $UBUNTU_CODENAME-security main restricted universe multiverse
EOF
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