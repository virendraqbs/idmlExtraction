# Ubuntu Server Deployment Guide

**Application:** CL Pipeline (FastAPI + Uvicorn + MySQL)
**Target OS:** Ubuntu 22.04 LTS (or 20.04)
**Stack:** Python 3.11, FastAPI, Uvicorn, Nginx (reverse proxy), MySQL 8.0, systemd service

---

## Prerequisites

- Ubuntu server with sudo access
- Git access to the repository
- Domain name or server IP
- Gemini API key
- MySQL root password

---

## Step 1 — System Packages

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y \
    python3.11 python3.11-venv python3.11-dev \
    python3-pip \
    git \
    nginx \
    mysql-server \
    poppler-utils \
    build-essential \
    libssl-dev \
    libffi-dev
```

Verify poppler (required for `pdf2image`):

```bash
pdftoppm -v
# Should print: pdftoppm version x.x
```

---

## Step 2 — Create App User

Run the app under a dedicated non-root user:

```bash
sudo useradd -m -s /bin/bash clpipeline
sudo su - clpipeline
```

All subsequent steps run as `clpipeline` unless noted with `sudo`.

---

## Step 3 — Clone the Repository

```bash
cd /home/clpipeline

git clone <your-repo-url> cl-pdf-extraction
cd cl-pdf-extraction

# Checkout the release branch / tag
git checkout main
```

---

## Step 4 — Python Virtual Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

Verify FastAPI and Uvicorn are installed:

```bash
python -c "import fastapi, uvicorn; print('OK')"
```

---

## Step 5 — MySQL Database Setup

Run as root or with sudo:

```bash
sudo mysql -u root
```

Inside the MySQL shell:

```sql
CREATE DATABASE cl_json_schema CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER 'clpipeline'@'localhost' IDENTIFIED BY 'your-strong-db-password';
GRANT ALL PRIVILEGES ON cl_json_schema.* TO 'clpipeline'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

Import the schema:

```bash
sudo mysql -u root cl_json_schema < /home/clpipeline/cl-pdf-extraction/cl_json_schema.sql
```

Verify tables exist:

```bash
mysql -u clpipeline -p cl_json_schema -e "SHOW TABLES;"
# Should list cl_module, cl_topic, cl_resource, etc.
```

---

## Step 6 — Environment Configuration

```bash
cd /home/clpipeline/cl-pdf-extraction

cp .env.example .env
nano .env
```

Fill in all required values:

```dotenv
# App
SECRET_KEY=<generate: python3 -c "import secrets; print(secrets.token_hex(32))">
FLASK_ENV=production
PORT=8000

# Admin login
ADMIN_USER=admin
ADMIN_PASS=<your-secure-password>

# Gemini
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-2.5-flash

# Upload settings
MAX_UPLOAD_MB=100
PDF_RENDER_DPI=200

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=cl_json_schema
MYSQL_USER=clpipeline
MYSQL_PASSWORD=<your-strong-db-password>

# LDAP (optional — leave blank to disable)
LDAP_ENABLED=false

# AWS S3 (optional — leave blank to skip)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=
```

Secure the file:

```bash
chmod 600 .env
```

---

## Step 7 — Smoke Test (Before Daemonizing)

Activate the venv and run manually to confirm startup:

```bash
source .venv/bin/activate

uvicorn app:app --host 127.0.0.1 --port 8000
```

Expected output:

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Press `Ctrl+C` to stop, then continue.

---

## Step 8 — systemd Service

Create the service file (run as root/sudo):

```bash
sudo nano /etc/systemd/system/clpipeline.service
```

Paste:

```ini
[Unit]
Description=CL Pipeline FastAPI Application
After=network.target mysql.service

[Service]
Type=exec
User=clpipeline
Group=clpipeline
WorkingDirectory=/home/clpipeline/cl-pdf-extraction
Environment="PATH=/home/clpipeline/cl-pdf-extraction/.venv/bin"
EnvironmentFile=/home/clpipeline/cl-pdf-extraction/.env
ExecStart=/home/clpipeline/cl-pdf-extraction/.venv/bin/uvicorn app:app \
    --host 127.0.0.1 \
    --port 8000 \
    --workers 2 \
    --log-level info
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable clpipeline
sudo systemctl start clpipeline

# Check status
sudo systemctl status clpipeline
```

