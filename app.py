"""
Vera - AI voice customer-support agent for Kartify (hackathon demo).

Backend: Flask + SQLite (both free / open source).
 - /api/start  -> Vera's greeting
 - /api/chat   -> answers a customer message from the knowledge base (kb.json)
 - /api/escalations -> list of calls handed over to a human specialist

Two "brains" are supported:
 1. Rules mode (default, no account or API key needed): matches the customer's words
    against kb.json. Vera can ONLY say what is written there, so she never invents policy.
 2. Gemma 4 mode: set GEMINI_API_KEY (free, from Google AI Studio). Gemma 4 then understands
    the customer's words and answers from the same knowledge base. Safety rules (human requests,
    legal threats, abuse) still run first, and if the Gemma call fails Vera falls back to rules.
"""
import json
import os
import re
import sqlite3
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "data.db")

with open(os.path.join(BASE, "kb.json"), encoding="utf-8") as f:
    KB = json.load(f)

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="/static")

ESCALATION_LINE = KB["escalation_line"]
LANGS = ("en", "hi", "mr")
LANG_NAMES = {"en": "simple English", "hi": "simple Hindi written in Devanagari script", "mr": "simple Marathi written in Devanagari script"}


def T(key, lang, **kw):
    """Fixed Vera lines (greeting, thanks, escalation...) in English, Hindi or Marathi."""
    pack = KB["i18n"].get(lang) or {}
    return (pack.get(key) or KB["i18n"]["en"][key]).format(**kw)

SESSIONS = {}  # session_id -> {"order_id": str|None, "asked_order": bool, "turns": int}


