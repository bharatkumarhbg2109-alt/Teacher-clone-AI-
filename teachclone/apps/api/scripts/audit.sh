#!/bin/bash
set -e
echo "Running Python dependency audit..."
pip-audit -r requirements.txt --progress-spinner off
echo ""
echo "Running frontend dependency audit..."
cd ../web
npm audit --audit-level=high
echo ""
echo "All audits passed."
