/**
 * Clicky Proxy Worker
 *
 * Proxies requests to Gemini APIs so the app never ships with raw API keys.
 * Keys are stored as Cloudflare secrets.
 *
 * Routes:
 *   POST /chat  → Gemini Generative AI (streaming-compatible proxy)
 *   POST /tts   → ElevenLabs TTS API
 */

interface Env {
  GEMINI_API_KEY: string;
  ELEVENLABS_API_KEY: string;
  ELEVENLABS_VOICE_ID: string;
  ASSEMBLYAI_API_KEY: string;
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method !== "POST") {
      return new Response("Method not allowed", { status: 405 });
    }

    try {
      if (url.pathname === "/chat") {
        return await handleChat(request, env);
      }

      if (url.pathname === "/tts") {
        return await handleTTS(request, env);
      }

      if (url.pathname === "/transcribe-token") {
        return await handleTranscribeToken(env);
      }
    } catch (error) {
      console.error(`[${url.pathname}] Unhandled error:`, error);
      return new Response(
        JSON.stringify({ error: String(error) }),
        { status: 500, headers: { "content-type": "application/json" } }
      );
    }

    return new Response("Not found", { status: 404 });
  },
};

function toSseText(text: string): string {
  return `event: content_block_delta\ndata: ${JSON.stringify({
    delta: { type: "text_delta", text },
  })}\n\n`;
}

function toGeminiParts(content: unknown): Array<{ text?: string; inlineData?: { mimeType: string; data: string } }> {
  if (typeof content === "string") {
    return [{ text: content }];
  }

  if (!Array.isArray(content)) {
    return [{ text: String(content ?? "") }];
  }

  const parts: Array<{ text?: string; inlineData?: { mimeType: string; data: string } }> = [];

  for (const block of content) {
    if (!block || typeof block !== "object") {
      continue;
    }

    const maybeBlock = block as {
      type?: string;
      text?: string;
      source?: { type?: string; media_type?: string; data?: string };
      image_url?: { url?: string };
    };

    if (maybeBlock.type === "text" && typeof maybeBlock.text === "string") {
      parts.push({ text: maybeBlock.text });
      continue;
    }

    if (maybeBlock.type === "image" && maybeBlock.source?.type === "base64") {
      const mimeType = maybeBlock.source.media_type || "image/jpeg";
      const data = maybeBlock.source.data || "";
      if (data) {
        parts.push({ inlineData: { mimeType, data } });
      }
      continue;
    }

    if (maybeBlock.type === "image_url" && typeof maybeBlock.image_url?.url === "string") {
      const url = maybeBlock.image_url.url;
      if (url.startsWith("data:")) {
        const match = url.match(/^data:(image\/[^;]+);base64,(.+)$/i);
        if (match) {
          parts.push({ inlineData: { mimeType: match[1], data: match[2] } });
        }
      }
    }
  }

  return parts.length > 0 ? parts : [{ text: "" }];
}

function buildGeminiRequest(
  model: string,
  system: string,
  messages: any[],
  maxTokens: number,
): Record<string, unknown> {
  const contents: Array<{ role: string; parts: Array<{ text?: string; inlineData?: { mimeType: string; data: string } }> }> = [];

  for (const message of messages || []) {
    const role = message?.role === "assistant" ? "model" : "user";
    const parts = toGeminiParts(message?.content);
    if (parts.length > 0) {
      contents.push({ role, parts });
    }
  }

  const body: Record<string, unknown> = {
    contents,
    generationConfig: {
      maxOutputTokens: maxTokens,
      temperature: 0.3,
    },
  };

  if (system && system.trim()) {
    body.systemInstruction = {
      parts: [{ text: system }],
    };
  }

  return body;
}

async function handleChat(request: Request, env: Env): Promise<Response> {
  const body = (await request.json()) as {
    model?: string;
    max_tokens?: number;
    system?: string;
    messages?: unknown[];
  };

  const model = body.model || "gemini-2.5-flash";
  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${env.GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(
        buildGeminiRequest(model, body.system || "", body.messages || [], body.max_tokens || 1024)
      ),
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/chat] Gemini API error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  const data = (await response.json()) as {
    candidates?: Array<{
      content?: { parts?: Array<{ text?: string }> };
    }>;
  };

  const text = (data.candidates || [])
    .flatMap((candidate) => candidate.content?.parts || [])
    .map((part) => part.text || "")
    .join("")
    .trim();

  const sse = toSseText(text);

  return new Response(sse, {
    status: 200,
    headers: {
      "content-type": "text/event-stream",
      "cache-control": "no-cache",
    },
  });
}

async function handleTranscribeToken(env: Env): Promise<Response> {
  const response = await fetch(
    "https://streaming.assemblyai.com/v3/token?expires_in_seconds=480",
    {
      method: "GET",
      headers: {
        authorization: env.ASSEMBLYAI_API_KEY,
      },
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/transcribe-token] AssemblyAI token error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  const data = await response.text();
  return new Response(data, {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

async function handleTTS(request: Request, env: Env): Promise<Response> {
  const body = await request.text();
  const voiceId = env.ELEVENLABS_VOICE_ID;

  const response = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`,
    {
      method: "POST",
      headers: {
        "xi-api-key": env.ELEVENLABS_API_KEY,
        "content-type": "application/json",
        accept: "audio/mpeg",
      },
      body,
    }
  );

  if (!response.ok) {
    const errorBody = await response.text();
    console.error(`[/tts] ElevenLabs API error ${response.status}: ${errorBody}`);
    return new Response(errorBody, {
      status: response.status,
      headers: { "content-type": "application/json" },
    });
  }

  return new Response(response.body, {
    status: response.status,
    headers: {
      "content-type": response.headers.get("content-type") || "audio/mpeg",
    },
  });
}

