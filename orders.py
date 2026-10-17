"""Demo orders database + simulated backend actions (cancel / refund) for Vera. All data is fictional."""
from datetime import datetime, timedelta

_db = None
# id, customer, product, category, status, day (+N = expected in N days, -N = delivered N days ago), amount
SEED = [
    ("56567", "Rohan Mehta", "Wireless Earphones", "electronics", "Out for delivery", 0, 2499),
    ("10001", "Ananya Iyer", "Wireless Headphones", "electronics", "Shipped", 3, 3999),
    ("10002", "Karan Malhotra", "Smart Watch", "electronics", "Out for delivery", 0, 4499),
    ("10003", "Imran Sheikh", "Bluetooth Speaker", "electronics", "Refund under review", -4, 1999),
    ("10004", "Priya Nair", "Laptop Backpack", "accessories", "Processing", 5, 1299),
    ("10005", "Vikram Rao", "USB-C Charger", "electronics", "Refund approved", -8, 899),
    ("10006", "Sneha Kulkarni", "Gaming Mouse", "electronics", "Delayed", 6, 1599),
    ("56568", "Meera Joshi", "Cotton T-Shirt (M)", "fashion", "Delivered", -2, 599),
    ("56569", "Arjun Singh", "Running Shoes", "fashion", "Shipped", 2, 2799),
    ("56570", "Fatima Khan", "Air Fryer", "home", "Delivered", -12, 5499),
    ("56572", "Divya Reddy", "Yoga Mat", "sports", "Cancelled", 0, 799),
    ("56573", "Suresh Patil", "Mixer Grinder", "home", "Return requested", -5, 3299),
    ("56574", "Neha Gupta", "Kurta Set", "fashion", "Processing", 4, 1499),
    ("98234", "Aman Verma", "Noise-Cancelling Earphones", "electronics", "Delivered", -11, 3299),
    ("45112", "Pooja Shah", "Cotton T-Shirt (M)", "fashion", "Shipped", 1, 599),
    ("77389", "Rahul Deshmukh", "Smartphone XYZ", "electronics", "Delivered", -3, 18999),
    ("56575", "Kavya Menon", "Desk Lamp", "home", "Out for delivery", 0, 999),
    ("56576", "Harsh Vora", "Power Bank 20000mAh", "electronics", "Delayed", 4, 1799),
]