Check live logs:

```bash
sudo journalctl -u clpipeline -f
```

---

## Step 9 — Nginx Reverse Proxy

Create the Nginx site config (run as root/sudo):

```bash
sudo nano /etc/nginx/sites-available/clpipeline
```

Paste (replace `your-domain.com` with your actual domain or server IP):

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Max upload size — must match MAX_UPLOAD_MB in .env
    client_max_body_size 110M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts — PDF processing can take 2–5 minutes
        proxy_read_timeout 600s;
        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
    }

    location /static/ {
        alias /home/clpipeline/cl-pdf-extraction/static/;
        expires 7d;
        add_header Cache-Control "public";
    }
}
```

Enable the site and reload Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/clpipeline /etc/nginx/sites-enabled/

# Test config syntax
sudo nginx -t

sudo systemctl reload nginx
```

---

## Step 10 — SSL Certificate (HTTPS)

Using Certbot (Let's Encrypt) — skip if using IP only:

```bash
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d your-domain.com

# Auto-renewal test
sudo certbot renew --dry-run
```

Certbot automatically updates the Nginx config for HTTPS.

---

## Step 11 — File Permissions

Ensure the app user owns all runtime directories:

```bash
sudo chown -R clpipeline:clpipeline /home/clpipeline/cl-pdf-extraction/uploads
sudo chown -R clpipeline:clpipeline /home/clpipeline/cl-pdf-extraction/outputs

chmod 750 /home/clpipeline/cl-pdf-extraction/uploads
chmod 750 /home/clpipeline/cl-pdf-extraction/outputs
```

---

## Step 12 — Firewall

Allow only HTTP, HTTPS, and SSH:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable

sudo ufw status
```

---

## Step 13 — Verify End-to-End

```bash
# App process is running
sudo systemctl status clpipeline

# App responds on loopback
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/login
# Expected: 200

# Nginx is forwarding correctly
curl -s -o /dev/null -w "%{http_code}" http://your-domain.com/login
# Expected: 200

# DB connection works — no errors in logs
sudo journalctl -u clpipeline --since "1 min ago"
```

---

## Deployment Checklist

| # | Step | Done |
|---|---|---|
| 1 | System packages installed (python, nginx, mysql, poppler-utils) | ☐ |
| 2 | `clpipeline` OS user created | ☐ |
| 3 | Repo cloned, checked out `main` | ☐ |
| 4 | Python venv created, `pip install -r requirements.txt` | ☐ |
| 5 | MySQL DB `cl_json_schema` created, schema imported | ☐ |
| 6 | `.env` configured with real keys, `chmod 600` applied | ☐ |
| 7 | Smoke test passed (uvicorn runs manually) | ☐ |
| 8 | systemd service enabled and started | ☐ |
| 9 | Nginx site configured and reloaded | ☐ |
| 10 | SSL certificate issued (Certbot) | ☐ |
| 11 | Upload/output directory permissions set | ☐ |
| 12 | UFW firewall enabled | ☐ |
| 13 | End-to-end verify: login page returns 200 | ☐ |

---

## Updating the Application (Future Deploys)

```bash
sudo su - clpipeline
cd /home/clpipeline/cl-pdf-extraction

git pull origin main

source .venv/bin/activate
pip install -r requirements.txt

# If DB schema changed:
# mysql -u clpipeline -p cl_json_schema < cl_json_schema.sql

exit

sudo systemctl restart clpipeline
sudo journalctl -u clpipeline -f
```

---

## Troubleshooting

| Problem | Check |
|---|---|
| App fails to start | `sudo journalctl -u clpipeline -n 50` — look for missing env vars or import errors |
| 502 Bad Gateway | App isn't running — `sudo systemctl status clpipeline` |
| Upload fails / 413 | `client_max_body_size` in Nginx must be ≥ `MAX_UPLOAD_MB` |
| PDF processing timeout | Increase `proxy_read_timeout` in Nginx; check Gemini API key |
| DB connection error | Verify `MYSQL_*` values in `.env`; confirm MySQL is running: `sudo systemctl status mysql` |
| Permission denied on uploads | `chown -R clpipeline:clpipeline uploads/` |
| `poppler` not found | `sudo apt install poppler-utils` and restart the service |