# ---------------------------------------------------------------- database
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS escalations (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 ts TEXT NOT NULL,
                 session_id TEXT,
                 order_id TEXT,
                 reason TEXT,
                 message TEXT
               )"""
        )


def log_escalation(session_id, order_id, reason, message):
    with db() as con:
        con.execute(
            "INSERT INTO escalations (ts, session_id, order_id, reason, message) VALUES (?,?,?,?,?)",
            (datetime.now().strftime("%d %b %Y, %I:%M:%S %p"), session_id, order_id or "-", reason, message),
        )


# ---------------------------------------------------------------- text matching
def stem(tok):
    if len(tok) > 4:
        for suf in ("ing", "ed", "es", "s", "e"):
            if tok.endswith(suf) and len(tok) - len(suf) >= 3:
                return tok[: -len(suf)]
    return tok


def normalise(text):
    text = text.lower().replace("’", " ").replace("'", " ")
    text = re.sub(r"[^a-z0-9ऀ-ॿ]+", " ", text)
    return " ".join(stem(t) for t in text.split())


def contains(norm_text, phrase):
    p = normalise(phrase)
    return f" {p} " in f" {norm_text} "


def any_trigger(norm_text, triggers):
    return any(contains(norm_text, t) for t in triggers)


ORDER_ID_RE = re.compile(r"\b(?:(?:ORD|KRT|KR|OD)[- ]?)?(\d{5,12})\b", re.IGNORECASE)


def find_order_id(text):
    m = ORDER_ID_RE.search(text.replace(",", ""))
    return m.group(0).strip() if m else None


def best_entry(norm_text):
    best, best_score = None, 0
    for e in KB["entries"]:
        score = sum(len(normalise(t).split()) for t in e["triggers"] if contains(norm_text, t))
        if score == 0:
            continue
        key = (score, e.get("priority", 0))
        if best is None or key > (best_score, best.get("priority", 0)):
            best, best_score = e, score
    return best, best_score


# ---------------------------------------------------------------- Gemma 4 brain
def load_env_file():
    """Tiny .env reader (no extra package). Lines look like KEY=value. Never commit this file."""
    path = os.path.join(BASE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_file()


def ai_key():
    return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def ai_model():
    return os.environ.get("GEMMA_MODEL", "gemma-4-26b-a4b-it")


def parse_ai_json(text):
    """Gemma may wrap JSON in text or code fences. Pull out the first {...} object."""
    text = text.strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b <= a:
        return None
    try:
        data = json.loads(text[a : b + 1])
        answer = str(data["answer"]).strip()
        if not answer:
            return None
        return answer, bool(data.get("escalate"))
    except Exception:
        return None


def build_system_prompt(lang="en"):
    facts = "\n".join(f"- [{e['topic']}] {e['answer']}" for e in KB["entries"])
    return (
        "You are Vera, a warm, calm AI voice agent for Kartify, an Indian online shopping platform. "
        "The customer is speaking on a phone call, so answer in 1 to 3 short, natural spoken sentences. "
        "Use ONLY the facts below. Never invent policies, prices, timelines, discounts or offers. "
        f"The customer may speak English, Hindi, Marathi or Hinglish; always reply in {LANG_NAMES.get(lang, LANG_NAMES['en'])}. "
        "Never ask for card numbers, OTPs, PINs or passwords. Apologise sincerely when something went wrong. "
        "Set escalate to true if the question is not covered by the facts, or involves a legal threat, fraud, "
        "abuse, a complex dispute, a refund that is already overdue, or a request for a human. "
        "When escalate is true, your answer must be only a short empathetic sentence; the system adds the callback line.\n"
        'Reply with ONLY a JSON object, no other text: {"answer": "...", "escalate": true or false}\n\n'
        "FACTS:\n" + facts
    )


def ai_answer(message, history, lang="en"):
    """Ask Gemma 4 (through the Gemini API). Returns (answer, escalate) or None if unavailable."""
    key = ai_key()
    if not key:
        return None
    try:
        import urllib.request

        convo = "\n".join(f"{r}: {t}" for r, t in history[-6:]) + f"\nCustomer: {message}"
        gen_cfg = {"temperature": 0.2, "maxOutputTokens": 500}
        if os.environ.get("GEMMA_THINKING"):  # optional: "minimal" for faster replies
            gen_cfg["thinkingConfig"] = {"thinkingLevel": os.environ["GEMMA_THINKING"]}
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": build_system_prompt(lang)}]},
                "contents": [{"role": "user", "parts": [{"text": convo}]}],
                "generationConfig": gen_cfg,
            }
        ).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{ai_model()}:generateContent",
            data=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": key},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            out = json.loads(r.read())
        parts = out["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        return parse_ai_json(text)
    except Exception as exc:  # any failure (no internet, rate limit, bad reply) -> rules mode
        print("Gemma call failed, using rules instead:", exc)
        return None


# ---------------------------------------------------------------- core logic
def respond(session_id, message, lang="en"):
    sess = SESSIONS.setdefault(session_id, {"order_id": None, "asked_order": False, "turns": 0, "history": []})
    sess["turns"] += 1
    lang = lang if lang in LANGS else "en"
    ESC = T("escalation", lang)
    raw = message.strip()
    norm = normalise(raw)

    def reply(text, escalated=False, topic="", mode="rules", reason="", out_lang=None):
        sess["history"].append(("Customer", raw))
        sess["history"].append(("Vera", text))
        if escalated:
            log_escalation(session_id, sess["order_id"], reason or topic, raw)
        return {
            "reply": text,
            "escalated": escalated,
            "topic": topic,
            "order_id": sess["order_id"],
            "mode": mode,
            "lang": out_lang or lang,
        }

    if not raw:
        return reply(T("unclear", lang), topic="Unclear")

    # Order ID spoken or typed
    oid = find_order_id(raw)
    if oid:
        sess["order_id"] = oid
        leftover = normalise(ORDER_ID_RE.sub("", raw).strip(" ,.-"))
        only_id = best_entry(leftover)[0] is None and not any_trigger(leftover, KB["hard_escalation_triggers"])
        if only_id:
            return reply(T("noted", lang, oid=oid), topic="Order ID")

    # Safety first: human requests, legal threats, abuse
    if any_trigger(norm, KB["hard_escalation_triggers"]):
        return reply(ESC, True, "Escalation", reason="Customer asked for a human / legal or fraud issue")
    if any_trigger(norm, KB["abuse_words"]):
        return reply(ESC, True, "Escalation", reason="Abusive language")

    # Small talk
    if any_trigger(norm, KB["bye_triggers"]):
        return reply(T("bye", lang), topic="Goodbye")
    if len(norm.split()) <= 4 and any_trigger(norm, KB["thanks_triggers"]):
        return reply(T("thanks", lang), topic="Thanks")
    if len(norm.split()) <= 3 and any_trigger(norm, KB["greet_triggers"]):
        return reply(T("greet", lang), topic="Greeting")

    # Optional AI brain
    ai = ai_answer(raw, sess["history"], lang)
    if ai:
        text, esc = ai
        if esc and ESC not in text:
            text = f"{text} {ESC}".strip()
        return reply(text, esc, "Gemma 4 answer", mode="gemma", reason="Gemma 4 judged: outside policy")

    # Rules brain
    entry, score = best_entry(norm)
    if entry is None:
        return reply(ESC, True, "Not in policy", reason="Question not covered by policy")

    translated = entry.get("answer_" + lang)
    out = lang if (translated or lang == "en") else "en"
    text = translated or entry["answer"]
    if entry.get("escalate"):
        line = ESC if out == lang else ESC
        return reply(line if out != lang else f"{text} {ESC}", True, entry["topic"], reason=entry["id"].replace("_", " "), out_lang=lang)

    if entry.get("order_specific") and not sess["order_id"] and not sess["asked_order"]:
        sess["asked_order"] = True
        text += T("askorder", out)
    return reply(text, False, entry["topic"], out_lang=out)


# ---------------------------------------------------------------- routes
@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/escalations")
def escalations_page():
    return send_from_directory(app.static_folder, "escalations.html")


@app.post("/api/start")
def api_start():
    body = request.get_json(silent=True) or {}
    sid = body.get("session_id") or uuid.uuid4().hex[:10]
    lang = body.get("lang") if body.get("lang") in LANGS else "en"
    SESSIONS[sid] = {"order_id": None, "asked_order": False, "turns": 0, "history": []}
    return jsonify({"session_id": sid, "lang": lang, "reply": T("greeting", lang), "ai_mode": bool(ai_key()), "model": ai_model() if ai_key() else None})


@app.post("/api/chat")
def api_chat():
    data = request.get_json(silent=True) or {}
    sid = data.get("session_id") or uuid.uuid4().hex[:10]
    out = respond(sid, str(data.get("message", ""))[:500], data.get("lang", "en"))
    out["session_id"] = sid
    return jsonify(out)


@app.get("/api/escalations")
def api_escalations():
    with db() as con:
        rows = con.execute("SELECT * FROM escalations ORDER BY id DESC LIMIT 100").fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/escalations/clear")
def api_clear():
    with db() as con:
        con.execute("DELETE FROM escalations")
    return jsonify({"ok": True})


@app.get("/api/health")
def health():
    return jsonify({"ok": True, "time": time.time(), "ai_mode": bool(ai_key()), "model": ai_model() if ai_key() else None})


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Vera is running ->  http://localhost:{port}\n  Escalations page ->  http://localhost:{port}/escalations\n")
    app.run(host="127.0.0.1", port=port, debug=False)
