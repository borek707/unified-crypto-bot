# Operations Manual

## Daily Operations

### Morning Routine (5 min)

```bash
# 1. Check bot status
./scripts/status.sh

# 2. Review overnight activity
grep -E "(OPEN|CLOSE|TREND CHANGE|CIRCUIT)" memory/bot_dashboard.html 2>/dev/null || \
  grep -E "(OPEN|CLOSE|TREND CHANGE|CIRCUIT)" ~/.crypto_bot/logs/unified_bot.log | tail -50

# 3. Check daily report
python3 daily_report.py

# 4. Check paper trading results
cat memory/paper_trading_results.json | python3 -m json.tool | tail -30
```

### Health Indicators

| Indicator | Good | Warning | Critical |
|-----------|------|---------|----------|
| Bot processes | 3 running | 2 running | 0-1 running |
| Last price update | < 2 min | 2-15 min | > 15 min |
| Daily PnL | > 0% | -5% to 0% | < -5% |
| Database size | < 100MB | 100-500MB | > 500MB |
| Disk space | > 20% | 10-20% | < 10% |

## Weekly Maintenance

### Every Monday

```bash
# 1. Review weekly performance (manual, no automated script)
cat memory/paper_trading_results.json | python3 -m json.tool

# 2. Archive old logs
find ~/.crypto_bot/logs -name "*.log" -mtime +7 -exec gzip {} \;

# 3. Update dependencies
pip install --upgrade -r requirements.txt
```

### Strategy Review

Every Sunday evening:

1. **Check win rate by strategy**:
   ```sql
   SELECT 
     strategy,
     COUNT(*) as trades,
     SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
     ROUND(AVG(pnl), 2) as avg_pnl
   FROM trades 
   WHERE timestamp > datetime('now', '-7 days')
   GROUP BY strategy;
   ```

2. **Adjust parameters if needed**:
   - If sideways win rate < 50%: widen grid spacing
   - If short losses > 30%: reduce leverage
   - If missing trends: lower threshold

## Monthly Tasks

### Performance Analysis

```bash
# Generate monthly report
python3 scripts/monthly_report.py --month $(date +%Y-%m)
```

Review metrics:
- Total return vs. buy & hold
- Sharpe ratio
- Max drawdown
- Win rate by trend
- Average trade duration

### Security Audit

```bash
# Check for unauthorized access
last | head -20
grep "Failed password" /var/log/auth.log | tail -20

# Rotate API keys (if needed)
# Update .env and restart bots
./scripts/restart_bots.sh

# Review firewall rules
sudo ufw status verbose
```

## Incident Response

### Level 1: Bot Stopped

```bash
# Auto-restart
crontab -l | grep health_check

# Manual restart
./scripts/start_bots.sh

# Verify
sleep 5 && ps aux | grep unified_bot
```

### Level 2: Rate Limited

```bash
# Check current state
cat .api_rate_state.json

# Reset if needed
echo '{}' > .api_rate_state.json

# Wait 15 minutes
# No manual action needed - auto-resolves
```

### Level 3: Large Loss (>5% in 1 hour) / Circuit Breaker Active

```bash
# Emergency stop
./scripts/stop_bots.sh

# Check if circuit breaker fired
grep "CIRCUIT BREAKER" ~/.crypto_bot/logs/unified_bot.log | tail -5

# Check current bot state
cat memory/bot_state.json | python3 -m json.tool

# Decision: Restart or wait for cooldown
# Circuit Breaker auto-resets after 60 min cooldown
```

### Level 4: Exchange Issues

```bash
# Check exchange status
curl https://status.hyperliquid.xyz/

# Switch to backup exchange (if configured)
# Or wait for resolution

# Monitor: Every 5 minutes until resolved
watch -n 300 './scripts/status.sh'
```

## Configuration Changes

### Adding a New Bot

```bash
# 1. Create config based on existing profile
cp config_medium_risk.json config_custom.json
nano config_custom.json

# 2. Test in paper mode
python3 skills/passivbot-micro/scripts/unified_bot.py --config config_custom.json --testnet

# 3. Start live
nohup python3 skills/passivbot-micro/scripts/unified_bot.py --config config_custom.json --live \
  >> ~/.crypto_bot/logs/custom.log 2>&1 &
```

