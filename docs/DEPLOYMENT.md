# Deployment Guide

## Table of Contents

1. [Local Development](#local-development)
2. [VPS/Cloud Deployment](#vpscloud-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Monitoring Setup](#monitoring-setup)
6. [Backup & Recovery](#backup--recovery)

---

## Local Development

### Prerequisites

```bash
# Ubuntu 22.04 LTS
sudo apt-get update
sudo apt-get install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    sqlite3 \
    git \
    tmux

# Clone repository
git clone <your-repo-url> unified-crypto-bot
cd unified-crypto-bot
```

### Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
nano .env  # Edit with your keys

# Initialize database
python3 scripts/init_db.py

# Run tests
pytest tests/
```

### Running Locally

```bash
# Terminal 1: Low risk bot
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_low_risk.json --testnet

# Terminal 2: Medium risk bot
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_medium_risk.json --testnet

# Terminal 3: High risk bot
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_high_risk.json --testnet
```

Or use tmux:

```bash
./scripts/start_bots.sh
```

---

## VPS/Cloud Deployment

### Recommended Providers

| Provider | Instance | Cost/Month | Notes |
|----------|----------|------------|-------|
| AWS | t3.small | ~$15 | Good availability |
| DigitalOcean | 2GB RAM | ~$12 | Simple pricing |
| Hetzner | CPX11 | ~$6 | Best value |
| Oracle Cloud | Always Free | $0 | Limited resources |

### Server Setup (Ubuntu 22.04)

```bash
# Create user
sudo adduser trading
sudo usermod -aG sudo trading
su - trading

# Install dependencies
sudo apt-get update
sudo apt-get install -y python3-pip sqlite3 git htop

# Clone repo
git clone <your-repo>

# Setup
pip3 install --user -r requirements.txt

# Create systemd service
sudo nano /etc/systemd/system/crypto-bot.service
```

### Systemd Service

```ini
[Unit]
Description=Unified Crypto Trading Bot
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/home/trading/unified-crypto-bot
Environment=PYTHONPATH=/home/trading/.local/lib/python3.10/site-packages
EnvironmentFile=/home/trading/unified-crypto-bot/.env
ExecStart=/usr/bin/python3 /home/trading/unified-crypto-bot/skills/passivbot-micro/scripts/unified_bot.py --config /home/trading/unified-crypto-bot/config_low_risk.json --live
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Enable service
sudo systemctl daemon-reload
sudo systemctl enable crypto-bot
sudo systemctl start crypto-bot

# Check status
sudo systemctl status crypto-bot
sudo journalctl -u crypto-bot -f
```

### SSH Hardening

```bash
# Disable password auth
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
# PubkeyAuthentication yes

# Firewall
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## Docker Deployment

### Single Bot

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONUNBUFFERED=1

CMD ["python3", "skills/passivbot-micro/scripts/unified_bot.py", "--config", "config_low_risk.json", "--live"]
```

```bash
# Build
docker build -t crypto-bot:low .

# Run
docker run -d \
  --name bot-low \
  --env-file .env \
  -v $(pwd)/memory:/app/memory \
  crypto-bot:low
```

### Multi-Bot with Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  bot-low:
    build: .
    container_name: bot-low
    env_file: .env
    volumes:
      - ./memory:/app/memory
      - ./config/low_risk.json:/app/config/config.json:ro
    command: ["python3", "skills/passivbot-micro/scripts/unified_bot.py", "--config", "config_low_risk.json", "--live"]
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  bot-medium:
    build: .
    container_name: bot-medium
    env_file: .env
    volumes:
      - ./memory:/app/memory
      - ./config_medium_risk.json:/app/config_medium_risk.json:ro
    command: ["python3", "skills/passivbot-micro/scripts/unified_bot.py", "--config", "config_medium_risk.json", "--live"]
    restart: unless-stopped

  bot-high:
    build: .
    container_name: bot-high
    env_file: .env
    volumes:
      - ./memory:/app/memory
      - ./config_high_risk.json:/app/config_high_risk.json:ro
    command: ["python3", "skills/passivbot-micro/scripts/unified_bot.py", "--config", "config_high_risk.json", "--live"]
    restart: unless-stopped

  cron:
    build: .
    container_name: bot-cron
    volumes:
      - ./memory:/app/memory
    command: ["python3", "-c", "while true; do python3 cron_runner_v2.py; sleep 900; done"]
    restart: unless-stopped

volumes:
  memory:
    driver: local
```

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bot-low
docker-compose logs -f --tail=100

# Stop
docker-compose down
```

---

## Kubernetes Deployment

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: trading
```

### ConfigMap

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bot-config
  namespace: trading
data:
  low_risk.json: |
    {
      "initial_capital": 100.0,
      "trend_lookback": 48,
      "trend_threshold": 0.05,
      "exchange": "hyperliquid",
      "symbol": "BTC/USDC:USDC",
      "testnet": false
    }
```

### Secret

```yaml
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: bot-secrets
  namespace: trading
type: Opaque
stringData:
  HYPERLIQUID_API_KEY: "your-api-key"
  HYPERLIQUID_SECRET: "your-secret"
```

### Deployment

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: bot-low
  namespace: trading
spec:
  replicas: 1
  selector:
    matchLabels:
      app: bot-low
  template:
    metadata:
      labels:
        app: bot-low
    spec:
      containers:
      - name: bot
        image: crypto-bot:latest
        envFrom:
        - secretRef:
            name: bot-secrets
        volumeMounts:
        - name: config
          mountPath: /app/config
        - name: memory
          mountPath: /app/memory
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: config
        configMap:
          name: bot-config
      - name: memory
        persistentVolumeClaim:
          claimName: bot-memory
```

### PVC

```yaml
# k8s/pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: bot-memory
  namespace: trading
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Deploy

```bash
kubectl apply -f k8s/

# Check status
kubectl get pods -n trading
kubectl logs -f deployment/bot-low -n trading
```

---

## Monitoring Setup

### Prometheus + Grafana

```yaml
# docker-compose.monitoring.yml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-storage:/var/lib/grafana

volumes:
  grafana-storage:
```

### Log Aggregation

```bash
# Using Loki + Grafana
docker run -d \
  --name loki \
  -p 3100:3100 \
  grafana/loki:latest

# Promtail for log shipping
docker run -d \
  --name promtail \
  -v /var/log:/var/log:ro \
  grafana/promtail:latest
```

### Alerting (Slack)

```python
# scripts/alerts.py
import requests
import json

SLACK_WEBHOOK = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

def send_alert(message, severity="info"):
    color = {"info": "#36a64f", "warning": "#ff9900", "error": "#ff0000"}[severity]
    
    payload = {
        "attachments": [{
            "color": color,
            "text": message,
            "footer": "Crypto Bot",
            "ts": int(time.time())
        }]
    }
    
    requests.post(SLACK_WEBHOOK, json=payload)
```

### Health Checks

```bash
# Add to crontab
*/5 * * * * /path/to/bot/scripts/health_check.sh
```

```bash
#!/bin/bash
# scripts/health_check.sh

if ! pgrep -f "unified_bot.py" > /dev/null; then
    echo "Bot not running!" | mail -s "ALERT: Bot Down" admin@example.com
    /path/to/bot/scripts/start_bots.sh
fi
```

---

## Backup & Recovery

### Database Backup

```bash
#!/bin/bash
# scripts/backup.sh

BACKUP_DIR="/backups/crypto-bot"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup SQLite
cp memory/crypto_prices.db "$BACKUP_DIR/prices_$DATE.db"
cp memory/trades.db "$BACKUP_DIR/trades_$DATE.db" 2>/dev/null

# Compress
gzip "$BACKUP_DIR/prices_$DATE.db"
gzip "$BACKUP_DIR/trades_$DATE.db" 2>/dev/null

# Keep only last 30 days
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete

# Sync to S3 (optional)
aws s3 sync $BACKUP_DIR s3://your-backup-bucket/crypto-bot/
```

```bash
# Add to crontab (daily at 2 AM)
0 2 * * * /path/to/bot/scripts/backup.sh
```

### Recovery

```bash
#!/bin/bash
# scripts/restore.sh

BACKUP_FILE=$1  # e.g., prices_20240318_120000.db.gz

gunzip -c "$BACKUP_FILE" > memory/crypto_prices.db
echo "Database restored from $BACKUP_FILE"
```

### State Recovery

Bot automatically recovers state from:
1. Database (positions, stats)
2. Log files (recent activity)
3. Price history (rebuilds trend detection)

No manual intervention needed for restart.

---

## Security Checklist

- [ ] SSH key auth only (no passwords)
- [ ] Firewall enabled (ufw)
- [ ] API keys in environment variables
- [ ] Database backups encrypted
- [ ] Server auto-updates enabled
- [ ] Fail2ban installed
- [ ] Audit logging enabled
- [ ] No root access for trading user

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Bot not starting | Check logs: `journalctl -u crypto-bot -f` |
| Rate limit errors | Wait for reset, check `.api_rate_state.json` |
| Database locked | Restart bot, check for zombie processes |
| Orders not filling | Check exchange status, verify API keys |
| High memory usage | Restart bot, check for memory leaks |

---

For updates and maintenance, see [OPERATIONS.md](OPERATIONS.md).