def setup(db_func):
    global _db
    _db = db_func
    with _db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, customer TEXT, product TEXT,
                       category TEXT, status TEXT, day INTEGER, amount INTEGER)""")
        con.execute("""CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT,
                       order_id TEXT, action TEXT, status TEXT, detail TEXT, ref TEXT)""")
        if con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0:
            con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", SEED)


def reset():
    with _db() as con:
        con.execute("DELETE FROM orders"); con.execute("DELETE FROM actions")
        con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", SEED)


_DAYS = {"en": ("today", "tomorrow"), "hi": ("आज", "कल"), "mr": ("आज", "उद्या")}


def _date(day, lang="en"):
    if day in (0, 1):
        return _DAYS.get(lang, _DAYS["en"])[day]
    return (datetime.now() + timedelta(days=day)).strftime("%d %b")


def _view(r):
    o = dict(r)
    o["window"] = 10 if o["category"] == "electronics" else 7
    if o["status"] in ("Delivered", "Return requested", "Refund under review", "Refund approved"):
        o["when"] = f"Delivered {-o['day']} days ago"
    elif o["status"] == "Cancelled":
        o["when"] = "-"
    else:
        o["when"] = "Expected " + _date(o["day"]).capitalize() if o["day"] <= 1 else "Expected " + _date(o["day"])
    return o


def find_id(text):
    import re
    m = re.search(r"\b(?:(?:ORD|KRT|KR|OD)[- ]?)?(\d{5,12})\b", text.replace(",", ""))
    if not m:  # speech sometimes splits digits: "56 567"
        m = re.search(r"\b(\d{2,3})[ -](\d{2,3})\b", text)
        return (m.group(1) + m.group(2)) if m and len(m.group(1) + m.group(2)) >= 5 else None
    return m.group(1)


def get(oid):
    with _db() as con:
        r = con.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    return _view(r) if r else None


def all_orders():
    with _db() as con:
        return [_view(r) for r in con.execute("SELECT * FROM orders ORDER BY rowid")]


def all_actions():
    with _db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 50")]


# Language Bridge: every spoken line exists in English, Hindi and Marathi. i=order id, p=product, d=date, n=days, w=window
TXT = {
 "out": {"en": "Order {i} is your {p}, and it is out for delivery. It should reach you today.",
         "hi": "ऑर्डर {i} ({p}) डिलीवरी के लिए निकल चुका है। यह आज आप तक पहुँच जाएगा।",
         "mr": "ऑर्डर {i} ({p}) डिलिव्हरीसाठी निघाली आहे. ती आज तुमच्यापर्यंत पोहोचेल."},
 "ship": {"en": "Order {i}, your {p}, has shipped and is expected {d}.",
          "hi": "ऑर्डर {i} ({p}) शिप हो चुका है और {d} तक पहुँचेगा।",
          "mr": "ऑर्डर {i} ({p}) पाठवली गेली आहे आणि {d} पर्यंत पोहोचेल."},
 "proc": {"en": "Order {i}, your {p}, is being prepared and is expected {d}. It has not shipped yet, so it can still be cancelled for free.",
          "hi": "ऑर्डर {i} ({p}) तैयार हो रहा है और {d} तक पहुँचेगा। यह अभी शिप नहीं हुआ है, इसलिए इसे मुफ़्त में रद्द किया जा सकता है।",
          "mr": "ऑर्डर {i} ({p}) तयार केली जात आहे आणि {d} पर्यंत पोहोचेल. ती अजून पाठवलेली नाही, त्यामुळे मोफत रद्द करता येईल."},
 "delay": {"en": "I'm sorry, order {i}, your {p}, is delayed. The new expected date is {d}.",
           "hi": "क्षमा कीजिए, ऑर्डर {i} ({p}) में देरी हो रही है। नई अनुमानित तारीख {d} है।",
           "mr": "क्षमस्व, ऑर्डर {i} ({p}) ला उशीर होत आहे. नवीन अपेक्षित तारीख {d} आहे."},
 "canc": {"en": "Order {i}, your {p}, has been cancelled.", "hi": "ऑर्डर {i} ({p}) रद्द किया जा चुका है।", "mr": "ऑर्डर {i} ({p}) रद्द झाली आहे."},
 "retreq": {"en": "A return is already requested for order {i}, your {p}, and it is being processed.",
            "hi": "ऑर्डर {i} ({p}) के लिए रिटर्न का अनुरोध पहले से दर्ज है और प्रक्रिया में है।",
            "mr": "ऑर्डर {i} ({p}) साठी रिटर्नची विनंती आधीच नोंदवली आहे आणि प्रक्रिया सुरू आहे."},
 "revw": {"en": "The refund for order {i}, your {p}, is under review. Refunds are processed within 5 to 7 business days after we receive the item.",
          "hi": "ऑर्डर {i} ({p}) का रिफंड समीक्षा में है। सामान मिलने के 5 से 7 कार्य दिवसों में रिफंड हो जाता है।",
          "mr": "ऑर्डर {i} ({p}) चा परतावा तपासणीत आहे. वस्तू मिळाल्यापासून 5 ते 7 कामकाजाच्या दिवसांत परतावा होतो."},
 "rapp": {"en": "The refund for order {i}, your {p}, is approved and processing, which takes 5 to 7 business days.",
          "hi": "ऑर्डर {i} ({p}) का रिफंड मंज़ूर हो गया है और प्रोसेस हो रहा है। इसमें 5 से 7 कार्य दिवस लगते हैं।",
          "mr": "ऑर्डर {i} ({p}) चा परतावा मंजूर झाला आहे आणि प्रक्रिया सुरू आहे. यास 5 ते 7 कामकाजाचे दिवस लागतात."},
 "dl_in": {"en": "Order {i}, your {p}, was delivered {n} days ago. It is still inside the {w}-day return window.",
           "hi": "ऑर्डर {i} ({p}) {n} दिन पहले डिलीवर हुआ था। यह अभी {w} दिन की रिटर्न अवधि में है।",
           "mr": "ऑर्डर {i} ({p}) {n} दिवसांपूर्वी डिलिव्हर झाली. ती अजून {w} दिवसांच्या रिटर्न कालावधीत आहे."},
 "dl_out": {"en": "Order {i}, your {p}, was delivered {n} days ago. The {w}-day return window has closed.",
            "hi": "ऑर्डर {i} ({p}) {n} दिन पहले डिलीवर हुआ था। {w} दिन की रिटर्न अवधि समाप्त हो चुकी है।",
            "mr": "ऑर्डर {i} ({p}) {n} दिवसांपूर्वी डिलिव्हर झाली. {w} दिवसांचा रिटर्न कालावधी संपला आहे."},
 "nf": {"en": "I couldn't find order {i} in our system. Could you check the number? I can also arrange a specialist callback.",
        "hi": "मुझे ऑर्डर {i} हमारे सिस्टम में नहीं मिला। क्या आप नंबर दोबारा देख सकते हैं? मैं विशेषज्ञ कॉलबैक भी करवा सकती हूँ।",
        "mr": "मला ऑर्डर {i} आमच्या सिस्टममध्ये सापडली नाही. कृपया क्रमांक तपासाल का? मी तज्ज्ञ कॉलबॅकही ठरवू शकते."},
 "c_ok": {"en": "Done. Our system has confirmed that order {i}, your {p}, is cancelled. Reference {ref}.",
          "hi": "हो गया। हमारे सिस्टम ने पुष्टि की है कि ऑर्डर {i} ({p}) रद्द हो गया है। रेफ़रेंस {ref}।",
          "mr": "झाले. आमच्या सिस्टमने पुष्टी केली आहे की ऑर्डर {i} ({p}) रद्द झाली आहे. संदर्भ {ref}."},
 "c_ship": {"en": "I couldn't cancel order {i} because it has already shipped, and shipped orders can't be cancelled. You can return it after delivery. Nothing was changed.",
            "hi": "मैं ऑर्डर {i} रद्द नहीं कर सकी क्योंकि वह शिप हो चुका है, और शिप हुए ऑर्डर रद्द नहीं होते। डिलीवरी के बाद आप उसे रिटर्न कर सकते हैं। कुछ भी बदला नहीं गया है।",
            "mr": "मी ऑर्डर {i} रद्द करू शकले नाही, कारण ती पाठवली गेली आहे आणि पाठवलेल्या ऑर्डर रद्द होत नाहीत. डिलिव्हरीनंतर तुम्ही ती परत करू शकता. काहीही बदललेले नाही."},
 "c_done": {"en": "I couldn't cancel order {i} because it is already cancelled. Nothing was changed.",
            "hi": "ऑर्डर {i} पहले ही रद्द हो चुका है, इसलिए कुछ नहीं बदला गया।", "mr": "ऑर्डर {i} आधीच रद्द झाली आहे, त्यामुळे काहीही बदललेले नाही."},
 "c_dlv": {"en": "I couldn't cancel order {i} because it has already been delivered. You can return it instead. Nothing was changed.",
           "hi": "ऑर्डर {i} डिलीवर हो चुका है, इसलिए रद्द नहीं हो सकता। आप उसे रिटर्न कर सकते हैं। कुछ नहीं बदला गया।",
           "mr": "ऑर्डर {i} डिलिव्हर झाली आहे, त्यामुळे रद्द करता येत नाही. तुम्ही ती परत करू शकता. काहीही बदललेले नाही."},
 "r_ok": {"en": "I've submitted a return and refund request for order {i}, your {p}. Its status is Pending, reference {ref}. The refund is processed within 5 to 7 business days after we receive the item.",
          "hi": "मैंने ऑर्डर {i} ({p}) के लिए रिटर्न और रिफंड का अनुरोध जमा कर दिया है। स्थिति Pending है, रेफ़रेंस {ref}। सामान मिलने के 5 से 7 कार्य दिवसों में रिफंड होगा।",
          "mr": "मी ऑर्डर {i} ({p}) साठी रिटर्न आणि परताव्याची विनंती सादर केली आहे. स्थिती Pending आहे, संदर्भ {ref}. वस्तू मिळाल्यापासून 5 ते 7 कामकाजाच्या दिवसांत परतावा होईल."},
 "r_win": {"en": "I couldn't submit a return for order {i}: the {w}-day return window has closed. Nothing was changed.",
           "hi": "मैं ऑर्डर {i} का रिटर्न जमा नहीं कर सकी: {w} दिन की रिटर्न अवधि समाप्त हो चुकी है। कुछ नहीं बदला गया।",
           "mr": "मी ऑर्डर {i} चे रिटर्न सादर करू शकले नाही: {w} दिवसांचा रिटर्न कालावधी संपला आहे. काहीही बदललेले नाही."},
 "r_prog": {"en": "I couldn't submit a return for order {i}: a return or refund is already in progress. Nothing was changed.",
            "hi": "ऑर्डर {i} के लिए रिटर्न या रिफंड पहले से प्रक्रिया में है। कुछ नहीं बदला गया।",
            "mr": "ऑर्डर {i} साठी रिटर्न किंवा परतावा आधीच सुरू आहे. काहीही बदललेले नाही."},
 "r_canc": {"en": "I couldn't submit a return for order {i}: this order is cancelled. Nothing was changed.",
            "hi": "ऑर्डर {i} रद्द है, इसलिए रिटर्न नहीं हो सकता। कुछ नहीं बदला गया।", "mr": "ऑर्डर {i} रद्द आहे, त्यामुळे रिटर्न करता येत नाही. काहीही बदललेले नाही."},
 "r_und": {"en": "I couldn't submit a return for order {i}: it has not been delivered yet. You can return it after delivery. Nothing was changed.",
           "hi": "ऑर्डर {i} अभी डिलीवर नहीं हुआ है। डिलीवरी के बाद आप उसे रिटर्न कर सकते हैं। कुछ नहीं बदला गया।",
           "mr": "ऑर्डर {i} अजून डिलिव्हर झालेली नाही. डिलिव्हरीनंतर तुम्ही ती परत करू शकता. काहीही बदललेले नाही."},
}


def tr(key, lang="en", **kw):
    return TXT[key].get(lang, TXT[key]["en"]).format(**kw)


def describe(o, lang="en"):
    """What the DATABASE says, in a spoken sentence. Returns (text, handover_reason or None)."""
    s = o["status"]
    kw = dict(i=o["id"], p=o["product"], d=_date(o["day"], lang), n=-o["day"], w=o["window"])
    key = {"Out for delivery": "out", "Shipped": "ship", "Processing": "proc", "Delayed": "delay", "Cancelled": "canc",
           "Return requested": "retreq", "Refund under review": "revw", "Refund approved": "rapp"}.get(s)
    if not key:
        key = "dl_in" if -o["day"] <= o["window"] else "dl_out"
    return tr(key, lang, **kw), ("Delayed order" if s == "Delayed" else None)


def _log(oid, action, status, detail):
    with _db() as con:
        cur = con.execute("INSERT INTO actions (ts,order_id,action,status,detail) VALUES (?,?,?,?,?)",
                          (datetime.now().strftime("%d %b, %I:%M:%S %p"), oid, action, status, detail))
        ref = f"KR-{1000 + cur.lastrowid}"
        con.execute("UPDATE actions SET ref=? WHERE id=?", (ref, cur.lastrowid))
    return ref


def _set(oid, status):
    with _db() as con:
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))


def cancel(o, lang="en"):
    """Simulated backend. Returns (spoken text, action dict, handover_reason)."""
    s, kw = o["status"], dict(i=o["id"], p=o["product"], w=o["window"])
    if s == "Processing":
        _set(o["id"], "Cancelled"); ref = _log(o["id"], "Cancel order", "Successful", "Cancelled before shipping")
        return tr("c_ok", lang, ref=ref, **kw), {"name": "Cancel order", "status": "Successful", "ref": ref}, None
    key = "c_done" if s == "Cancelled" else "c_ship" if s in ("Shipped", "Out for delivery", "Delayed") else "c_dlv"
    ref = _log(o["id"], "Cancel order", "Failed", key)
    return tr(key, lang, **kw), {"name": "Cancel order", "status": "Failed", "ref": ref}, None


def refund(o, lang="en"):
    s, n, kw = o["status"], -o["day"], dict(i=o["id"], p=o["product"], w=o["window"])
    if s == "Delivered" and n <= o["window"]:
        _set(o["id"], "Return requested"); ref = _log(o["id"], "Return + refund", "Pending", "Awaiting pickup and item check")
        return tr("r_ok", lang, ref=ref, **kw), {"name": "Return + refund", "status": "Pending", "ref": ref}, None
    key, esc = (("r_win", "Return window closed, needs human review") if s == "Delivered" else
                ("r_prog", None) if s in ("Return requested", "Refund under review", "Refund approved") else
                ("r_canc", None) if s == "Cancelled" else ("r_und", None))
    ref = _log(o["id"], "Return + refund", "Failed", key)
    return tr(key, lang, **kw), {"name": "Return + refund", "status": "Failed", "ref": ref}, esc
