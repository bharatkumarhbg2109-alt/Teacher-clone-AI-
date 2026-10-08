#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────
# TeachClone — Pre-Deploy CI Script
# Run this before every production deployment.
# Exit code 0 = all checks passed. Non-zero = deploy blocked.
#
# Usage:
#   bash scripts/pre-deploy.sh          # from project root
#   bash apps/api/scripts/pre-deploy.sh # from apps/api
# ──────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/apps/api"
WEB_DIR="$PROJECT_ROOT/apps/web"

PASS=0
FAIL=0
WARN=0
RESULTS=()

pass() { PASS=$((PASS + 1)); RESULTS+=("  ✅ $1"); }
fail() { FAIL=$((FAIL + 1)); RESULTS+=("  ❌ $1"); }
warn() { WARN=$((WARN + 1)); RESULTS+=("  ⚠️  $1"); }

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  TEACHCLONE — PRE-DEPLOY CHECKS"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "═══════════════════════════════════════════════════════════"
echo ""

# ── 1. Run backend tests ──────────────────────────────────────────────────
echo "▸ [1/7] Running backend tests..."
if cd "$API_DIR" && python -m pytest tests/ --tb=line -q 2>&1 | tail -5; then
    pass "Backend tests passed"
else
    fail "Backend tests FAILED"
fi
echo ""

# ── 2. Run frontend build ─────────────────────────────────────────────────
echo "▸ [2/7] Building frontend..."
if cd "$WEB_DIR" && npx next build 2>&1 | tail -3; then
    pass "Frontend build succeeded"
else
    fail "Frontend build FAILED"
fi
echo ""

# ── 3. Run Playwright E2E tests ──────────────────────────────────────────
echo "▸ [3/7] Running Playwright E2E tests..."
if cd "$WEB_DIR" && npx playwright test --reporter=line 2>&1 | tail -5; then
    pass "Playwright E2E tests passed"
else
    fail "Playwright E2E tests FAILED"
fi
echo ""

# ── 4. Check for hardcoded secrets ────────────────────────────────────────
echo "▸ [4/7] Scanning for hardcoded secrets..."

SECRETS_FOUND=0

# Exclusions for secrets scan
EXCLUDE="--exclude-dir=node_modules --exclude-dir=.next --exclude-dir=__pycache__ --exclude-dir=.venv --exclude-dir=venv --exclude-dir=test-results --exclude-dir=playwright-report"

# Check for real API keys (sk-ant-, sk-, pk_live-, sk_live-)
for pattern in "sk-ant-[a-zA-Z0-9]" "sk-[a-zA-Z0-9]{20,}" "pk_live_" "sk_live_" "ghp_[a-zA-Z0-9]"; do
    matches=$(grep -rn $EXCLUDE "$pattern" "$PROJECT_ROOT/apps/" \
        --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
        2>/dev/null \
        | grep -v "test_" | grep -v "conftest" \
        | grep -v "example\|placeholder\|your-\|change-me\|sk-ant-\.\.\." \
        || true)
    if [ -n "$matches" ]; then
        echo "  FOUND: $pattern"
        echo "$matches" | head -3
        SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
done

# Check for hardcoded passwords or connection strings (exclude .env.example)
for pattern in "password.*=.*['\"][a-zA-Z0-9]" "mongodb://\|postgres://\|mysql://"; do
    matches=$(grep -rn $EXCLUDE "$pattern" "$PROJECT_ROOT/apps/" \
        --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
        2>/dev/null \
        | grep -v "test_" | grep -v "conftest" | grep -v "example" \
        | grep -v "localhost\|127.0.0.1\|minioadmin" \
        || true)
    if [ -n "$matches" ]; then
        echo "  FOUND: $pattern"
        echo "$matches" | head -3
        SECRETS_FOUND=$((SECRETS_FOUND + 1))
    fi
done

if [ "$SECRETS_FOUND" -eq 0 ]; then
    pass "No hardcoded secrets found"
else
    fail "Found $SECRETS_FOUND potential secret(s) in source code"
fi
echo ""

