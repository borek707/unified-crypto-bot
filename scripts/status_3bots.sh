#!/bin/bash
# Quick status check for 3 paper trading bots

echo "======================================================================"
echo "🤖 3 BOTS PAPER TRADING - STATUS"
echo "======================================================================"
echo ""

# Show results from JSON
python3 -c "
import json
from pathlib import Path

results_file = Path('~/.openclaw/workspace/memory/paper_trading_results.json').expanduser()
if results_file.exists():
    with open(results_file) as f:
        data = json.load(f)
    
    print('📊 LAST SIMULATION RESULTS')
    print('-'*60)
    for r in data['results']:
        emoji = '🟢' if r['name'] == 'LOW' else '🟡' if r['name'] == 'MEDIUM' else '🔴'
        pnl_emoji = '🟢' if r['pnl'] >= 0 else '🔴'
        print(f\"{emoji} {r['name']:<10} ${r['final']:<8.2f} ({r['return_pct']:+>6.2f}%) {pnl_emoji} ${r['pnl']:+>7.2f} | {r['trades']} trades\")
    
    print('-'*60)
    winner = max(data['results'], key=lambda x: x['return_pct'])
    print(f\"🏆 Winner: {winner['name']} ({winner['return_pct']:+.2f}%)\")
else:
    print('No results yet. Run: python3 run_3bots_paper.py')
"

echo ""
echo "======================================================================"
echo "📁 Logi bota:"
echo "======================================================================"
echo "  🟢 LOW:    ~/.openclaw/workspace/memory/passivbot_logs/low/bot.log"
echo "  🟡 MEDIUM: ~/.openclaw/workspace/memory/passivbot_logs/medium/bot.log"
echo "  🔴 HIGH:   ~/.openclaw/workspace/memory/passivbot_logs/high/bot.log"
echo ""
echo "Komendy:"
echo "  • Podgląd logów: tail -f ~/.openclaw/workspace/memory/passivbot_logs/*/bot.log"
echo "  • Dashboard:     python3 ~/.openclaw/workspace/bot_monitor.py"
echo "  • Raport HTML:   python3 ~/.openclaw/workspace/generate_dashboard.py"
echo "======================================================================"
