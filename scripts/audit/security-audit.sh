#!/usr/bin/env bash
# Security audit script for ChemEng dependencies
# Usage: bash scripts/audit/security-audit.sh
set -euo pipefail

echo "=== ChemEng Security Audit ==="
echo ""

# Check pip-audit is available
if ! command -v pip-audit &> /dev/null; then
    echo "Installing pip-audit..."
    pip install pip-audit --quiet
fi

# Run pip-audit in strict mode
# Exit code 1 = vulnerabilities found, 0 = clean
pip-audit --desc --fix --dry-run 2>&1 | tee /tmp/audit-output.txt
AUDIT_EXIT=${PIPESTATUS[0]}

echo ""

if [ "$AUDIT_EXIT" -eq 0 ]; then
    echo "✅ No vulnerabilities found."
    exit 0
fi

# Check for known/accepted advisories
python3 scripts/audit/check_known.py /tmp/audit-output.txt
