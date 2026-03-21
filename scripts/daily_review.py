#!/usr/bin/env python3
"""
Daily Incident Tracker & Auto-Fix System
========================================
Śledzi problemy z dnia poprzedniego i próbuje je naprawić automatycznie.

Użycie:
    python3 daily_review.py              # Analiza wczorajszego dnia + auto-fix
    python3 daily_review.py --report     # Tylko raport
    python3 daily_review.py --fix        # Tylko naprawy
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

INCIDENTS_DB = Path('~/.openclaw/workspace/memory/incidents.json').expanduser()
AUTO_FIX_LOG = Path('~/.openclaw/workspace/memory/auto_fixes.log').expanduser()


def load_incidents():
    """Load incidents database."""
    if INCIDENTS_DB.exists():
        with open(INCIDENTS_DB, 'r') as f:
            return json.load(f)
    return {}


def save_incidents(incidents):
    """Save incidents database."""
    INCIDENTS_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(INCIDENTS_DB, 'w') as f:
        json.dump(incidents, f, indent=2)


def log_incident(category, description, severity="medium", auto_fixable=False, fix_command=None):
    """Log a new incident."""
    incidents = load_incidents()
    today = datetime.now().strftime('%Y-%m-%d')
    
    if today not in incidents:
        incidents[today] = []
    
    incident = {
        'timestamp': datetime.now().isoformat(),
        'category': category,
        'description': description,
        'severity': severity,
        'auto_fixable': auto_fixable,
        'fix_command': fix_command,
        'status': 'open',
        'fix_attempts': 0
    }
    
    incidents[today].append(incident)
    save_incidents(incidents)
    print(f"📝 Logged incident: [{category}] {description}")


def analyze_logs():
    """Analyze yesterday's logs for issues."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    issues = []
    
    # Check bot logs for errors
    log_files = [
        '~/.openclaw/workspace/memory/passivbot_logs/unified_bot.log',
        '~/.openclaw/workspace/memory/passivbot_logs/low/live.log',
        '~/.openclaw/workspace/memory/passivbot_logs/medium/live.log',
        '~/.openclaw/workspace/memory/passivbot_logs/high/live.log',
    ]
    
    for log_file in log_files:
        log_path = Path(log_file).expanduser()
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Look for errors
            error_patterns = [
                (r'ERROR.*Failed to connect', 'API Connection Failed', True, 'restart_bots'),
                (r'ERROR.*initialize exchange', 'Exchange Init Failed', True, 'restart_bots'),
                (r'CRITICAL|FATAL', 'Critical Error', False, None),
                (r'Could not save state', 'State Save Failed', False, None),
                (r'Could not load state', 'State Load Failed', False, None),
            ]
            
            for pattern, desc, auto_fix, fix_cmd in error_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Count occurrences
                    count = len(re.findall(pattern, content, re.IGNORECASE))
                    if count > 0:
                        issues.append({
                            'source': log_path.name,
                            'description': f"{desc} ({count}x)",
                            'auto_fixable': auto_fix,
                            'fix_command': fix_cmd
                        })
    
    # Check if bots were down
    pids = Path('~/.openclaw/workspace/bot_low.pid').expanduser()
    if pids.exists():
        try:
            pid = int(pids.read_text().strip())
            result = subprocess.run(['ps', '-p', str(pid)], capture_output=True)
            if result.returncode != 0:
                issues.append({
                    'source': 'bot_monitor',
                    'description': 'Bot process not running (crashed?)',
                    'auto_fixable': True,
                    'fix_command': 'restart_bots'
                })
        except:
            pass
    
    return issues


