# Kokoroko Production Deployment Guide

## Architecture

```
                    ┌──────────┐
  Users ──HTTPS──▸  │  Nginx   │ ──▸ Daphne (:8000) ──▸ Django/Channels
                    │ (443/80) │       ▲
                    └──────────┘       │
                                       ├── Celery Worker
                                       ├── Celery Beat
                                       ├── Redis (:6379)
                                       └── MySQL (:3306)
```

- **Nginx** terminates SSL and reverse-proxies to Daphne on `127.0.0.1:8000`
- **Daphne** is NOT exposed to the public internet (localhost-only bind)
- **Redis** and **MySQL** are Docker-internal only (no host port binding)

## Ports

| Port | Service | Exposed? |
|------|---------|----------|
| 80   | Nginx HTTP → HTTPS redirect | Public |
| 443  | Nginx HTTPS (SSL) | Public |
| 8000 | Daphne (Django + WebSockets) | localhost only |

## Services (docker-compose.prod.yml)

| Container | Purpose |
|-----------|---------|
| `kokoroko-prod-server` | Django app via Daphne (HTTP + WebSocket) |
| `kokoroko-celery-worker` | Async tasks (settlement, notifications, dice rolls) |
| `kokoroko-celery-beat` | Scheduled tasks (auto virtual rounds, cleanup) |
| `kokoroko-redis` | Channel layer, caching, Celery broker |
| `kokoroko-mysql` | Primary database |

## Environment Variables

Create a `.env` file in the server directory (never commit this):

```env
# Django
DJANGO_ENV=prod
SECRET_KEY=<your-django-secret-key>

# Database
DB_HOST=mysql
DB_PORT=3306
DB_NAME=kokoroko_db
DB_USER=kokoroko
DB_PASSWORD=<your-db-password>
MYSQL_ROOT_PASSWORD=<your-mysql-root-password>
MYSQL_DATABASE=kokoroko_db
MYSQL_USER=kokoroko
MYSQL_PASSWORD=<your-db-password>

# Redis
REDIS_URL=redis://redis:6379/0

# OTP (random by default; set these ONLY for staging/dev)
# OTP_ALLOW_FIXED=true
# OTP_FIXED_CODE=123456

# SMS Provider (none|msg91|twilio)
SMS_PROVIDER=none
# MSG91_AUTH_KEY=<your-msg91-key>
# MSG91_SENDER_ID=KOKOKO
# TWILIO_ACCOUNT_SID=<your-twilio-sid>
# TWILIO_AUTH_TOKEN=<your-twilio-token>
# TWILIO_FROM_NUMBER=<your-twilio-number>

# App version (bump for in-app update prompts)
APP_VERSION_CODE=2
APP_VERSION_NAME=2.0.0
APP_DOWNLOAD_URL=https://roosterrun.io/roosterrun.apk
APP_FORCE_UPDATE=false

# Sentry (optional, disabled until set)
# SENTRY_DSN=<your-sentry-dsn>

# CORS (add extra origins for testing)
# CORS_EXTRA_ORIGINS=http://localhost:3000
# CSRF_EXTRA_ORIGINS=http://localhost:3000
```

## Deployment Steps

### Initial Setup

```bash
# 1. Clone repo on server
cd /opt/kokoroko
git clone https://github.com/Moksha89/fight.git .

# 2. Create .env file (see above)
cp server/deploy/.env.example server/.env
# Edit server/.env with real values

# 3. Build and start containers
cd server
docker compose -f docker-compose.prod.yml up -d --build

# 4. Set up Nginx
sudo cp deploy/nginx-roosterrun.conf /etc/nginx/sites-available/roosterrun
sudo ln -sf /etc/nginx/sites-available/roosterrun /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# 5. Set up SSL (if not already done)
sudo certbot certonly --webroot -w /var/www/html \
  -d roosterrun.io -d www.roosterrun.io -d api.roosterrun.io
```

### Updating Production

```bash
cd /opt/kokoroko

# Pull latest code
git pull origin main

# Rebuild and restart
cd server
docker compose -f docker-compose.prod.yml up -d --build

# The compose command runs migrations automatically on startup
# If you need to run them manually:
docker exec kokoroko-prod-server python manage.py migrate
```

## Rate Limits (Nginx)

| Endpoint | Limit | Burst |
|----------|-------|-------|
| OTP request | 3/min | 2 |
| Login | 5/min | 3 |
| Forgot password | 3/min | 2 |
| Bet placement | 30/min | 10 |
| General API | 60/min | 30 |
| Admin API | 30/min | 10 |
| WebSocket connections | 10 per IP | — |

## WebSocket Endpoints

| Path | Purpose |
|------|---------|
| `/ws/notifications/` | User notifications |
| `/ws/cockfight/match-result/` | Cockfight match results |
| `/ws/cockfight/match/` | Live cockfight match updates |
| `/ws/dice/match-result/` | Dice match results |
| `/ws/dice/match/` | Live dice match updates |
| `/ws/dice/timer/` | Dice round timer |

## Backups

Database backups are handled by the backup system. Manual backup:

```bash
docker exec kokoroko-mysql mysqldump -u root -p kokoroko_db > backup_$(date +%Y%m%d).sql
```

## Monitoring

- Health check: `GET /health/`
- Monitoring dashboard: `GET /admin/monitoring/`
- Logs: `/var/log/kokoroko/` (django, celery, security, monitoring)
