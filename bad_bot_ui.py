from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from datetime import datetime, timezone
from pathlib import Path
import json
import re
import random
import requests
from difflib import get_close_matches

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

BASE_DIR = Path(__file__).resolve().parent
COMPLAINTS_STORE_PATH = BASE_DIR / "complaints_store.json"
DASHBOARD_DIR = BASE_DIR / "dashboard-UI"

# MODEL API PORT
MODEL_API_URL = "http://127.0.0.1:8001/predict"

ESCALATION_MESSAGE = (
    "I understand your concern. I am connecting you to customer support now. "
    "A support specialist will join shortly."
)


def initialize_session():
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
    session['issue_type'] = None
    session['escalation_count'] = 0
    session['details'] = {}
    session['order_attempts'] = 0
    session['conversation_history'] = []
    session['escalation_logged'] = False
    session['clarification_attempts'] = 0
    session['last_detected_intent'] = None
    session['last_user_message'] = ""


def load_complaints_store():
    default_store = {"active": [], "resolved": []}

    if not COMPLAINTS_STORE_PATH.exists():
        app.logger.warning("Complaints store missing. Creating %s", COMPLAINTS_STORE_PATH)
        save_complaints_store(default_store)
        return default_store

    try:
        with COMPLAINTS_STORE_PATH.open("r", encoding="utf-8") as store_file:
            store = json.load(store_file)
    except (json.JSONDecodeError, OSError) as exc:
        app.logger.exception("Failed to read complaints store: %s", exc)
        save_complaints_store(default_store)
        return default_store

    if not isinstance(store, dict):
        app.logger.warning("Complaints store had invalid structure. Resetting.")
        save_complaints_store(default_store)
        return default_store

    store.setdefault("active", [])
    store.setdefault("resolved", [])

    if not isinstance(store["active"], list):
        app.logger.warning("Active complaints entry was invalid. Resetting active list.")
        store["active"] = []

    if not isinstance(store["resolved"], list):
        app.logger.warning("Resolved complaints entry was invalid. Resetting resolved list.")
        store["resolved"] = []

    return store


def save_complaints_store(store):
    with COMPLAINTS_STORE_PATH.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, indent=2)


