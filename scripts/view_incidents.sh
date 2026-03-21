#!/bin/bash
# Quick incident viewer

echo "📋 INCIDENTS DATABASE"
echo "===================="
echo ""

if [ -f ~/.openclaw/workspace/memory/incidents.json ]; then
    python3 -c "
import json
from pathlib import Path
import sys

path = Path.home() / '.openclaw/workspace/memory/incidents.json'
if not path.exists():
    print('No incidents database found')
    sys.exit(0)

with open(path) as f:
    data = json.load(f)

if not data:
    print('No incidents logged')
    sys.exit(0)

for date in sorted(data.keys())[-7:]:  # Last 7 days
    incidents = data[date]
    print(f'\\n📅 {date}: {len(incidents)} incident(s)')
    
    for inc in incidents:
        status = inc.get('status', 'unknown')
        emoji = '✅' if status == 'fixed' else '🔴' if status == 'open' else '⏸️'
        severity = inc.get('severity', 'unknown')
        cat = inc.get('category', 'unknown')
        desc = inc.get('description', 'no description')[:60]
        print(f'   {emoji} [{severity.upper()}] [{cat}] {desc}...')
"
else
    echo "No incidents database found"
fi

echo ""
echo "Commands:"
echo "  daily_review.py       # Run full analysis"
echo "  daily_review.py --log 'description'  # Log manual incident"
echo "  cat memory/incidents.json  # View raw data"
