# How to Start the Optimized Bot

## Prerequisites

### 1. Accept Xcode License (One-time setup)
```bash
sudo xcodebuild -license accept
```

### 2. Install orjson for faster JSON parsing (Optional but recommended)
```bash
pip install orjson
```

## Starting the Bot

### Option 1: Standard start
```bash
python main.py
```

### Option 2: Background with logging
```bash
python main.py > logs/bot.log 2>&1 &
```

### Option 3: With nohup (survives terminal close)
```bash
nohup python main.py > logs/bot.log 2>&1 &
```

## Stopping the Bot

```bash
pkill -f "python.*main.py"
```

## Checking Bot Status

```bash
ps aux | grep "python.*main.py" | grep -v grep
```

## Viewing Logs

```bash
tail -f logs/bot.log
```

## Troubleshooting

### Bot won't start
1. Check if Xcode license is accepted:
   ```bash
   xcodebuild -version
   ```
   If it asks for license agreement, run:
   ```bash
   sudo xcodebuild -license accept
   ```

2. Check Python version (should be 3.13+):
   ```bash
   python --version
   ```

3. Check if required packages are installed:
   ```bash
   pip list | grep -E "aiogram|openai|aiosqlite"
   ```

### Performance not improved
1. Check if orjson is installed:
   ```bash
   python -c "import orjson; print('orjson installed')"
   ```

2. Check provider cache warming in logs:
   ```bash
   grep "Pre-warmed provider" logs/bot.log
   ```

3. Run speed test in bot:
   ```
   /speedtest
   ```

