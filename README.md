# <img src="/frontend/public/kalship-text.png" alt="Logo" height="32">

scroll shorts. trade predictions. that's it.

matches YouTube Shorts to Kalshi prediction markets using AI, so you can doomscroll your way into financial literacy (or not)


https://github.com/user-attachments/assets/e0e68e53-62f0-4264-a490-565823de1e67


## what it does

- **shorts meet markets** — every reel gets paired with a relevant Kalshi market via OpenAI keyword extraction
- **live price charts** — candlestick data pulled straight from Kalshi, rendered with lightweight-charts
- **yes/no trading** — tap a side, get AI trade advice from our 3D mascot Joe
- **AI video generation** — after you trade, a custom visualization reel gets generated (Vertex AI Veo) and injected as your next video
- **tutorial flow** — 3D character walks you through it so you don't get lost

## stack

**frontend** — Next.js, TypeScript, Tailwind, Framer Motion, React Three Fiber, lightweight-charts

**backend** — Python, BlackSheep, Uvicorn, aiohttp

**integrations** — Kalshi API, YouTube Data API, OpenAI (GPT-4o), Vertex AI (Veo), Firebase Firestore, Google Cloud Storage + Tasks

## setup

### backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
python main.py         # localhost:8000
```

needs: `KALSHI_API_KEY`, `KALSHI_PRIVATE_KEY_PATH`, `OPENAI_API_KEY`, `YOUTUBE_API_KEY`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`

### frontend
```bash
cd frontend
bun install
bun run dev  # localhost:3000
```

set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `.env`

### video pipeline (optional)
```bash
cd backend/scripts && bash setup-gcp.sh
```
needs Cloud Tasks, Cloud Storage, and Vertex AI enabled on your GCP project

## how it works

1. frontend loads a feed of YouTube Shorts from the pool (Firebase)
2. each short is pre-matched to Kalshi markets via OpenAI keyword extraction
3. user scrolls, sees the market card + live price chart alongside each video
4. tapping YES/NO triggers AI video generation — Veo creates a themed clip that gets injected as the next reel
5. Joe (the 3D character) gives trade advice if you ask nicely

## api routes

| route | method | what it does |
| --- | --- | --- |
| `/pool/feed` | GET | grab feed items from the pool |
| `/shorts/candlesticks` | GET | price history for charts |
| `/shorts/advice` | POST | AI trade commentary |
| `/jobs/create` | POST | kick off video generation |
| `/pool/generated/{id}/consume` | POST | mark generated video as consumed |