### Modifying Strategy Parameters

1. **Edit config file**:
   ```bash
   nano config_low_risk.json
   ```

2. **Validate JSON**:
   ```bash
   python3 -m json.tool config_low_risk.json > /dev/null && echo "Valid JSON"
   ```

3. **Restart bot**:
   ```bash
   pkill -f "unified_bot.py.*low_risk"
   sleep 2
   nohup python3 skills/passivbot-micro/scripts/unified_bot.py \
     --config config_low_risk.json --live >> ~/.crypto_bot/logs/low.log 2>&1 &
   ```

4. **Monitor for 1 hour**:
   ```bash
   tail -f ~/.crypto_bot/logs/low.log | grep -E "(ERROR|OPEN|CLOSE|CIRCUIT|TREND)"
   ```

## Log Analysis

### Common Patterns

```bash
# Find all trades
grep "OPEN\|CLOSE" ~/.crypto_bot/logs/unified_bot.log

# Find errors
grep "ERROR" ~/.crypto_bot/logs/unified_bot.log | tail -20

# Check trend changes
grep "TREND CHANGE" ~/.crypto_bot/logs/unified_bot.log

# Check circuit breaker events
grep "CIRCUIT BREAKER" ~/.crypto_bot/logs/unified_bot.log

# Rate limit hits
grep "Rate limit" ~/.crypto_bot/logs/unified_bot.log
```

### Performance Metrics

```bash
# Trades per day
sqlite3 memory/trades.db "SELECT date(timestamp), COUNT(*) FROM trades GROUP BY date(timestamp);"

# PnL by day
sqlite3 memory/trades.db "SELECT date(timestamp), ROUND(SUM(pnl), 2) FROM trades GROUP BY date(timestamp);"

# Win rate
sqlite3 memory/trades.db "SELECT 
  ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as win_rate
FROM trades;"
```

## Backup Verification

```bash
# Weekly: Test restore on backup
#!/bin/bash
# scripts/test_backup.sh

BACKUP=$(ls -t /backups/crypto-bot/*.gz | head -1)
TMP_DIR=$(mktemp -d)

# Restore to temp
gunzip -c "$BACKUP" > "$TMP_DIR/test.db"

# Verify
if sqlite3 "$TMP_DIR/test.db" "SELECT COUNT(*) FROM crypto_prices;" > /dev/null; then
    echo "✓ Backup OK: $BACKUP"
else
    echo "✗ Backup corrupt: $BACKUP"
    # Alert admin
fi

rm -rf "$TMP_DIR"
```

## Communication

### Slack Integration

Set up alerts for:
- Bot stops/resets
- Daily PnL < -5%
- Rate limit errors
- Database errors

### Email Alerts

```bash
# Critical: Immediate
# Warning: Every 4 hours
# Info: Daily digest
```

## Runbook Templates

### Template: Market Volatility Spike

**Trigger**: BTC moves >10% in 1 hour

**Actions**:
1. Check all bot positions
2. Verify stop-losses are active
3. Monitor liquidation levels (short positions)
4. Consider pausing new entries
5. Document in incident log

### Template: Exchange Maintenance

**Trigger**: Exchange announces maintenance

**Actions**:
1. Note maintenance window
2. Verify no open orders at maintenance time
3. Monitor bot behavior during reconnect
4. Check for order state mismatches after

## Documentation Updates

When making changes:

1. Update this file (OPERATIONS.md)
2. Update ARCHITECTURE.md if structural changes
3. Update DEPLOYMENT.md if infra changes
4. Commit with message: `docs: update operations for X`
5. Notify team in Slack

## Contact Information

| Role | Contact | Escalation |
|------|---------|------------|
| Primary | admin@example.com | Immediate |
| Secondary | backup@example.com | 30 min |
| Exchange | support@hyperliquid.xyz | Exchange issues |

---

Last updated: 2026-03-18