#!/bin/bash
# Quick audit wrapper for OpenClaw

URL=$1

if [ -z "$URL" ]; then
    echo "Usage: ./quick-audit.sh <url>"
    echo "Example: ./quick-audit.sh https://example.com"
    exit 1
fi

echo "🔍 Running website audit for: $URL"
echo ""

cd /Users/alfred/.openclaw/workspace/audit-system
node run-audit.js "$URL"

echo ""
echo "✅ Audit complete! Check the reports/ directory for results."
