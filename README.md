# Thai Vocab Mastery

Local Thai vocabulary trainer with:

- FastAPI backend
- React + Vite frontend
- SQLite mastery/session tracking
- OpenAI-generated question variants with safe fallbacks
- Pluggable Thai TTS with browser speech today and a server TTS path ready for Google Cloud

## Setup

1. Copy [.env.example](/Users/pauljames/1%20-%20PROJECTS/Codex/Mastery%20vocab%20learning%20app/.env.example) to `.env`
2. Fill in `OPENAI_API_KEY`
3. Install backend deps:

```bash
python3 -m pip install -r backend/requirements.txt
```

4. Install frontend deps:

```bash
cd frontend
npm install
```

5. Optional frontend TTS env:

```bash
cd frontend
cp .env.example .env.local
```

## Run

Backend:

```bash
python3 -m uvicorn backend.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm run dev
```

## Google TTS Prep

The app still defaults to browser speech, but it is now wired so you can switch to server audio later.

Backend `.env` options:

```bash
TTS_PROVIDER=browser
GOOGLE_TTS_LANGUAGE_CODE=th-TH
GOOGLE_TTS_VOICE_NAME=th-TH-Standard-A
GOOGLE_TTS_AUDIO_ENCODING=MP3
GOOGLE_TTS_WORD_RATE=0.82
GOOGLE_TTS_SENTENCE_RATE=0.9
```

Frontend `frontend/.env.local` options:

```bash
VITE_TTS_PROVIDER=browser
VITE_TTS_BASE=http://127.0.0.1:8000
```

To move to Google Cloud Text-to-Speech:

1. Install backend dependencies again so `google-auth` is present.
2. Configure Google Application Default Credentials or another supported Google auth flow.
3. Set backend `TTS_PROVIDER=google`.
4. Set frontend `VITE_TTS_PROVIDER=server`.

When server TTS is enabled, the frontend fetches audio from `GET /tts/speak?text=...&mode=word|sentence`. If that endpoint is unavailable, the UI falls back to browser speech.

To pre-generate cached audio for the whole deck:

```bash
python3 backend/precache_tts.py --mode both
```

Useful variants:

```bash
python3 backend/precache_tts.py --mode word
python3 backend/precache_tts.py --mode sentence
python3 backend/precache_tts.py --mode both --limit 50
python3 backend/precache_tts.py --mode both --force
```

This writes audio files into `backend/data/tts_cache` and skips existing cached files unless `--force` is used.

## Content Review

The seed deck can be audited and refreshed in a non-destructive first pass with:

```bash
python3 backend/review_words.py --limit 25
```

This writes:

- a raw review report to `backend/data/reviews/words_first_pass.jsonl`
- a merged candidate deck to `backend/data/reviews/words_first_pass_merged.json`

The review pass asks the LLM to:

- sanity-check the English gloss
- tighten `english_alt`
- generate a shorter, more natural Thai example sentence
- generate a clean English translation

Only suggestions at or above the confidence threshold are merged into the candidate deck.

## Notes

- If `OPENAI_API_KEY` is missing or the model call fails, the app falls back to locally generated multiple-choice questions and explanations.
- The backend reads `.env` from the project root, so you do not need to duplicate env files across folders.
