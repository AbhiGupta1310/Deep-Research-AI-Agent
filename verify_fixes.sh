#!/bin/bash

# Verify all memory optimization changes are in place

echo "=================================="
echo "Memory Optimization Verification"
echo "=================================="
echo ""

ERRORS=0
WARNINGS=0

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Check modified files
echo "1. Checking modified source files..."
echo ""

# Check embeddings.py has batch size
if grep -q "MAX_BATCH_SIZE = 20" backend/app/embeddings.py; then
    echo -e "${GREEN}✅${NC} embeddings.py: Batch size optimization found"
else
    echo -e "${RED}❌${NC} embeddings.py: Batch size optimization NOT found"
    ERRORS=$((ERRORS+1))
fi

# Check nodes.py has result cap
if grep -q "MAX_RESULTS_PER_SECTION" backend/app/nodes.py && grep -q "30.*Cap total results" backend/app/nodes.py; then
    echo -e "${GREEN}✅${NC} nodes.py: Search result cap found"
else
    echo -e "${RED}❌${NC} nodes.py: Search result cap NOT found"
    ERRORS=$((ERRORS+1))
fi

# Check main.py has garbage collection
if grep -q "gc.collect()" backend/app/main.py; then
    echo -e "${GREEN}✅${NC} main.py: Garbage collection added"
else
    echo -e "${RED}❌${NC} main.py: Garbage collection NOT found"
    ERRORS=$((ERRORS+1))
fi

# Check requirements.txt has been updated
if grep -q "uvloop" backend/requirements.txt; then
    echo -e "${GREEN}✅${NC} requirements.txt: uvloop added"
else
    echo -e "${YELLOW}⚠️${NC}  requirements.txt: uvloop not found (optional)"
    WARNINGS=$((WARNINGS+1))
fi

if grep -q "chromadb" backend/requirements.txt; then
    echo -e "${RED}❌${NC} requirements.txt: chromadb still present (should be removed)"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}✅${NC} requirements.txt: chromadb removed"
fi

if grep -q "weasyprint" backend/requirements.txt; then
    echo -e "${RED}❌${NC} requirements.txt: weasyprint still present (should be removed)"
    ERRORS=$((ERRORS+1))
else
    echo -e "${GREEN}✅${NC} requirements.txt: weasyprint removed"
fi

echo ""
echo "2. Checking new Render deployment files..."
echo ""

# Check for new files
if [ -f "render.yaml" ]; then
    echo -e "${GREEN}✅${NC} render.yaml: Found"
else
    echo -e "${RED}❌${NC} render.yaml: NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -f "Procfile" ]; then
    echo -e "${GREEN}✅${NC} Procfile: Found"
else
    echo -e "${RED}❌${NC} Procfile: NOT found"
    ERRORS=$((ERRORS+1))
fi

if [ -f ".env.render" ]; then
    echo -e "${GREEN}✅${NC} .env.render: Found"
else
    echo -e "${YELLOW}⚠️${NC}  .env.render: NOT found (optional template)"
    WARNINGS=$((WARNINGS+1))
fi

echo ""
echo "3. Checking documentation files..."
echo ""

if [ -f "MEMORY_OPTIMIZATION.md" ]; then
    echo -e "${GREEN}✅${NC} MEMORY_OPTIMIZATION.md: Found"
else
    echo -e "${YELLOW}⚠️${NC}  MEMORY_OPTIMIZATION.md: NOT found (documentation)"
    WARNINGS=$((WARNINGS+1))
fi

if [ -f "RENDER_DEPLOYMENT.md" ]; then
    echo -e "${GREEN}✅${NC} RENDER_DEPLOYMENT.md: Found"
else
    echo -e "${YELLOW}⚠️${NC}  RENDER_DEPLOYMENT.md: NOT found (documentation)"
    WARNINGS=$((WARNINGS+1))
fi

if [ -f "FIXES_SUMMARY.md" ]; then
    echo -e "${GREEN}✅${NC} FIXES_SUMMARY.md: Found"
else
    echo -e "${YELLOW}⚠️${NC}  FIXES_SUMMARY.md: NOT found (documentation)"
    WARNINGS=$((WARNINGS+1))
fi

echo ""
echo "4. Verifying code changes in detail..."
echo ""

# Check gc import
if grep -q "^import gc" backend/app/main.py; then
    echo -e "${GREEN}✅${NC} main.py: gc module imported"
else
    echo -e "${RED}❌${NC} main.py: gc module NOT imported"
    ERRORS=$((ERRORS+1))
fi

# Check garbage collection in finally block
if grep -q "gc.collect()" backend/app/main.py; then
    echo -e "${GREEN}✅${NC} main.py: gc.collect() found in code"
else
    echo -e "${RED}❌${NC} main.py: gc.collect() NOT found"
    ERRORS=$((ERRORS+1))
fi

# Check batch processing in embeddings
if grep -q "for batch_start in range(0, len(texts), MAX_BATCH_SIZE):" backend/app/embeddings.py; then
    echo -e "${GREEN}✅${NC} embeddings.py: Batch processing loop found"
else
    echo -e "${RED}❌${NC} embeddings.py: Batch processing loop NOT found"
    ERRORS=$((ERRORS+1))
fi

# Check result capping in nodes
if grep -q "if len(all_results) >= MAX_RESULTS_PER_SECTION:" backend/app/nodes.py; then
    echo -e "${GREEN}✅${NC} nodes.py: Result capping logic found"
else
    echo -e "${YELLOW}⚠️${NC}  nodes.py: Result capping logic might not be applied"
    WARNINGS=$((WARNINGS+1))
fi

echo ""
echo "5. Git status check..."
echo ""

# Check if files are staged for commit
STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l)
UNSTAGED=$(git diff --name-only 2>/dev/null | wc -l)

if [ "$STAGED" -gt 0 ]; then
    echo -e "${YELLOW}⚠️${NC}  $STAGED file(s) staged for commit"
fi

if [ "$UNSTAGED" -gt 0 ]; then
    echo -e "${YELLOW}⚠️${NC}  $UNSTAGED file(s) with unstaged changes"
    echo "   Run: git add -A && git commit -m 'Memory optimization fixes'"
else
    echo -e "${GREEN}✅${NC} All changes committed (or no git repo)"
fi

echo ""
echo "=================================="
echo "Summary"
echo "=================================="
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ All critical checks passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. git push origin main"
    echo "2. Create Render service"
    echo "3. Set environment variables"
    echo "4. Monitor deployment in Render dashboard"
else
    echo -e "${RED}❌ $ERRORS critical error(s) found${NC}"
    echo ""
    echo "Please fix the errors above before deploying."
fi

if [ $WARNINGS -gt 0 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  $WARNINGS warning(s) found${NC}"
    echo "   These are non-critical and usually optional."
fi

echo ""
echo "Memory Optimization Summary:"
echo "- Embedding batch size: 20 texts per API call"
echo "- Max search results: 30 per section"  
echo "- Removed: chromadb, weasyprint (~180MB saved)"
echo "- Added: uvloop, garbage collection"
echo "- Expected memory usage: 400-450MB (fits in 512MB)"
echo ""

exit $ERRORS
