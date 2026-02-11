# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

QHacks is a prediction market app that matches YouTube Shorts with Kalshi trading markets. Users scroll through a TikTok-style feed where each video is paired with a relevant trade they can place.

## Commands

### Frontend (Next.js + Bun)
```bash
cd frontend
bun install          # Install dependencies
bun run dev          # Development server (localhost:3000)
bun run build        # Production build
bun run lint         # ESLint
```

### Backend (Python + BlackSheep)
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python main.py       # Runs uvicorn on port 8000
```

## Architecture

### Data Flow
1. Frontend loads hardcoded YouTube video IDs from `useVideoQueue` hook
2. Videos are sent to backend `/shorts/feed` endpoint
3. `FeedService` extracts keywords via OpenAI, matches to Kalshi markets
4. Results cached in Firebase Firestore (`video_matches` collection)
5. Frontend displays video + trade card overlay in iPhone mockup

### Backend Services (Dependency Injected via rodi)
- **FeedService**: Core matching logic - YouTube metadata → OpenAI keyword extraction → Kalshi API market matching
- **JobService**: Video generation pipeline using Vertex AI (Veo) - creates promotional videos from trade data
- **VertexService**: Google Vertex AI wrapper for image/video generation

### Frontend Structure
- `app/page.tsx`: Main page with iPhone mockup, trade modal, background
- `components/Feed.tsx`: Scrollable feed container with snap scrolling
- `components/ShortCard.tsx`: Individual video card with embedded YouTube + trade overlay
- `hooks/useVideoQueue.ts`: Queue management, API calls, localStorage persistence
- `types/index.ts`: Shared TypeScript interfaces (KalshiMarket, FeedItem, etc.)

### Key Integrations
- **Kalshi API**: Uses RSA-PSS signature authentication (private key at `backend/kalshi_private_key.pem`)
- **YouTube Data API**: Fetches video metadata (title, description, thumbnail)
- **OpenAI**: GPT-4o for keyword extraction, GPT-4o-mini for event matching
- **Firebase**: Firestore for caching video-to-market matches
- **Google Cloud**: Storage bucket for job persistence, Cloud Tasks for async processing

## Environment Variables

Backend `.env` requires:
- `KALSHI_API_KEY`, `KALSHI_PRIVATE_KEY_PATH`
- `OPENAI_API_KEY`
- `YOUTUBE_API_KEY`
- `GOOGLE_CLOUD_PROJECT`, `GOOGLE_APPLICATION_CREDENTIALS`
- `GOOGLE_CLOUD_BUCKET_NAME` (optional, for job persistence)

Frontend uses `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`)
