# Render Deployment Checklist

## Pre-Deployment ✅

### 1. Environment Variables on Render Dashboard

Go to **Settings → Environment** and add:

```
RENDER=true
PRODUCTION=true
OPENROUTER_API_KEY=sk-xxxxx
TAVILY_API_KEY=tvly-xxxxx
SERPER_API_KEY=your_serper_key (optional)
REDIS_URL=redis://:password@redis-host:6379
LLM_MODEL_CHEAP=google/gemini-2.0-flash
LLM_MODEL_MID=anthropic/claude-3.5-haiku
LLM_MODEL_PREMIUM=anthropic/claude-3.5-sonnet
```

### 2. Git Push Latest Code

```bash
git add -A
git commit -m "Render deployment: memory optimization"
git push origin main
```

### 3. Verify Files Are Committed

Check these files exist in your repo:

- ✅ `render.yaml` (new)
- ✅ `Procfile` (new)
- ✅ `.env.render` (template)
- ✅ `MEMORY_OPTIMIZATION.md` (guide)
- ✅ `backend/requirements.txt` (updated)
- ✅ `backend/app/main.py` (updated)
- ✅ `backend/app/embeddings.py` (updated)
- ✅ `backend/app/nodes.py` (updated)

---

## Deployment Steps

### Option 1: Using Render Dashboard (Recommended)

1. Go to https://dashboard.render.com
2. Click **New +** → **Web Service**
3. Connect your GitHub repo
4. Fill in:
   - **Name:** `deep-research-agent`
   - **Runtime:** Python 3.11
   - **Build Command:** `pip install -r backend/requirements.txt`
   - **Start Command:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`
5. Select **Free Tier** (512 MB RAM)
6. Click **Create Web Service**
7. Go to **Settings → Environment** and paste all variables from section above
8. Render will auto-deploy

### Option 2: Using `render.yaml`

1. Render will auto-detect `render.yaml` if committed
2. Just deploy from dashboard or CLI:

```bash
render deploy --service deep-research-agent
```

---

## Post-Deployment

### Monitor Memory (First 5 minutes)

1. Go to **Logs**
2. Watch for any errors
3. Check memory usage stays under **450MB**

### Test the API

```bash
curl https://your-service.onrender.com/health
```

Should return:

```json
{ "status": "ok", "version": "2.0" }
```

### Test Research Endpoint

```bash
curl -X POST https://your-service.onrender.com/api/research \
  -H "Content-Type: application/json" \
  -d '{"topic": "Python", "depth": "quick", "output_format": "both"}'
```

---

## Troubleshooting

### ❌ "Out of Memory" (OOM) Error

**Solution:**

1. Check Render logs for the error
2. Ensure `--workers 1` is in start command
3. Verify `REDIS_URL` is set (enables caching)
4. Check `MAX_RESULTS_PER_SECTION = 30` in `nodes.py`

### ❌ "Module not found" Error

**Solution:**

```bash
# Check requirements.txt is installed
# Run locally first:
cd backend
pip install -r requirements.txt
python -c "import app.main"
```

### ❌ "API timeout" (>30 seconds)

**Solution:**

1. Render free tier is slow - expected for research
2. Timeout is 30 seconds for SSE requests
3. Upgrade to **Starter** plan ($7/month) for faster performance

### ❌ "Redis connection refused"

**Solution:**

1. Set up Redis on Render or Upstash (free tier available)
2. Get the `REDIS_URL` connection string
3. Add to environment variables
4. Without Redis, caching won't work but app still runs

---

## Memory Usage Breakdown

With all optimizations:

- **Base (Startup):** 150MB
- **Idle (no requests):** 250MB
- **During research:** 400-450MB (peak)
- **After research:** 300MB (GC cleanup)
- **Headroom:** ~60MB (safe)

---

## If You Need PDF Generation

Since we removed `weasyprint` to save memory:

**Option A (Client-side):** Users download markdown, convert to PDF in browser

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
<!-- User clicks "Download PDF" button in frontend -->
```

**Option B (Micro-service):** Create separate API on paid tier for PDF

```bash
# Separate render service with 1GB RAM just for PDFs
```

---

## Security Checklist

- ✅ All API keys are environment variables (not in code)
- ✅ CORS allows frontend origin
- ✅ Redis has password (in URL)
- ✅ No sensitive logs printed
- ✅ Rate limiting via semaphore (max 2 concurrent)

---

## Estimated Costs

| Item                        | Cost                         |
| --------------------------- | ---------------------------- |
| API (512MB, free tier)      | **$0**                       |
| Redis (free tier - Upstash) | **$0**                       |
| OpenRouter API calls        | ~$0.01-0.05/request          |
| Tavily Search API           | ~$0.01/request               |
| Render Data Transfer        | $0.10/GB                     |
| **Total**                   | **~$0.02-0.10 per research** |

---

## Performance Expectations

With these optimizations, on Render free tier:

| Metric              | Value          |
| ------------------- | -------------- |
| Memory usage        | 400-450MB      |
| Research time       | 60-120 seconds |
| Concurrent requests | 2 max          |
| Cache hit time      | <5 seconds     |
| Cache miss time     | 60-120 seconds |

---

## Next Steps

1. **Push code:** `git push origin main`
2. **Create service:** Go to Render dashboard
3. **Set variables:** Add all env vars
4. **Monitor:** Watch logs for first 5 minutes
5. **Test:** Call `/health` endpoint
6. **Deploy frontend:** Create second web service for `frontend/`

---

## Contact Support

If issues persist:

- Render Support: https://support.render.com
- Check Render docs: https://render.com/docs
- Debug locally first before deploying
