# 🚀 LXC Container Deployment Guide

This guide explains how to deploy the Telegram AI Assistant Bot on an LXC container for continuous operation.

## Prerequisites

- LXC/LXD installed on your host system
- Root or sudo access
- Internet connection
- API keys for the services (Telegram, OpenRouter, Fal AI)

## 1. Create and Configure LXC Container

### Create Ubuntu Container
```bash
# Create a new Ubuntu 22.04 LTS container
lxc launch ubuntu:22.04 ai-tg-bot

# Wait for container to start
lxc exec ai-tg-bot -- cloud-init status --wait

# Enter the container
lxc exec ai-tg-bot -- bash
```

### Update System
```bash
# Update package lists and upgrade system
apt update && apt upgrade -y

# Install essential packages
apt install -y curl wget git python3 python3-pip python3-venv htop nano
```

## 2. Clone and Setup Application

```bash
# Clone the repository (running as root)
cd /root
git clone https://github.com/ygrfil/ai_tg_bot.git
cd ai_tg_bot

# Switch to main branch
git checkout main

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## 3. Configure Environment

```bash
# Create environment file
nano .env
```

Add the following configuration:
```env
# Telegram Bot Configuration
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
ALLOWED_USER_IDS=user1_id,user2_id,user3_id

# AI Provider API Keys
OPENROUTER_API_KEY=your_openrouter_api_key
FAL_API_KEY=your_fal_api_key

# Performance Settings
MAX_TOKENS=4096
POLLING_TIMEOUT=10
POLLING_INTERVAL=0.5
POLLING_MAX_DELAY=5.0
POLLING_START_DELAY=1.0
POLLING_BACKOFF_FACTOR=1.5
POLLING_JITTER=0.1

# Database Settings
DATABASE_PATH=data/chat.db
```

## 4. Create Systemd Service

Create service file:
```bash
nano /etc/systemd/system/ai-tg-bot.service
```

Add the following service configuration:
```ini
[Unit]
Description=AI Telegram Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/root/ai_tg_bot
Environment=PATH=/root/ai_tg_bot/venv/bin
ExecStart=/root/ai_tg_bot/venv/bin/python main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ai-tg-bot

# Resource limits
MemoryMax=512M
CPUQuota=50%

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ReadWritePaths=/root/ai_tg_bot/data

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
# Reload systemd configuration
systemctl daemon-reload

# Enable service to start on boot
systemctl enable ai-tg-bot

# Start the service
systemctl start ai-tg-bot

# Check service status
systemctl status ai-tg-bot
```

## 5. Container Auto-Start Configuration

On the host system, configure the container to start automatically:

```bash
# Enable auto-start for the container
lxc config set ai-tg-bot boot.autostart true

# Set startup priority (optional)
lxc config set ai-tg-bot boot.autostart.priority 10

# Set startup delay (optional)
lxc config set ai-tg-bot boot.autostart.delay 30
```

## 6. Resource Limits and Optimization

Configure container resource limits:
```bash
# Set memory limit (adjust based on your needs)
lxc config set ai-tg-bot limits.memory 1GB

# Set CPU limit (optional)
lxc config set ai-tg-bot limits.cpu 2

# Set disk limits (optional)
lxc config device override ai-tg-bot root size=10GB
```

## 7. Updates and Maintenance

### Create Update Script
```bash
#!/bin/bash
# Update bot to latest version

echo "[INFO] Starting update script for ai_tg_bot..."
cd /root/ai_tg_bot || { echo '[ERROR] Failed to cd to /root/ai_tg_bot'; exit 1; }

echo "[INFO] Stopping ai-tg-bot service..."
systemctl stop ai-tg-bot

echo "[INFO] Backing up current version..."
cp -r . ../ai_tg_bot_backup_$(date +%Y%m%d)

echo "[INFO] Pulling latest changes from git..."
git pull origin main

echo "[INFO] Activating virtual environment..."
source venv/bin/activate

echo "[INFO] Updating Python dependencies..."
pip install --upgrade -r requirements.txt

echo "[INFO] Starting ai-tg-bot service..."
systemctl start ai-tg-bot

echo "[SUCCESS] $(date): Bot updated and restarted."
```

Make executable:
```bash
chmod +x /root/update.sh
```

## 8. Troubleshooting

### Check Bot Status
```bash
# Check systemd service
systemctl status ai-tg-bot

# View logs
journalctl -u ai-tg-bot -f

# Check if bot process is running
pgrep -f "python main.py"

# Check container resources
lxc info ai-tg-bot
```

### Useful Commands
```bash
# Restart the bot
systemctl restart ai-tg-bot

# View real-time logs
journalctl -u ai-tg-bot -f

# Check resource usage
htop

# Container management
lxc list
lxc stop ai-tg-bot
lxc start ai-tg-bot
```

## Support

If you encounter issues:
1. Check the logs: `journalctl -u ai-tg-bot -f`
2. Verify API keys and environment variables
3. Check container resource usage
4. Review the troubleshooting section above

The bot should now run continuously with automatic restarts, monitoring, and backups!