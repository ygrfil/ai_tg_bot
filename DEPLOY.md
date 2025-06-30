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
apt install -y curl wget git python3 python3-pip python3-venv supervisor nginx htop nano
```

## 2. Setup Application User

```bash
# Create dedicated user for the bot
useradd -m -s /bin/bash botuser
usermod -aG sudo botuser

# Switch to bot user
su - botuser
```

## 3. Clone and Setup Application

```bash
# Clone the repository
git clone https://github.com/ygrfil/ai_tg_bot.git
cd ai_tg_bot

# Switch to openrouter branch
git checkout openrouter

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure Environment

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

## 5. Create Systemd Service (Recommended Method)

Exit to root user and create service file:
```bash
exit  # Exit from botuser
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
User=botuser
Group=botuser
WorkingDirectory=/home/botuser/ai_tg_bot
Environment=PATH=/home/botuser/ai_tg_bot/venv/bin
ExecStart=/home/botuser/ai_tg_bot/venv/bin/python main.py
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
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/botuser/ai_tg_bot/data

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

## 6. Alternative: Supervisor Configuration

If you prefer Supervisor over systemd:

```bash
# Create supervisor configuration
nano /etc/supervisor/conf.d/ai-tg-bot.conf
```

Add the following:
```ini
[program:ai-tg-bot]
command=/home/botuser/ai_tg_bot/venv/bin/python main.py
directory=/home/botuser/ai_tg_bot
user=botuser
group=botuser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/ai-tg-bot.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
environment=PATH="/home/botuser/ai_tg_bot/venv/bin"
```

Start with Supervisor:
```bash
# Update supervisor configuration
supervisorctl reread
supervisorctl update

# Start the bot
supervisorctl start ai-tg-bot

# Check status
supervisorctl status ai-tg-bot
```

## 7. Setup Logging and Monitoring

### Configure Log Rotation
```bash
nano /etc/logrotate.d/ai-tg-bot
```

Add:
```
/var/log/ai-tg-bot.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 botuser botuser
    postrotate
        systemctl reload ai-tg-bot
    endscript
}
```

### Create Monitoring Script
```bash
nano /home/botuser/monitor.sh
```

Add:
```bash
#!/bin/bash
# Monitor bot health and restart if needed

BOT_PID=$(pgrep -f "python main.py")
if [ -z "$BOT_PID" ]; then
    echo "$(date): Bot is not running, restarting..."
    systemctl restart ai-tg-bot
    sleep 10
    
    # Check if restart was successful
    BOT_PID=$(pgrep -f "python main.py")
    if [ -z "$BOT_PID" ]; then
        echo "$(date): Failed to restart bot, sending alert..."
        # Add your alerting mechanism here (email, webhook, etc.)
    else
        echo "$(date): Bot restarted successfully with PID $BOT_PID"
    fi
else
    echo "$(date): Bot is running with PID $BOT_PID"
fi
```

Make it executable and add to cron:
```bash
chmod +x /home/botuser/monitor.sh
chown botuser:botuser /home/botuser/monitor.sh

# Add to crontab (check every 5 minutes)
crontab -u botuser -e
```

Add this line:
```
*/5 * * * * /home/botuser/monitor.sh >> /var/log/bot-monitor.log 2>&1
```

## 8. Container Auto-Start Configuration

On the host system, configure the container to start automatically:

```bash
# Enable auto-start for the container
lxc config set ai-tg-bot boot.autostart true

# Set startup priority (optional)
lxc config set ai-tg-bot boot.autostart.priority 10

# Set startup delay (optional)
lxc config set ai-tg-bot boot.autostart.delay 30
```

## 9. Resource Limits and Optimization

Configure container resource limits:
```bash
# Set memory limit (adjust based on your needs)
lxc config set ai-tg-bot limits.memory 1GB

# Set CPU limit (optional)
lxc config set ai-tg-bot limits.cpu 2

# Set disk limits (optional)
lxc config device override ai-tg-bot root size=10GB
```

## 10. Backup and Maintenance

### Create Backup Script
```bash
nano /home/botuser/backup.sh
```

Add:
```bash
#!/bin/bash
# Backup bot data and configuration

BACKUP_DIR="/home/botuser/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database and configuration
tar -czf $BACKUP_DIR/ai-tg-bot-backup-$DATE.tar.gz \
    /home/botuser/ai_tg_bot/data/ \
    /home/botuser/ai_tg_bot/.env \
    /home/botuser/ai_tg_bot/CLAUDE.md

# Keep only last 30 days of backups
find $BACKUP_DIR -name "ai-tg-bot-backup-*.tar.gz" -mtime +30 -delete

echo "$(date): Backup completed: ai-tg-bot-backup-$DATE.tar.gz"
```

Add to crontab (daily backup):
```bash
0 2 * * * /home/botuser/backup.sh >> /var/log/bot-backup.log 2>&1
```

## 11. Updates and Maintenance

### Create Update Script
```bash
nano /home/botuser/update.sh
```

Add:
```bash
#!/bin/bash
# Update bot to latest version

cd /home/botuser/ai_tg_bot

# Stop the bot
systemctl stop ai-tg-bot

# Backup current version
cp -r . ../ai_tg_bot_backup_$(date +%Y%m%d)

# Pull latest changes
git pull origin openrouter

# Update dependencies
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Start the bot
systemctl start ai-tg-bot

echo "$(date): Bot updated and restarted"
```

## 12. Troubleshooting

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

### Common Issues

1. **Bot not starting**: Check .env file permissions and API keys
2. **Database errors**: Ensure data directory has proper permissions
3. **Memory issues**: Increase container memory limit
4. **Network issues**: Check container network configuration

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

## 13. Security Considerations

1. **Firewall**: Configure firewall rules to limit access
2. **User permissions**: Run bot as non-root user
3. **API keys**: Keep .env file secure (600 permissions)
4. **Updates**: Regularly update system and dependencies
5. **Monitoring**: Set up alerts for failures

## 14. Performance Optimization

1. **SSD Storage**: Use SSD for container storage
2. **Memory**: Allocate sufficient RAM (1-2GB recommended)
3. **CPU**: Ensure adequate CPU resources
4. **Network**: Good internet connection for API calls

## Support

If you encounter issues:
1. Check the logs: `journalctl -u ai-tg-bot -f`
2. Verify API keys and environment variables
3. Check container resource usage
4. Review the troubleshooting section above

The bot should now run continuously with automatic restarts, monitoring, and backups!