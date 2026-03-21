# Dashboard Commands

## View Dashboard in Terminal

```bash
# Simple text dashboard
openclaw run skill finance-tracker --script dashboard_slack.py

# Or directly:
python3 ~/.openclaw/workspace/skills/finance-tracker/scripts/dashboard_slack.py
```

## View as JSON

```bash
python3 ~/.openclaw/workspace/skills/finance-tracker/scripts/dashboard_slack.py --json
```

## Web Dashboard

```bash
# Start web server
python3 ~/.openclaw/workspace/skills/finance-tracker/scripts/dashboard.py

# Then open in browser:
# http://localhost:8080
```

## Automatic Slack Reports

Cron jobs automatically send reports:
- **Trading signals**: 8:00, 13:00, 16:00 GMT (Mon-Fri)
- **Daily summary**: 9:00 GMT (Mon-Fri)

## Files

- `memory/trading.db` - SQLite database with all trades
- `skills/finance-tracker/scripts/dashboard.py` - Web dashboard
- `skills/finance-tracker/scripts/dashboard_slack.py` - Terminal/Slack reports