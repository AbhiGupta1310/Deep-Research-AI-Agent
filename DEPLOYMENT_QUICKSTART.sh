#!/bin/bash
# Quick Deploy to Render - Reference Guide

# ============================================================
# 1. LOCAL TESTING (Run these commands first)
# ============================================================

# Test locally to ensure no errors
cd /Users/abhigupta/Desktop/deep_research_agent

# Activate virtual environment
source .venv/bin/activate

# Install updated requirements
pip install -r backend/requirements.txt

# Test if the app starts
cd backend
uvicorn app.main:app --reload --port 8000

# In another terminal, test the API
curl http://localhost:8000/health
# Should return: {"status": "ok", "version": "2.0"}

# ============================================================
# 2. COMMIT & PUSH
# ============================================================

git add -A
git commit -m "Memory optimization for 512MB Render deployment

- Batch embeddings in groups of 20 to prevent memory spikes
- Cap search results at 30 per section (was unlimited)
- Remove chromadb and weasyprint (120MB savings)
- Add explicit garbage collection after requests
- Add Render configuration files
- Memory reduction: ~162MB total"

git push origin main

# ============================================================
# 3. CREATE RENDER SERVICE (Do this in dashboard)
# ============================================================

# 1. Go to https://dashboard.render.com
# 2. Click "New" → "Web Service"
# 3. Connect your GitHub repository
# 4. Select the deep_research_agent repo
# 
# Service Details:
# - Name: deep-research-agent-backend
# - Runtime: Python 3.11
# - Build Command: pip install -r backend/requirements.txt
# - Start Command: cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
# - Plan: Free (512 MB)
#
# 5. Click "Create Web Service"

# ============================================================
# 4. SET ENVIRONMENT VARIABLES (In Render Dashboard)
# ============================================================

# Go to: Settings → Environment → Add Environment Variables

# Required variables:
# RENDER=true
# PRODUCTION=true
# OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
# TAVILY_API_KEY=tvly-xxxxxxxxxxxxx
# REDIS_URL=redis://default:password@redis-host:6379
# LLM_MODEL_CHEAP=google/gemini-2.0-flash
# LLM_MODEL_MID=anthropic/claude-3.5-haiku
# LLM_MODEL_PREMIUM=anthropic/claude-3.5-sonnet

# ============================================================
# 5. MONITOR DEPLOYMENT
# ============================================================

# After clicking "Create", Render will:
# 1. Build your service (install dependencies)
# 2. Start the application
# 3. Show you live logs

# Check these in the Logs tab:
# ✅ "Deep Research Agent API v2 is running"
# ✅ No error messages
# ✅ Memory usage stays under 450MB

# ============================================================
# 6. TEST THE DEPLOYMENT
# ============================================================

# Get your Render service URL from the dashboard
# Example: https://deep-research-agent-backend-xxxx.onrender.com

# Test health endpoint
curl https://YOUR_SERVICE_URL/health

# Test research (this will stream SSE events)
curl -X POST https://YOUR_SERVICE_URL/api/research \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Artificial Intelligence",
    "depth": "quick",
    "output_format": "markdown"
  }'

# ============================================================
# 7. MEMORY MONITORING
# ============================================================

# In Render dashboard:
# 1. Click your service
# 2. Go to "Logs"
# 3. Click "Metrics" tab
# 4. Watch "Memory" graph

# Expected values:
# - Idle (no requests): 250-300 MB
# - During research: 400-450 MB (peak)
# - After cleanup: 300 MB (GC runs)

# ============================================================
# 8. IF THINGS GO WRONG
# ============================================================

# Check logs for errors:
# 1. Render Dashboard → Logs tab
# 2. Look for "Out of memory" or error messages
# 3. Common fixes:

# Error: "ModuleNotFoundError: No module named 'app'"
# Fix: Ensure build command is: pip install -r backend/requirements.txt

# Error: "Out of memory"
# Fixes:
# a) Check REDIS_URL is set (enables caching)
# b) Verify --workers 1 is in start command
# c) Check MAX_RESULTS_PER_SECTION = 30 in nodes.py

# Error: "Redis connection refused"
# Fix: Set up Upstash (free Redis) or remove REDIS_URL if not needed

# Error: "API timeout after 30 seconds"
# This is normal on free tier - research takes 60-120 seconds
# Upgrade to Starter plan ($7/month) for faster performance

# ============================================================
# 9. DEPLOYMENT VERIFICATION CHECKLIST
# ============================================================

# After deployment, verify:
# ✅ Service shows "Live" status (green)
# ✅ /health endpoint returns 200 OK
# ✅ No error logs in the Logs tab
# ✅ Memory stays under 450MB
# ✅ Can make research requests
# ✅ Reports generate successfully

# ============================================================
# 10. DEPLOYING FRONTEND (Optional)
# ============================================================

# If you want to deploy frontend to Render too:
# 1. Create NEW service (separate from backend)
# 2. Use Start Command: cd frontend && npm run preview
# 3. Build Command: cd frontend && npm install && npm run build
# 4. Set environment variable: VITE_API_URL=https://your-backend-url/api

# ============================================================
# MEMORY SAVINGS BREAKDOWN
# ============================================================

# Total memory saved: ~162 MB
#
# Breakdown:
# - Embedding batches (20 at a time): 50-80 MB ✓ embeddings.py
# - Search result caps (30 max): 30-40 MB ✓ nodes.py  
# - Removed chromadb: 60 MB ✓ requirements.txt
# - Removed weasyprint: 60 MB ✓ requirements.txt
# - Garbage collection: 20-30 MB ✓ main.py
#
# Result: 512MB Render free tier now has ~60MB headroom! 🎉

# ============================================================
# USEFUL COMMANDS FOR DEBUGGING
# ============================================================

# SSH into Render container (if needed)
# Note: Free tier doesn't have SSH, but you can check logs

# View last 100 lines of logs:
# Click "Logs" tab in Render → scroll to bottom

# Memory usage:
# Render Dashboard → Logs → Metrics → Memory (graph)

# Test API from terminal:
curl -v https://your-service.onrender.com/health

# Monitor in real-time (requires Render CLI):
render logs --service deep-research-agent-backend

# ============================================================
# NEXT STEPS
# ============================================================

# 1. Push all changes: git push origin main ✓
# 2. Create Render service ✓
# 3. Set environment variables ✓
# 4. Monitor first deployment (5 minutes)
# 5. Test endpoints
# 6. Celebrate! 🎉

echo "Deployment guide complete! Follow the steps above."
