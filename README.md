# Vera: AI Voice Agent for Customer Support

Vera answers customer calls using **only** a company's written policies. When a question is outside
those policies (or the customer is angry, threatens legal action, or asks for a human), Vera does not
guess. She says a specialist will call back within 5 minutes, and the case appears on a callbacks page.

Built for the Hacktoberfest / CodeCraft 2026 hackathon using **Gemma 4**. **Kartify is a fictional demo company.**

## Why it matters

A call centre of 500 agents paid about Rs. 20,000 a month each costs roughly Rs. 1 crore a month
(a rough estimate). Vera is meant to handle the repetitive questions (delivery, returns, refunds,
exchanges, payments) for a small yearly subscription, and pass only the hard cases to humans.

## What is inside

| File | What it does |
|------|--------------|
| `app.py` | Backend (Python Flask + SQLite). Matches questions to policies, decides when to escalate, logs callbacks. |
| `.env.example` | Template for your private API key file. |
| `kb.json` | Vera's knowledge base: every policy answer and the escalation rules. **Edit this to teach Vera a new company.** |
| `static/index.html` | Frontend: voice call page (microphone in, spoken answer out) with typed fallback. |
| `static/escalations.html` | Dashboard of calls handed to a human specialist. |
| `docs/Kartify_Vera_Knowledge_Base.pdf` | The same policies as a readable document, with 34 test questions. |

## Run it (Windows, Mac or Linux)

1. Install Python 3.9 or newer from python.org (tick "Add Python to PATH" on Windows).
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   python app.py
   ```
3. Open **http://localhost:5000** in **Google Chrome** (voice input works in Chrome and Edge).
4. Click **Start call with Vera**, allow the microphone, and speak after Vera finishes her greeting.
5. Open **http://localhost:5000/escalations** in a second tab to watch callbacks appear live.

No account, API key or payment is needed.

## Demo script (3 minutes)

1. "I want to return my earphones." Vera explains the 10-day electronics return window.
2. "My product arrived broken." Vera explains the 48-hour rule and refund or replacement.
3. "Do you have a store near me?" This is not in the policy. Vera hands over to a specialist,
   a 5:00 countdown starts, and the case shows up on the callbacks page. This proves Vera never makes things up.

If the microphone or Wi-Fi fails, tap the sample question buttons or type instead.

## How it works

```
Customer voice -> browser speech recognition -> POST /api/chat
   -> Flask backend: safety rules (human / legal / abuse) first
   -> Gemma 4 (via the Gemini API) reads the customer's words + the Kartify knowledge base
   -> answer, or escalation + SQLite log -> browser text-to-speech -> Customer hears Vera
```

- **Gemma 4 = the AI.** It understands any phrasing (English, Hindi, Hinglish) and writes a short spoken answer using only the facts in `kb.json`. Models: `gemma-4-26b-a4b-it` (default, faster) or `gemma-4-31b-it`.
- **Safety rules = the guard rails.** Requests for a human, legal threats, fraud and abusive language are escalated by fixed rules before Gemma is even asked.
- **Fallback.** If there is no API key, no internet, or the Gemma call fails, Vera switches to a built-in rules brain so the demo never freezes. The page shows which brain is active.
- **Voice layer:** the browser's built-in speech tools (free). It can be swapped for any speech engine later.

### Turn on Gemma 4

1. Get a free key at https://aistudio.google.com/apikey (sign in with Google, click Create API key).
2. In this folder, copy `.env.example` to a new file named `.env` and paste your key after `GEMINI_API_KEY=`.
3. Run `python app.py`. The pill on the page should say **Brain: Gemma 4**.

**Never upload your API key to GitHub.** `.env` is already listed in `.gitignore`. On Render, add the key under Environment instead.

## Put it online (so anyone can open it on a phone)

Free option: **Render.com** (the project already includes `render.yaml`, `Procfile` and `gunicorn`). Add your `GEMINI_API_KEY` in Render under Environment. The event guide also suggests DigitalOcean for hosting; check the event's rules to see whether a specific host is required.

1. Upload this folder to a public GitHub repository.
2. On render.com, sign in with GitHub, choose **New > Blueprint** (or **New > Web Service**) and pick the repository.
3. If you chose Web Service: Build command `pip install -r requirements.txt`, Start command
   `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`, plan **Free**.
4. After a few minutes Render gives a link like `https://vera-ai-voice-agent.onrender.com`. Share that link or a QR code.

Notes:
- Free services go to sleep when unused, so the first visit can take up to a minute. Open the link yourself a few minutes before the demo.
- Microphone input works because Render gives you HTTPS. Use Chrome on Android. iPhones may not support voice input, but typing and the sample buttons still work.
- Callbacks are stored in a temporary database that resets when the service restarts. That is fine for a demo.
- The callbacks page is public. Anyone with the link can see and clear it.

## Teach Vera a new company

Open `kb.json` and add an entry:

```json
{
  "id": "gift_wrap", "topic": "Orders", "priority": 1,
  "triggers": ["gift wrap", "wrap as gift"],
  "answer": "Gift wrapping is available for 49 rupees per item."
}
```

Restart `python app.py`. Add `"escalate": true` to an entry if it should always go to a human.

## Known limits (honest list)

- Without a Gemma key, Vera uses the rules brain, which only knows a fixed set of words and phrases. Unusual wording is escalated to a human, which is the safe failure.
- Gemma replies take a second or two. Free API keys have usage limits, so a very busy demo may fall back to the rules brain.
- Voice input needs Chrome or Edge and an internet connection.
- Callbacks are logged but no real phone call is placed. A real version would connect a telephony provider.
- Order details are not looked up. Vera explains policy and records the Order ID.

## Licence

MIT. See `LICENSE`.
