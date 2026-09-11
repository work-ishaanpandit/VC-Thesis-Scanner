# VC Thesis Screener

An AI-powered venture capital startup screening assistant designed to perform structured first-pass investment evaluations against an **Industrial Robotics** and **Physical AI** thesis across Germany and Western Europe.

---

## 🎯 Investment Thesis Context

The screener evaluates pre-seed and seed startups against the following thesis:

> *"I am building my edge by becoming a specialist in industrial robotics and Physical AI across Germany and Western Europe, focusing on pre-seed and seed startups building the enabling technologies for industrial automation."*

---

## ⚙️ AI Provider & Gemini Free Tier Setup

The application uses **Google Gemini** as its primary AI provider via free-tier models (e.g. `gemini-3.6-flash`), while maintaining a provider-agnostic architecture:

1. Obtain a free API Key at [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Configure `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   GEMINI_MODEL=gemini-3.6-flash
   ```

---

## ☁️ How to Deploy to Vercel

The project includes `vercel.json` and is ready for 1-click deployment on Vercel:

### Method 1: Deploy via GitHub (Recommended)
1. Push this project folder to a GitHub repository:
   ```bash
   git add .
   git commit -m "Deploy VC Thesis Screener"
   git push origin main
   ```
2. Go to [Vercel Dashboard](https://vercel.com/new).
3. Select **Import Project** and choose your GitHub repository.
4. Under **Environment Variables**, add:
   - **Key**: `GEMINI_API_KEY`
   - **Value**: `your_gemini_api_key_here`
5. Click **Deploy**. Vercel will automatically build the Python FastAPI app and serve your web app!

### Method 2: Deploy via Vercel CLI
```bash
# Install Vercel CLI
npm install -g vercel

# Deploy directly from terminal
vercel
```

---

## 🖥️ Running Locally

```bash
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Start server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open **[http://127.0.0.1:8000](http://127.0.0.1:8000)** in your browser.
