# 🚀 Deployment Guide: AI ScreenX Full-Stack

This guide provides a production-ready roadmap for deploying the AI Resume Screener using **Vercel** (Frontend) and **Railway** (Backend).

---

## 1. 🌐 Frontend Deployment (Vercel)

Vercel is the best platform for React/Vite apps due to its global CDN and edge performance.

### Step-by-Step:
1.  **Connect Repo**: Log in to [Vercel](https://vercel.com/) and import your project repository.
2.  **Project Settings**:
    - **Framework Preset**: Vite
    - **Build Command**: `npm run build`
    - **Output Directory**: `dist`
3.  **Environment Variables**:
    - Go to **Settings > Environment Variables**.
    - Add `VITE_API_BASE_URL`: Enter your deployed Railway API URL (e.g., `https://api.yourdomain.com/api/v1`).
4.  **Deploy**: Click Deploy. Vercel will handle the rest.

---

## 2. 🚂 Backend Deployment (Railway)

We recommend **Railway** or **Render** because they handle long-running Python servers and AI models (SBERT/SpaCy) better than serverless functions.

### Step-by-Step:
1.  **New Project**: Connect your repo to [Railway](https://railway.app/).
2.  **Root Directory**: Set this to `backend/`.
3.  **Dockerization**: Railway will automatically detect the `Dockerfile` in the `backend/` folder and build your image.
4.  **Variables**: Add the following:
    - `ALLOWED_ORIGINS`: Your Vercel frontend URL (e.g., `https://your-app.vercel.app`).
    - `PYTHONUNBUFFERED`: `1`
5.  **Networking**: Railway will assign a public domain to your service. Copy this for your Frontend `VITE_API_BASE_URL`.

---

## 3. 📦 Storage & File Uploads (Production)

For production, storing files on a local server is risky. We suggest migrating to **Cloudinary** or **AWS S3**.

- **Recommendation**: Use **Cloudinary** for its excellent Python SDK and auto-optimization.
- **Implementation**:
    1. Update `backend/app/utils/parser.py` to upload the file to Cloudinary first.
    2. Pass the resulting URL to the extraction logic.

---

## 4. ⚡ Performance & Security

### **Caching**
- The backend is already optimized with **async processing**.
- To further improve speed, consider adding **Redis** for caching repeated JD/Resume match results.

### **Rate Limiting**
- I have already integrated **SlowAPI** in `main.py`. 
- By default, it's set to prevent brute-force abuse of the AI matching engine.

### **Monitoring**
- Use **Sentry** or **LogRocket** for frontend error tracking.
- For the backend, Railway provides built-in metrics and logs.

---

## 💎 Bonus: Serverless Migration (AWS Lambda)

If you wish to go serverless to save costs:
1.  Package the backend as a **Docker Container** (which you already have).
2.  Deploy to **AWS Lambda** via **AWS ECR**.
3.  Use **AWS API Gateway** to expose the endpoints.
4.  *Note: Boot times (Cold Starts) will be higher due to the SBERT model loading.*

---

**You are now ready for launch!** 🚀
