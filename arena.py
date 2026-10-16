"""Vera Arena: runs scripted customer scenarios and scores the results. Uses rules mode so results are repeatable."""
import uuid

# (name, category, language, messages, expect_escalate, [answer must contain ANY of these], expected action status or None)
SCENARIOS = [
    ("Track an order out for delivery", "Order status", "en", ["Where is order 56567?"], False, ["out for delivery"], None),
    ("Track a shipped order", "Order status", "en", ["order 10001"], False, ["shipped"], None),
    ("Track order in Hindi", "Languages", "hi", ["ऑर्डर 56567 कहाँ है?"], False, ["डिलीवरी के लिए"], None),
    ("Track order in Marathi", "Languages", "mr", ["ऑर्डर 56567 कुठे आहे?"], False, ["डिलिव्हरीसाठी"], None),
    ("Cancel order in Hindi", "Languages", "hi", ["ऑर्डर 56574 रद्द करें"], False, ["रद्द हो गया"], "Successful"),
    ("Unknown order number", "Order status", "en", ["where is order 99999"], False, ["couldn't find"], None),
    ("Cancel an order not yet shipped", "Actions", "en", ["Cancel order 10004"], False, ["is cancelled"], "Successful"),
    ("Cancel an order already shipped", "Actions", "en", ["cancel order 10001"], False, ["can't be cancelled"], "Failed"),
    ("Return inside the return window", "Actions", "en", ["I want to return order 77389"], False, ["pending"], "Pending"),
    ("Return after the window closed", "Handover", "en", ["I want to return order 98234"], True, ["window has closed"], "Failed"),
    ("Delayed order", "Handover", "en", ["order 10006"], True, ["delayed"], None),
    ("Refund status check", "Order status", "en", ["order 10003", "what is my refund status"], False, ["under review"], None),
    ("Refund timeline policy", "Policy", "en", ["When will I get my refund?"], False, ["5 to 7"], None),
    ("Exchange policy", "Policy", "en", ["Can I exchange this for a different size?"], False, ["exchange"], None),
    ("Damaged product", "Policy", "en", ["My product arrived broken"], False, ["sorry", "replacement"], None),
    ("Customer asks for a manager", "Handover", "en", ["I want to speak to a manager"], True, ["specialist"], None),
    ("Legal threat", "Handover", "en", ["I will take this to consumer court"], True, ["specialist"], None),
    ("Money deducted but no order", "Policy", "en", ["My money was deducted but I got no order"], False, ["deducted", "payment", "bank"], None),
    ("OTP or security issue", "Handover", "en", ["Someone is asking me for my OTP"], True, ["specialist"], None),
    ("Abusive customer", "Handover", "en", ["you idiots are useless"], True, ["specialist"], None),
    ("Question outside the policy", "Handover", "en", ["Can you give me stock tips?"], True, ["specialist"], None),
]


def run(respond, sessions, orders):
    orders.reset()
    rows = []
    for name, cat, lang, msgs, exp_esc, must, exp_act in SCENARIOS:
        sid = "arena-" + uuid.uuid4().hex[:8]
        sessions[sid] = {"order_id": None, "asked_order": False, "turns": 0, "history": [], "dry": True}
        steps, out = [], {}
        for m in msgs:
            out = respond(sid, m, lang)
            steps.append({"customer": m, "vera": out["reply"]})
        act = (out.get("card") or {}).get("action")
        act_status = act["status"] if act else None
        accurate = any(k.lower() in out["reply"].lower() for k in must) and (exp_act is None or act_status == exp_act)
        esc_ok = bool(out["escalated"]) == exp_esc
        rows.append({"name": name, "category": cat, "steps": steps, "expect_escalate": exp_esc, "escalated": bool(out["escalated"]),
                     "action": act_status, "expect_action": exp_act, "accurate": accurate, "esc_ok": esc_ok,
                     "resolved": (accurate and not out["escalated"]) if not exp_esc else None})
        sessions.pop(sid, None)
    orders.reset()  # leave the demo data clean
    n = len(rows)
    solv = [r for r in rows if r["resolved"] is not None]
    pct = lambda a, b: round(100 * a / b) if b else 0
    return {"rows": rows, "metrics": {
        "accuracy": pct(sum(r["accurate"] for r in rows), n),
        "escalations": pct(sum(r["esc_ok"] for r in rows), n),
        "resolutions": pct(sum(bool(r["resolved"]) for r in solv), len(solv)),
        "total": n, "passed": sum(r["accurate"] and r["esc_ok"] for r in rows)}}
