# ClickyWin

**A voice-powered AI tutor for Windows that watches your screen, answers your questions, and points at what it's talking about.**

ClickyWin is a Windows port of [Farza's Clicky](https://github.com/farzaa/clicky) — the open-source AI companion that lives next to your cursor. Hold Ctrl+Alt to talk, release to get a spoken answer.

Built for Windows developers, creatives, and anyone learning unfamiliar software by doing instead of watching tutorials.

## How it works

1. Launch ClickyWin. A small blue triangle appears near your cursor.
2. Open whatever software you're learning — DaVinci Resolve, Blender, Wild Apricot, anything.
3. Hold **Ctrl+Alt** and ask your question out loud.
4. Release. ClickyWin screenshots your screen(s), sends them to Gemini along with your transcribed speech, and speaks the answer back to you.
5. The companion cursor flies to the UI element Gemini is describing, so your eyes go right to it.
6. Follow up with another question — ClickyWin remembers the conversation.

## Features

- **Push-to-talk voice input** via Ctrl+Alt with live waveform visualization
- **Multi-monitor screen capture** sent to Gemini for visual context
- **Text-to-speech responses** via ElevenLabs with real-time output waveform
- **Cursor guidance** — companion flies to UI elements Gemini references
- **Knowledge base injection** — curated markdown docs loaded per-app based on active window, so Gemini gives authoritative answers for niche software
- **Conversation memory** — 20-turn history so follow-up questions have full context
- **Interrupt support** — press Ctrl+Alt mid-response to cut the audio and ask something new
- **History window** — optional scrollable transcript accessible from the tray menu

## Prerequisites

- **Windows 10/11**
- **Python 3.12** — [download](https://www.python.org/downloads/)
- **uv** package manager — [install](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js 18+** — for deploying the Cloudflare Worker
- **Cloudflare account** (free tier) — [sign up](https://dash.cloudflare.com/sign-up)
- **API keys:**
  - [Google AI Studio / Gemini](https://aistudio.google.com/) (vision + chat model)
  - [AssemblyAI](https://www.assemblyai.com) (speech-to-text)
  - [ElevenLabs](https://elevenlabs.io) (text-to-speech)

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/JaySmith502/clicky-win.git
cd clicky-win/clicky-py
uv sync
```

### 2. Deploy the Cloudflare Worker

The Worker is a tiny proxy that holds your API keys. The app talks to the Worker, the Worker talks to the APIs. Your keys never ship in the app.

```bash
cd ../worker
npm install
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put ASSEMBLYAI_API_KEY
npx wrangler secret put ELEVENLABS_API_KEY
npx wrangler deploy
```

Copy the deployed URL (e.g. `https://your-worker.your-subdomain.workers.dev`).

### 3. Configure and run

```bash
cd ../clicky-py
uv run python -m clicky
```

On first run, ClickyWin creates `%APPDATA%\ClickyWin\config.toml`. Open it and paste your Worker URL:

```toml
worker_url = "https://your-worker.your-subdomain.workers.dev"
```

Restart ClickyWin. The blue triangle should appear near your cursor. Hold Ctrl+Alt and start talking.

### 4. Permissions

- **Microphone:** Windows Settings > Privacy > Microphone — ensure access is enabled
- **SmartScreen:** If Windows shows a warning on first run, click "More info" then "Run anyway"

## Build a standalone exe

```bash
cd clicky-py
uv run pyinstaller clicky.spec
```

Output: `dist/clicky/ClickyWin.exe` — runs without Python installed.

## Configuration

Edit `%APPDATA%\ClickyWin\config.toml`:

| Field | Default | Description |
|-------|---------|-------------|
| `worker_url` | *(required)* | Your deployed Cloudflare Worker URL |
| `hotkey` | `ctrl+alt` | Push-to-talk binding. Also supports `right_ctrl` |
| `default_model` | `gemini-2.5-flash` | Gemini model for responses |
| `log_level` | `INFO` | DEBUG, INFO, WARNING, or ERROR |
| `knowledge_dir` | `%APPDATA%/ClickyWin/knowledge/` | Path to knowledge base folder |

## Knowledge base

ClickyWin can inject curated documentation into Gemini's context based on which app is in the foreground. This turns it from a general-purpose assistant into an expert trainer for specific software.

## Architecture

Python + PySide6 system tray app using asyncio (via qasync). All three APIs are proxied through a shared Cloudflare Worker.

## Tests

```bash
cd clicky-py
uv run pytest
uv run ruff check .
```