def build_complaint_record(reason, confidence=None):
    history = session.get("conversation_history", [])
    issue_type = session.get("issue_type")
    order_id = session.get("order_id")
    last_customer_message = ""

    for entry in reversed(history):
        if entry.startswith("User: "):
            last_customer_message = entry[6:]
            break

    complaint_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")

    issue_map = {
        "missing": "Customer reports a missing or damaged item.",
        "delay": "Customer reports a delayed order.",
        "refund": "Customer reports a refund or payment issue.",
        "address": "Customer requests an address or contact correction.",
        "cancel": "Customer requests order cancellation support.",
        "track": "Customer needs order tracking assistance.",
    }

    complaint = {
        "id": complaint_id,
        "confidence": f"{confidence:.2f}" if isinstance(confidence, (int, float)) else "N/A",
        "reason": reason,
        "issue": issue_map.get(issue_type, "Customer requested human support."),
        "escalation_reason": "Customer issue remained unresolved after repeated bot guidance, and the customer needs human support.",
        "last_customer_message": last_customer_message,
        "order_id": order_id,
        "bot_failure": history[-1] if history else "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }

    return complaint


def record_escalation(reason, confidence=None):
    if session.get("escalation_logged"):
        app.logger.info("Skipping duplicate escalation log for current session.")
        return

    store = load_complaints_store()
    complaint = build_complaint_record(reason=reason, confidence=confidence)
    store["active"].insert(0, complaint)
    save_complaints_store(store)
    session["escalation_logged"] = True
    app.logger.info("Stored escalation complaint %s", complaint["id"])


def resolve_complaint_by_id(complaint_id):
    store = load_complaints_store()
    active_complaints = store.get("active", [])

    for index, complaint in enumerate(active_complaints):
        if str(complaint.get("id")) == str(complaint_id):
            resolved_complaint = active_complaints.pop(index)
            resolved_complaint["status"] = "resolved"
            resolved_complaint["resolved_timestamp"] = datetime.now(timezone.utc).isoformat()
            store["resolved"].insert(0, resolved_complaint)
            save_complaints_store(store)
            app.logger.info("Resolved complaint %s", complaint_id)
            return resolved_complaint

    return None

# ==========================================
# IMPROVED PATTERNS
# ==========================================

missing_patterns = r"(missing|not received|didn'?t receive|didn'?t get|broken|damaged|wrong|incorrect|defective|lost|empty|never arrived)"
delay_patterns = r"(late|delay|not arrived|taking too long|where is it|still waiting|hasn'?t come|when is it)"
track_patterns = r"(track|status|where is my|when will it|update on)"
refund_patterns = r"(refund|money back|charge|double payment|payment|reimburse|return my money)"
cancel_patterns = r"(cancel|stop|don'?t want|abort|changed my mind)"
address_patterns = r"(address|phone number|wrong location|delivered to wrong|update details)"

INTENT_KEYWORDS = {
    "missing": [
        "missing", "not received", "didnt receive", "didn't receive", "broken", "damaged",
        "wrong item", "incorrect", "defective", "lost", "empty package", "replacement"
    ],
    "delay": [
        "late", "delay", "delayed", "taking too long", "still waiting", "hasn't come",
        "hasnt come", "slow delivery", "running late"
    ],
    "track": [
        "track", "tracking", "status", "where is my order", "where is my food",
        "when will it arrive", "delivery update", "order update"
    ],
    "refund": [
        "refund", "money back", "reimburse", "return my money", "refund status",
        "payment issue", "charged twice", "double payment"
    ],
    "cancel": [
        "cancel", "stop order", "abort", "changed my mind", "cancel my order"
    ],
    "address": [
        "address", "change address", "update address", "phone number",
        "contact number", "wrong location", "new address"
    ],
}

NEGATIVE_WORDS = {
    "angry", "annoyed", "bad", "frustrated", "terrible", "useless", "ridiculous",
    "worst", "hate", "stupid", "slow", "upset", "disappointed", "unacceptable"
}

SEVERE_ESCALATION_WORDS = {
    "complaint", "fraud", "scam", "lawyer", "legal", "supervisor",
    "chargeback", "urgent", "emergency", "harassment"
}

HELP_WORDS = {"help", "support", "fix", "solve", "resolve", "anyone"}
HUMAN_REQUEST_PATTERNS = [
    r"\bhuman\b", r"\bagent\b", r"\brepresentative\b", r"\bmanager\b",
    r"\bcustomer care\b", r"\bperson\b", r"\bcall me\b", r"\bconnect me\b"
]
CLARIFYING_QUESTION = (
    "I want to make sure I understand correctly. Is this about tracking, delay, refund, address change, cancellation, or a missing item?"
)


# ==========================================
# INTENT DETECTION
# ==========================================

def normalize_text(text):
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()


def get_intent_from_text(text):
    normalized = normalize_text(text)

    if re.search(missing_patterns, normalized):
        return "missing", 0.95

    if re.search(track_patterns, normalized):
        return "track", 0.95

    if re.search(delay_patterns, normalized):
        return "delay", 0.92

    if re.search(refund_patterns, normalized):
        return "refund", 0.94

    if re.search(cancel_patterns, normalized):
        return "cancel", 0.92

    if re.search(address_patterns, normalized):
        return "address", 0.93

    fuzzy_map = {
        "refund": "refund", "refnd": "refund", "money": "refund",
        "delay": "delay", "late": "delay", "dely": "delay",
        "missing": "missing", "msing": "missing", "lost": "missing",
        "cancel": "cancel", "cncel": "cancel", "stop": "cancel",
        "address": "address", "location": "address",
        "track": "track", "trak": "track", "status": "track"
    }

    best_intent = None
    best_score = 0.0

    for intent, phrases in INTENT_KEYWORDS.items():
        if any(phrase in normalized for phrase in phrases):
            return intent, 0.88

    for word in normalized.split():
        matches = get_close_matches(word, list(fuzzy_map.keys()), n=1, cutoff=0.6)
        if matches:
            score = 0.72 if word == matches[0] else 0.64
            if score > best_score:
                best_intent = fuzzy_map[matches[0]]
                best_score = score

    return best_intent, best_score


# ==========================================
# CONVERSATION HISTORY
# ==========================================

def append_conversation(role, message):
    history = session.get("conversation_history", [])
    history.append(f"{role}: {message}")
    session["conversation_history"] = history[-20:]


def bot_reply(message):
    append_conversation("Bot", message)
    return jsonify({"response": message})


def get_recent_user_messages(limit=6):
    history = session.get("conversation_history", [])
    user_messages = []

    for entry in reversed(history):
        if entry.startswith("User: "):
            user_messages.append(entry[6:])
        if len(user_messages) >= limit:
            break

    return list(reversed(user_messages))


def get_last_user_message():
    messages = get_recent_user_messages(limit=1)
    return messages[0] if messages else ""


def user_requested_human(user_text):
    return any(re.search(pattern, user_text) for pattern in HUMAN_REQUEST_PATTERNS)


def has_severe_escalation_signal(user_text):
    normalized = normalize_text(user_text)
    return any(word in normalized for word in SEVERE_ESCALATION_WORDS)


def calculate_frustration_score(user_text):
    normalized = normalize_text(user_text)
    recent_user_messages = [normalize_text(message) for message in get_recent_user_messages()]
    frustration_score = 0

    # Repeated exact or near-exact messages are a strong sign the user feels stuck.
    if recent_user_messages.count(normalized) >= 2:
        frustration_score += 3

    if session.get("last_user_message") == normalized:
        frustration_score += 2

    negative_count = sum(1 for word in normalized.split() if word in NEGATIVE_WORDS)
    frustration_score += negative_count * 2

    help_count = sum(1 for word in normalized.split() if word in HELP_WORDS)
    frustration_score += help_count

    if user_requested_human(normalized):
        frustration_score += 4

    if "again" in normalized or "still" in normalized or "same" in normalized:
        frustration_score += 1

    if session.get("clarification_attempts", 0) >= 2:
        frustration_score += 2

    return frustration_score


def should_escalate_for_repetition(user_text):
    normalized = normalize_text(user_text)
    recent_user_messages = [normalize_text(message) for message in get_recent_user_messages(limit=4)]

    if len(recent_user_messages) < 3:
        return False

    return recent_user_messages.count(normalized) >= 2


def has_clear_escalation_reason(user_text, frustration_score):
    normalized = normalize_text(user_text)

    return any([
        has_severe_escalation_signal(normalized),
        should_escalate_for_repetition(normalized),
        frustration_score >= 5,
        "still" in normalized,
        "again" in normalized,
        "same" in normalized,
        session.get("order_attempts", 0) >= 2,
    ])


def extract_delay_minutes(user_text):
    match = re.search(r"\b(\d{1,3})\s*(min|mins|minutes)\b", normalize_text(user_text))
    return int(match.group(1)) if match else None


def extract_new_address(user_text):
    if any(token in normalize_text(user_text) for token in ["street", "road", "lane", "avenue", "building", "flat", "sector"]):
        return user_text.strip()
    return ""


def get_tracking_response():
    order_id = session.get("order_id")
    if order_id:
        return f"Order {order_id} is in transit. It is currently being prepared for delivery and should reach you soon."
    return "I can help track it. Please share your Order ID and I will check the latest delivery status."


def get_refund_response(user_text):
    normalized = normalize_text(user_text)

    if "status" in normalized or "how long" in normalized or "when" in normalized:
        return "Refunds usually reflect in 5-7 business days depending on your bank or payment method."

    if session.get("order_verified"):
        return "I have noted the refund issue. Refunds are typically processed within 5-7 business days after confirmation."

    return "I can help with the refund. Please share your Order ID so I can guide you on the refund status."


def get_address_response(user_text):
    updated_address = extract_new_address(user_text)

    if updated_address:
        session['details']['updated_address'] = updated_address
        session['conversation_stage'] = "chatting"
        return f"Thanks, I have noted the new address details: {updated_address}. If the order has not been dispatched yet, the update can still be applied."

    if session.get("order_verified"):
        return "Yes, you can request an address or phone update before dispatch. Please send the new address or phone details."

    return "I can help with an address update. Please share your Order ID first, then send the new address or phone number."


def get_cancel_response():
    if session.get("order_verified"):
        return "Cancellation is only possible before the order is fully processed. If preparation has already started, the order usually cannot be canceled."
    return "I can explain the cancellation policy. Orders can be canceled only before they move into processing or dispatch."


def get_missing_item_response(user_text):
    normalized = normalize_text(user_text)

    if "replace" in normalized or "replacement" in normalized:
        return "I can help with that. A replacement request can be raised for missing or damaged items once the order is verified."

    if session.get("order_verified"):
        return "I can help resolve the missing item issue. I can arrange a replacement or refund request. Please tell me which item is affected."

    return "I can help with a missing item replacement. Please share your Order ID so I can verify the order first."


def get_delay_response(user_text):
    minutes = extract_delay_minutes(user_text)

    if minutes is not None and minutes <= 20:
        return f"A {minutes}-minute delay is usually temporary. Your order should arrive soon, and no escalation is needed right now."

    if minutes is not None:
        return f"I see the order is delayed by about {minutes} minutes. I have flagged it as a delivery delay and it should be prioritized."

    if session.get("order_verified"):
        return "Minor delivery delays can happen during preparation or rider assignment. Your order should still arrive soon."

    return "I can help with the delivery delay. Please share your Order ID so I can guide you on the next step."


def get_knowledge_response(intent, user_text):
    knowledge_responses = {
        "track": get_tracking_response,
        "refund": lambda: get_refund_response(user_text),
        "address": lambda: get_address_response(user_text),
        "cancel": get_cancel_response,
        "missing": lambda: get_missing_item_response(user_text),
        "delay": lambda: get_delay_response(user_text),
    }

    response_builder = knowledge_responses.get(intent)
    return response_builder() if response_builder else ""


def handle_contextual_follow_up(user_text):
    current_issue = session.get("issue_type")


    if current_issue == "address" and session.get("order_verified"):
        updated_address = extract_new_address(user_text)
        if updated_address:
            session['details']['updated_address'] = updated_address
            return f"Thanks, I have noted the new address details: {updated_address}. If the order has not been dispatched yet, the update can still be applied."

    if current_issue == "missing" and session.get("order_verified"):
        items = re.findall(r"(pizza|burger|fries|drink|pasta|sandwich|shake|combo)", normalize_text(user_text))
        if items:
            session['details']['items'] = items
            return f"I have noted the affected item: {', '.join(items)}. I can help arrange a replacement or refund for it."
        if any(word in normalize_text(user_text) for word in ["refund", "replace", "replacement"]):
            return "I have noted your preference. A replacement or refund request can now be processed for the missing item."

    if current_issue == "delay" and session.get("order_verified"):
        minutes = extract_delay_minutes(user_text)
        if minutes is not None:
            return get_delay_response(user_text)

    if current_issue == "refund" and session.get("order_verified"):
        if any(word in normalize_text(user_text) for word in ["upi", "card", "cash", "wallet", "payment"]):
            return "Thanks, I have noted the payment method. Refunds are typically reflected within 5-7 business days after processing."

    return ""


def maybe_set_order_context(user_text):
    order_match = re.search(r"\b\d{8,12}\b", normalize_text(user_text))
    if order_match:
        session['order_verified'] = True
        session['order_id'] = order_match.group()
        session['order_attempts'] = 0
        return order_match.group()
    return None


def update_memory_after_response(intent=None, understood=False):
    session['last_user_message'] = normalize_text(get_last_user_message())
    if intent:
        session['last_detected_intent'] = intent
    if understood:
        session['clarification_attempts'] = 0


def escalate_with_reason(reason, confidence=None):
    record_escalation(reason=reason, confidence=confidence)
    return bot_reply(ESCALATION_MESSAGE)


def count_interchanges():
    history = session.get("conversation_history", [])
    user_count = sum(1 for entry in history if entry.startswith("User: "))
    bot_count = sum(1 for entry in history if entry.startswith("Bot: "))
    return min(user_count, bot_count)


def should_consult_ml_model():
    # The model should only be used after the bot has already had several chances
    # to solve the issue. This prevents "escalate everything after 5 texts" behavior.
    interchanges = count_interchanges()
    clarification_attempts = session.get("clarification_attempts", 0)
    issue_type = session.get("issue_type")

    unresolved_signals = [
        clarification_attempts >= 2,
        should_escalate_for_repetition(get_last_user_message()),
        issue_type is None and interchanges >= 2,
    ]

    # Require at least 3 full user-bot interchanges before consulting the model.
    # That means the bot must try guiding the user first instead of escalating early.
    return interchanges >= 3 and any(unresolved_signals)


def maybe_escalate_with_ml(reason):
    try:
        api_response = requests.post(
            MODEL_API_URL,
            json={"conversation": " || ".join(session.get("conversation_history", []))},
            timeout=2,
        )

        api_response.raise_for_status()
        result = api_response.json()

        if result.get("escalate") == 1:
            print("⚠️ Escalation triggered by ML model")
            return escalate_with_reason(reason=reason, confidence=result.get("probability"))

    except Exception as e:
        print("❌ Model API connection error:", e)

    return None


# ==========================================
# HOME ROUTE
# ==========================================

@app.route("/")
def home():
    session.clear()
    initialize_session()
    app.logger.info("Home route loaded and session reset.")
    return render_template("index.html")


@app.route("/dashboard")
def dashboard_home():
    app.logger.info("Dashboard home requested.")
    return redirect(url_for("dashboard_active"))


@app.route("/dashboard/active")
def dashboard_active():
    app.logger.info("Active complaints dashboard requested.")
    return send_from_directory(DASHBOARD_DIR, "active.html")


@app.route("/dashboard/resolved")
def dashboard_resolved():
    app.logger.info("Resolved complaints dashboard requested.")
    return send_from_directory(DASHBOARD_DIR, "resolved.html")


@app.route("/dashboard/insights")
def dashboard_insights():
    app.logger.info("Insights dashboard requested.")
    return send_from_directory(DASHBOARD_DIR, "insights.html")


@app.route("/dashboard/<path:asset_path>")
def dashboard_assets(asset_path):
    app.logger.info("Dashboard asset requested: %s", asset_path)
    return send_from_directory(DASHBOARD_DIR, asset_path)


@app.route("/api/complaints/active")
def get_active_complaints():
    store = load_complaints_store()
    active_complaints = store.get("active", [])
    app.logger.info("Loaded %d active complaints.", len(active_complaints))
    return jsonify({"complaints": active_complaints})


@app.route("/api/complaints/resolved")
def get_resolved_complaints():
    store = load_complaints_store()
    resolved_complaints = store.get("resolved", [])
    app.logger.info("Loaded %d resolved complaints.", len(resolved_complaints))
    return jsonify({"complaints": resolved_complaints})


@app.route("/api/complaints/resolve", methods=["POST"])
def resolve_complaint():
    payload = request.get_json(silent=True) or {}
    complaint_id = payload.get("id")

    if not complaint_id:
        app.logger.warning("Resolve complaint called without an id.")
        return jsonify({"error": "Complaint id is required."}), 400

    resolved_complaint = resolve_complaint_by_id(complaint_id)

    if not resolved_complaint:
        app.logger.warning("Complaint %s was not found in active complaints.", complaint_id)
        return jsonify({"error": "Complaint not found."}), 404

    return jsonify({"status": "ok", "complaint": resolved_complaint})


# ==========================================
# CHAT ROUTE
# ==========================================

@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    user_input = payload.get("message", "")

    if not isinstance(user_input, str) or not user_input.strip():
        return jsonify({"response": "Please type a message."})

    user_text = user_input.strip().lower()
    append_conversation("User", user_input)
    maybe_set_order_context(user_input)

    # ==========================================
    # RESET
    # ==========================================

    if user_text in ["reset", "restart", "start over"]:
        session.clear()
        initialize_session()
        return bot_reply("Conversation reset. How can I help you today?")


    # ==========================================
    # GREETING
    # ==========================================

    if user_text in ["hi", "hello", "hey", "help"]:
        update_memory_after_response(understood=True)
        return bot_reply("Hello! 👋 How can I help you today?")


    # ==========================================
    # GRATITUDE
    # ==========================================

    gratitude_patterns = r"\b(ok|okay|thanks|thank ?you|ty|awesome|great)\b"

    if re.search(gratitude_patterns, user_text):
        update_memory_after_response(understood=True)
        return bot_reply("You're welcome! Let me know if you need anything else.")

    # ==========================================
    # DYNAMIC ESCALATION SIGNALS
    # ==========================================

    frustration_score = calculate_frustration_score(user_input)

    if user_requested_human(user_text):
        return escalate_with_reason(reason="Customer explicitly requested a human agent.")

    if has_severe_escalation_signal(user_input):
        return escalate_with_reason(reason="Customer message contains a clear escalation signal.")

    if frustration_score >= 6:
        return escalate_with_reason(reason=f"Frustration score reached {frustration_score}.")

    stage = session.get('conversation_stage', 'chatting')

    # ==========================================
    # CONTEXT EXTRACTION
    # ==========================================

    items = re.findall(r"(pizza|burger|fries|drink|pasta|sandwich|shake|combo)", user_text)

    if items:
        session['details']['items'] = items

    # ==========================================
    # ORDER ID STAGE
    # ==========================================

    if stage == "waiting_for_order_id":
        if session.get('order_verified'):
            issue = session.get('issue_type')

            if issue == "missing":
                session['conversation_stage'] = "chatting"
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply("Thanks, your order is verified. Please tell me which item is missing or damaged so I can arrange a replacement or refund.")

            elif issue == "delay":
                session['conversation_stage'] = "chatting"
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply("Thanks, your order is verified. Please tell me roughly how late the delivery is.")

            elif issue == "refund":
                session['conversation_stage'] = "chatting"
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply("Thanks, your order is verified. Please explain the refund or payment issue.")

            elif issue == "address":
                session['conversation_stage'] = "chatting"
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply("Thanks, your order is verified. Please send the new address or phone number.")

            elif issue == "cancel":
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply("This order is already processed and cannot be canceled.")

            elif issue == "track":
                update_memory_after_response(intent=issue, understood=True)
                return bot_reply(get_tracking_response())

            update_memory_after_response(understood=True)
            return bot_reply("Order verified. Please explain your issue.")

        session['order_attempts'] += 1

        if session['order_attempts'] >= 3:
            return escalate_with_reason(reason="User could not provide an order ID after multiple attempts.")

        update_memory_after_response(intent=session.get('issue_type'), understood=False)
        return bot_reply("I still need your Order ID before I can make that update safely. Please share the Order ID.")

    contextual_response = handle_contextual_follow_up(user_input)
    if contextual_response:
        update_memory_after_response(intent=session.get('issue_type'), understood=True)
        return bot_reply(contextual_response)

    intent, confidence = get_intent_from_text(user_input)

    if intent and confidence >= 0.8:
        session['issue_type'] = intent
        response = get_knowledge_response(intent, user_input)

        if not session.get('order_verified') and intent in {"track", "refund", "address", "missing", "delay"}:
            if "Please share your Order ID" in response or "Please share your Order ID so I can" in response:
                session['conversation_stage'] = "waiting_for_order_id"
        else:
            session['conversation_stage'] = "chatting"

        update_memory_after_response(intent=intent, understood=True)
        return bot_reply(response)

    if intent and 0.55 <= confidence < 0.8:
        session['issue_type'] = intent
        session['clarification_attempts'] += 1

        update_memory_after_response(intent=intent, understood=False)
        tentative_reply = f"I think this may be about {intent}. {CLARIFYING_QUESTION}"

        if session['clarification_attempts'] >= 3 and has_clear_escalation_reason(user_input, frustration_score):
            ml_escalation = maybe_escalate_with_ml(
                reason="ML model predicted escalation from unresolved low-confidence conversation."
            )
            if ml_escalation:
                return ml_escalation
            return escalate_with_reason(reason="Low-confidence intent remained unresolved after 3 attempts.")

        if should_consult_ml_model():
            ml_escalation = maybe_escalate_with_ml(
                reason="ML model predicted escalation from unresolved low-confidence conversation."
            )
            if ml_escalation:
                return ml_escalation

        return bot_reply(tentative_reply)

    session['clarification_attempts'] += 1

    # After 3 unclear tries, escalate when there is a clear reason to hand off.
    if session['clarification_attempts'] >= 3 and has_clear_escalation_reason(user_input, frustration_score):
        ml_escalation = maybe_escalate_with_ml(
            reason="ML model predicted escalation after repeated unresolved bot guidance."
        )
        if ml_escalation:
            return ml_escalation
        return escalate_with_reason(reason="Bot could not resolve the issue after 3 unclear attempts.")

    if should_consult_ml_model():
        ml_escalation = maybe_escalate_with_ml(
            reason="ML model predicted escalation after repeated unresolved bot guidance."
        )
        if ml_escalation:
            return ml_escalation

    confusing_responses = [
        "I want to help, but I need a little more detail.",
        "I’m not fully sure what happened yet.",
        "I need a bit more context before I suggest the next step."
    ]

    update_memory_after_response(understood=False)
    return bot_reply(f"{random.choice(confusing_responses)} {CLARIFYING_QUESTION}")

if __name__ == "__main__":
    print("Chatbot UI running on http://127.0.0.1:5001")
    app.run(host="0.0.0.0", port=5001, debug=True)
