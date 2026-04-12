# ClickyWin

**A voice-powered AI tutor for Windows that watches your screen, answers your questions, and points at what it's talking about.**

ClickyWin is a Windows port of [Farza's Clicky](https://github.com/farzaa/clicky) — the open-source AI companion that lives next to your cursor on macOS. Hold Ctrl+Alt to talk, release to get a spoken answer from Claude. The companion cursor flies to UI elements it references, so you always know exactly what it's describing.

Built for Windows developers, creatives, and anyone learning unfamiliar software by doing instead of watching tutorials.

## How it works

1. Launch ClickyWin. A small blue triangle appears near your cursor.
2. Open whatever software you're learning — DaVinci Resolve, Blender, Wild Apricot, anything.
3. Hold **Ctrl+Alt** and ask your question out loud.
4. Release. ClickyWin screenshots your screen(s), sends them to Claude along with your transcribed speech, and speaks the answer back to you.
5. The companion cursor flies to the UI element Claude is describing, so your eyes go right to it.
6. Follow up with another question — ClickyWin remembers the conversation.

## Features

- **Push-to-talk voice input** via Ctrl+Alt with live waveform visualization
- **Multi-monitor screen capture** sent to Claude for visual context
- **Text-to-speech responses** via ElevenLabs with real-time output waveform
- **Cursor guidance** — companion flies to UI elements Claude references via POINT tags
- **Knowledge base injection** — curated markdown docs loaded per-app based on active window title, so Claude gives authoritative answers for niche software
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
  - [Anthropic](https://console.anthropic.com) (Claude)
  - [AssemblyAI](https://www.assemblyai.com) (speech-to-text)
  - [ElevenLabs](https://elevenlabs.io) (text-to-speech)

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/JaySmith502/clicky-win.git
cd clicky-win
```

### 2. Deploy the Cloudflare Worker

The Worker is a tiny proxy that holds your API keys. The app talks to the Worker, the Worker talks to the APIs. Your keys never ship in the app.

```bash
cd worker
npm install
npx wrangler secret put ANTHROPIC_API_KEY
npx wrangler secret put ASSEMBLYAI_API_KEY
npx wrangler secret put ELEVENLABS_API_KEY
npx wrangler deploy
```

Copy the deployed URL (e.g. `https://your-worker.your-subdomain.workers.dev`).

### 3. Install and run ClickyWin

```bash
cd clicky-py
uv sync
uv run python -m clicky
```

On first run, ClickyWin creates a config file at `%APPDATA%\ClickyWin\config.toml`. Open it and paste your Worker URL:

```toml
worker_url = "https://your-worker.your-subdomain.workers.dev"
```

Restart ClickyWin. The blue triangle should appear near your cursor.

### 4. Grant permissions

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
| `default_model` | `claude-sonnet-4-6` | Claude model for responses |
| `log_level` | `INFO` | DEBUG, INFO, WARNING, or ERROR |
| `knowledge_dir` | `%APPDATA%/ClickyWin/knowledge/` | Path to knowledge base folder |

## Knowledge base

ClickyWin can inject curated documentation into Claude's context based on which app is in the foreground. This turns it from a general-purpose assistant into an expert trainer for specific software.

### Setting up a KB

Create a folder per app inside your knowledge directory:

```
%APPDATA%/ClickyWin/knowledge/
  └── wild_apricot/
      ├── _meta.toml      # maps window titles to this KB
      ├── overview.md      # always included — app overview
      ├── events.md        # topic-specific docs
      ├── membership.md
      └── email.md
```

The `_meta.toml` file tells ClickyWin when to load this KB:

```toml
name = "Wild Apricot"
window_titles = ["Wild Apricot", "wildapricot.org"]
```

When the user's foreground window title contains any of the `window_titles` strings, all markdown files in that folder are injected into Claude's system prompt. Claude is instructed to treat this content as authoritative.

### Authoring KB content

Any source of markdown works. We recommend [NotebookLM](https://notebooklm.google.com/) for distilling large doc sets:

1. Upload the software's documentation, help articles, or video transcripts to NotebookLM
2. Ask it to produce focused markdown per topic area (see prompt template in `docs/`)
3. Drop the `.md` files into the app's KB folder
4. Write a `_meta.toml` with the window title matchers

No restart required — ClickyWin loads KB content fresh on every turn.

## Tests and linting

```bash
cd clicky-py
uv run pytest
uv run ruff check .
```

## Architecture

ClickyWin is a Python + PySide6 system tray app using asyncio (via qasync) for non-blocking I/O. All three APIs (Claude, AssemblyAI, ElevenLabs) are proxied through a shared Cloudflare Worker.

**Key modules:**
- **CompanionManager** — central state machine orchestrating the voice turn pipeline
- **CompanionWidget** — transparent cursor-following overlay with state-driven animations
- **MicCapture** — WASAPI audio input via sounddevice
- **OutputCapture** — system audio level monitoring via pycaw for response waveform
- **TranscriptionClient** — AssemblyAI real-time streaming via websockets
- **LLMClient** — Claude streaming via Anthropic SSE protocol
- **TTSClient** — ElevenLabs text-to-speech via QMediaPlayer
- **KnowledgeBase** — per-app markdown KB with window title matching and token-budgeted selection

**State flow:** IDLE → LISTENING (Ctrl+Alt held) → PROCESSING (screenshots + Claude request) → RESPONDING (TTS playback + cursor guidance) → IDLE

## Credits

ClickyWin is a community port of [Clicky](https://github.com/farzaa/clicky) by [Farza Majeed](https://x.com/FarzaTV). All credit for the original concept, UX design, companion cursor behavior, and Swift implementation goes to Farza. The cursor guidance system, POINT tag protocol, and voice interaction model are direct ports of his work.

The knowledge base system and Windows-specific adaptations (WASAPI audio, DWM transparency, pycaw output metering) are original to ClickyWin.

## License

MIT — see [LICENSE](LICENSE).
