# ClickyWin

ClickyWin is a Windows port of [Farza's Clicky](https://github.com/farzaa/clicky) — a voice-powered AI tutor that watches your screen and answers questions about what you're doing. Hold Ctrl+Alt to talk, release to get a spoken answer from Claude.

## Prerequisites

- Python 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- Cloudflare account (free tier)
- API keys: Anthropic, AssemblyAI, ElevenLabs

## Deploy the Worker

```bash
cd worker
npm install
wrangler secret put ANTHROPIC_API_KEY
wrangler secret put ASSEMBLYAI_API_KEY
wrangler secret put ELEVENLABS_API_KEY
wrangler deploy
```

Copy the deployed URL into `%APPDATA%\ClickyWin\config.toml` as `worker_url`.

## Dev loop

```bash
cd clicky-py
uv sync
uv run python -m clicky
```

## Build

```bash
cd clicky-py
uv run pyinstaller clicky.spec
```

Output: `dist/clicky/ClickyWin.exe`

## Tests + lint

```bash
uv run pytest
uv run ruff check .
```

## Configuration

Reference `config.example.toml`. Fields:

- `worker_url` — your Cloudflare Worker URL (required)
- `hotkey` — push-to-talk binding, default `ctrl+alt`
- `default_model` — `claude-sonnet-4-6` or `claude-opus-4-6`
- `log_level` — DEBUG/INFO/WARNING/ERROR

## Troubleshooting

- **Microphone:** ensure Windows Settings > Privacy > Microphone access is enabled
- **Worker URL:** replace the placeholder in config.toml with your actual deployed URL
- **SmartScreen:** on first run Windows may show a warning — click "More info" then "Run anyway"

## Credits

ClickyWin is a community port of [Clicky](https://github.com/farzaa/clicky) by [Farza Majeed](https://x.com/FarzaTV). All credit for the original concept, UX design, and Swift implementation goes to Farza.

## License

MIT — see [LICENSE](LICENSE).