# ── 5. Validate .env.example has no real values ───────────────────────────
echo "▸ [5/7] Validating .env.example..."
ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
ENV_ISSUES=0

if [ -f "$ENV_EXAMPLE" ]; then
    # Check that API key fields are empty or placeholder
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^# ]] && continue
        [[ -z "$line" ]] && continue

        # Extract key=value
        key="${line%%=*}"
        value="${line#*=}"

        # Check for real-looking API keys
        if echo "$key" | grep -qiE "KEY|SECRET|TOKEN|PASSWORD"; then
            if [ -n "$value" ] && [ "$value" != "" ] && [ "$value" != "change-me" ] && [ "$value" != "your-key-here" ]; then
                # Allow placeholder patterns
                if ! echo "$value" | grep -qE "^\.\.\.|^your_|^sk-test|^\$|placeholder|example|dev@|localhost"; then
                    echo "  ISSUE: $key has non-placeholder value: ${value:0:20}..."
                    ENV_ISSUES=$((ENV_ISSUES + 1))
                fi
            fi
        fi
    done < "$ENV_EXAMPLE"

    # Check that DATABASE_URL is not a production URL
    if grep -q "DATABASE_URL=postgresql" "$ENV_EXAMPLE" 2>/dev/null; then
        if ! grep -q "DATABASE_URL=postgresql.*localhost" "$ENV_EXAMPLE" 2>/dev/null; then
            echo "  ISSUE: DATABASE_URL points to non-local database"
            ENV_ISSUES=$((ENV_ISSUES + 1))
        fi
    fi

    if [ "$ENV_ISSUES" -eq 0 ]; then
        pass ".env.example has no real values"
    else
        fail ".env.example has $ENV_ISSUES potential real value(s)"
    fi
else
    warn ".env.example not found — skipping"
fi
echo ""

# ── 6. Check .gitignore covers secrets ───────────────────────────────────
echo "▸ [6/7] Checking .gitignore for secret coverage..."
GITISSUE=0

for pattern in "\.env$" "\.env\.local" "\.pem$" "\.key$"; do
    if ! grep -qE "$pattern" "$PROJECT_ROOT/.gitignore" 2>/dev/null; then
        echo "  MISSING: .gitignore does not cover $pattern"
        GITISSUE=$((GITISSUE + 1))
    fi
done

# Check that .env is not tracked by git
if cd "$PROJECT_ROOT" && git ls-files --error-unmatch .env 2>/dev/null; then
    echo "  CRITICAL: .env is tracked by git!"
    GITISSUE=$((GITISSUE + 1))
fi

if [ "$GITISSUE" -eq 0 ]; then
    pass ".gitignore properly covers secrets"
else
    fail ".gitignore has $GITISSUE issue(s)"
fi
echo ""

# ── 7. Check Docker config validity ──────────────────────────────────────
echo "▸ [7/7] Validating Docker Compose config..."
if command -v docker &>/dev/null && [ -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    if cd "$PROJECT_ROOT" && docker compose config --quiet 2>/dev/null; then
        pass "docker-compose.yml is valid"
    else
        fail "docker-compose.yml has errors"
    fi
elif [ ! -f "$PROJECT_ROOT/docker-compose.yml" ]; then
    warn "docker-compose.yml not found — skipping"
else
    warn "Docker not installed — skipping compose validation"
fi
echo ""

# ── Summary ──────────────────────────────────────────────────────────────
echo "═══════════════════════════════════════════════════════════"
echo "  PRE-DEPLOY RESULTS"
echo "═══════════════════════════════════════════════════════════"
for r in "${RESULTS[@]}"; do
    echo "$r"
done
echo ""
echo "  Total: $((PASS + FAIL + WARN)) checks | ✅ $PASS passed | ❌ $FAIL failed | ⚠️  $WARN warnings"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo "  🚫 DEPLOY BLOCKED — $FAIL check(s) failed"
    echo "═══════════════════════════════════════════════════════════"
    exit 1
else
    echo "  ✅ ALL CHECKS PASSED — safe to deploy"
    echo "═══════════════════════════════════════════════════════════"
    exit 0
fi
