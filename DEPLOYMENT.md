# Deployment Guide

This guide explains how to deploy the **Deep Research Agent** using **Render** (Backend) and **Vercel** (Frontend).

## Prerequisites
- A GitHub repository containing this project.
- Accounts on [Render](https://render.com) and [Vercel](https://vercel.com).
- API Keys: `OPENROUTER_API_KEY`, `TAVILY_API_KEY`.

---

## Part 1: Deploy Backend (Render)

1.  **Create a Web Service**:
    - Go to the Render Dashboard and click **New +** -> **Web Service**.
    - Connect your GitHub repository.

2.  **Configure Service**:
    - **Name**: `deep-research-backend` (or similar)
    - **Region**: Choose one close to you.
    - **Branch**: `main`
    - **Root Directory**: `backend` (IMPORTANT)
    - **Runtime**: `Python 3`
    - **Build Command**: `pip install -r requirements.txt`
    - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

3.  **Environment Variables**:
    - Add the following keys in the "Environment" tab:
        - `OPENROUTER_API_KEY`: `sk-or-v1-...`
        - `TAVILY_API_KEY`: `tvly-...`
        - `LLM_MODEL`: `google/gemini-2.0-flash-exp:free` (or your preferred model)
        - `PYTHON_VERSION`: `3.11.9` (Recommended)

4.  **Deploy**:
    - Click **Create Web Service**.
    - Wait for the deployment to finish.
    - **Copy the Backend URL** (e.g., `https://deep-research-backend.onrender.com`). You will need this for the frontend.

---

## Part 2: Deploy Frontend (Vercel)

1.  **Import Project**:
    - Go to the Vercel Dashboard and click **Add New...** -> **Project**.
    - Import your GitHub repository.

2.  **Configure Project**:
    - **Framework Preset**: `Vite` (Should be auto-detected).
    - **Root Directory**: Click the "Edit" button and select `frontend`.

3.  **Environment Variables**:
    - Expand the "Environment Variables" section.
    - Add:
        - `VITE_API_URL`: Paste your Render Backend URL (e.g., `https://deep-research-backend.onrender.com`).
        - **Note**: Do NOT remove the `https://` or include a trailing slash `/`.

4.  **Deploy**:
    - Click **Deploy**.
    - Vercel will build and deploy your React app.

5.  **Test**:
    - Visit the generated Vercel URL.
    - Enter a topic and click "Research".
    - You should see the progress stream and the final PDF.

---

## Troubleshooting

- **CORS Errors**: If you see CORS errors in the browser console, ensure the Backend URL in Vercel is correct (`VITE_API_URL`). The backend is configured to allow all origins (`*`) by default.
- **Connection Refused**: On Render, the first request might be slow as the free tier spins down on inactivity. Wait a moment and try again.
- **Build Fails**: Check the logs on Render/Vercel. Ensure `backend/requirements.txt` and `frontend/package.json` are present in their respective directories.