def attempt_auto_fix(issue):
    """Attempt to auto-fix an issue."""
    fix_commands = {
        'restart_bots': 'cd ~/.openclaw/workspace && ./start_bots_with_api.sh',
        'clear_cache': 'rm -rf ~/.openclaw/workspace/.cache/*',
        'reset_state': 'rm ~/.openclaw/workspace/memory/bot_state.json ~/.openclaw/workspace/memory/bot_price_history.json',
    }
    
    cmd = issue.get('fix_command')
    if cmd and cmd in fix_commands:
        try:
            print(f"🔧 Attempting auto-fix: {cmd}")
            result = subprocess.run(
                fix_commands[cmd],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ Auto-fix succeeded: {cmd}")
                return True, result.stdout
            else:
                print(f"❌ Auto-fix failed: {result.stderr}")
                return False, result.stderr
                
        except Exception as e:
            print(f"❌ Auto-fix error: {e}")
            return False, str(e)
    
    return False, "No auto-fix available"


def generate_daily_review():
    """Generate daily review report."""
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    print(f"\n{'='*60}")
    print(f"📊 DAILY REVIEW: {yesterday}")
    print(f"{'='*60}\n")
    
    # Analyze yesterday's logs
    print("🔍 Analyzing yesterday's logs...")
    issues = analyze_logs()
    
    if not issues:
        print("✅ No issues found - smooth day!")
        return
    
    print(f"\n⚠️  Found {len(issues)} issue(s):\n")
    
    for i, issue in enumerate(issues, 1):
        fixable = "🤖 Auto-fixable" if issue['auto_fixable'] else "👤 Manual fix needed"
        print(f"  {i}. [{issue['source']}] {issue['description']}")
        print(f"     → {fixable}\n")
    
    # Load previous incidents
    incidents = load_incidents()
    
    if yesterday in incidents:
        print(f"📋 Yesterday's logged incidents: {len(incidents[yesterday])}")
    
    # Check for recurring issues
    print("\n🔄 Checking for recurring issues...")
    recurring = []
    
    for issue in issues:
        desc = issue['description']
        # Check if similar issue was in last 7 days
        for day in [(datetime.now() - timedelta(days=d)).strftime('%Y-%m-%d') 
                    for d in range(2, 8)]:
            if day in incidents:
                for inc in incidents[day]:
                    if issue['description'] in inc['description'] and inc['status'] != 'fixed':
                        recurring.append({
                            'issue': issue,
                            'first_seen': day,
                            'previous_attempts': inc.get('fix_attempts', 0)
                        })
    
    if recurring:
        print(f"\n🚨 RECURRING ISSUES ({len(recurring)}):")
        for r in recurring:
            print(f"  - {r['issue']['description']} (first seen: {r['first_seen']}, attempts: {r['previous_attempts']})")
    
    # Attempt auto-fixes
    print(f"\n🔧 ATTEMPTING AUTO-FIXES:\n")
    fixed_count = 0
    
    for issue in issues:
        if issue['auto_fixable']:
            success, output = attempt_auto_fix(issue)
            
            # Log the attempt
            log_incident(
                category='auto_fix_attempt',
                description=f"{issue['description']} - {'SUCCESS' if success else 'FAILED'}",
                severity='low' if success else 'high',
                auto_fixable=False
            )
            
            if success:
                fixed_count += 1
        else:
            # Log for manual fix
            log_incident(
                category='manual_fix_needed',
                description=issue['description'],
                severity='medium',
                auto_fixable=False
            )
            print(f"  ⏸️  Manual fix needed: {issue['description']}")
    
    print(f"\n{'='*60}")
    print(f"📈 SUMMARY: {fixed_count}/{len(issues)} issues auto-fixed")
    print(f"{'='*60}\n")
    
    # Recommendations
    print("💡 RECOMMENDATIONS FOR TODAY:\n")
    
    if recurring:
        print("  1. PRIORITY: Fix recurring issues permanently:")
        for r in recurring[:3]:
            print(f"     - {r['issue']['description']}")
    
    if fixed_count < len(issues):
        print(f"\n  2. Manual fixes needed: {len(issues) - fixed_count}")
        print("     Check incidents.json for details")
    
    print("\n  3. Monitor bot stability throughout the day")
    print("     Use: ./check_bots.sh")


def main():
    parser = argparse.ArgumentParser(description='Daily Review & Auto-Fix System')
    parser.add_argument('--report', action='store_true', help='Only generate report')
    parser.add_argument('--fix', action='store_true', help='Only attempt fixes')
    parser.add_argument('--log', metavar='DESC', help='Log a manual incident')
    
    args = parser.parse_args()
    
    if args.log:
        log_incident('manual', args.log, 'medium', False)
        return
    
    generate_daily_review()


if __name__ == '__main__':
    main()
