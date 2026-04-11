from flask import Flask, jsonify, render_template, request, send_from_directory, session
import json
from pathlib import Path
import random
import re

import requests

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard-UI"
COMPLAINTS_STORE = Path(__file__).resolve().parent / "complaints_store.json"
MODEL_API_URL = "http://127.0.0.1:8000/predict"
MIN_MESSAGES_FOR_MODEL = 10
ESCALATION_MESSAGE = "I understand. I am connecting you to customer support."

# Intent patterns keep the chatbot deterministic and easy to debug.
INTENT_PATTERNS = {
    "missing": r"\b(missing|not received|didn't get|broken|damaged|wrong item|incorrect|defective)\b",
    "delay": r"\b(late|delay|not arrived|taking too long|where is my order|stuck)\b",
    "refund": r"\b(refund|money back|charged|double payment|payment issue|cancel order)\b",
    "address": r"\b(change address|wrong address|update address|phone number|contact number)\b",
    "human": r"\b(human|agent|person|representative|manager|support)\b",
}

INTENT_REPLIES = {
    "missing": "I can help with a missing or damaged item. Please share your 10-digit Order ID so I can check the order.",
    "delay": "I can look into the delivery delay. Please send your 10-digit Order ID.",
    "refund": "I can help with the refund or payment issue. Please share your 10-digit Order ID.",
    "address": "I can help update the delivery details. Please share your 10-digit Order ID.",
    "human": "I can still help with this, and if needed I will connect you to customer support shortly. Please tell me what went wrong.",
}

FOLLOW_UP_REPLIES = {
    "missing": "I have noted the missing or damaged item issue. Would you like a refund or a replacement?",
    "delay": "I have your order ID now. Let me check the delay and help you with the next steps.",
    "refund": "I have your order ID now. Please tell me the payment or refund issue in one sentence.",
    "address": "I have your order ID now. Please send the updated address or phone number.",
}

GENERIC_HELP_MESSAGE = (
    "I can help with order delays, missing items, refunds, address updates, or general support. "
    "Tell me what happened and I will guide you."
)


def reset_session_state():
    """Initialize every key used by the chatbot so requests stay predictable."""
    session.clear()
    session["conversation_history"] = []
    session["order_verified"] = False
    session["order_id"] = None
    session["current_intent"] = None
    session["active_complaint_id"] = None


def ensure_session_state():
    """Backfill missing session keys for older sessions and direct API calls."""
    session.setdefault("conversation_history", [])
    session.setdefault("order_verified", False)
    session.setdefault("order_id", None)
    session.setdefault("current_intent", None)
    session.setdefault("active_complaint_id", None)


def get_history():
    return list(session.get("conversation_history", []))


def save_history(history):
    # Keep the last 20 messages to prevent the cookie-backed session from growing indefinitely.
    session["conversation_history"] = history[-20:]
    session.modified = True


def append_message(role, message):
    history = get_history()
    history.append({"role": role, "message": message})
    save_history(history)


def conversation_to_model_input(history):
    return " || ".join(f"{entry['role']}: {entry['message']}" for entry in history)


def detect_intent(user_text):
    for intent, pattern in INTENT_PATTERNS.items():
        if re.search(pattern, user_text, flags=re.IGNORECASE):
            return intent
    return None


def extract_order_id(text):
    match = re.search(r"\b\d{10}\b", text)
    return match.group(0) if match else None


def load_complaints_store():
    if not COMPLAINTS_STORE.exists():
        return {"active": [], "resolved": []}

    try:
        with COMPLAINTS_STORE.open("r", encoding="utf-8") as store_file:
            data = json.load(store_file)
    except (json.JSONDecodeError, OSError):
        return {"active": [], "resolved": []}

    return {
        "active": data.get("active", []),
        "resolved": data.get("resolved", []),
    }


def save_complaints_store(store):
    with COMPLAINTS_STORE.open("w", encoding="utf-8") as store_file:
        json.dump(store, store_file, indent=2)


def create_active_complaint(probability, latest_user_message):
    """Persist one active complaint using the shared dashboard schema."""
    store = load_complaints_store()
    complaint = {
        "id": str(random.randint(10000, 99999)),
        "confidence": f"{float(probability):.2f}",
        "reason": latest_user_message.strip(),
        "status": "active",
    }
    store["active"].insert(0, complaint)
    save_complaints_store(store)
    return complaint


def resolve_active_complaint(complaint_id):
    store = load_complaints_store()

    for index, complaint in enumerate(store["active"]):
        if complaint.get("id") == complaint_id:
            resolved_complaint = store["active"].pop(index)
            resolved_complaint["status"] = "resolved"
            store["resolved"].insert(0, resolved_complaint)
            save_complaints_store(store)
            return resolved_complaint

    return None


def should_call_model(history):
    # The model is called only after 5 full exchanges: 10 messages total.
    return len(history) >= MIN_MESSAGES_FOR_MODEL


def call_model_api(history):
    """Send the serialized conversation to the model service and normalize the response."""
    try:
        response = requests.post(
            MODEL_API_URL,
            json={"conversation": conversation_to_model_input(history)},
            timeout=3,
        )
        response.raise_for_status()
        data = response.json()
        prediction = int(data.get("prediction", data.get("escalate", 0)))
        probability = float(data.get("probability", 0.0))
        return {"prediction": prediction, "probability": probability, "error": None}
    except Exception as exc:
        return {"prediction": 0, "probability": 0.0, "error": str(exc)}


def build_bot_reply(user_message):
    """Return a deterministic response based on intent and current session state."""
    user_text = user_message.strip()
    user_text_lower = user_text.lower()

    if user_text_lower in {"reset", "restart", "start over"}:
        reset_session_state()
        return "Conversation reset. How can I help you today?"

    if user_text_lower in {"hi", "hello", "hey"}:
        return "Hello! How can I help you with your order today?"

    order_id = extract_order_id(user_text)
    current_intent = session.get("current_intent")

    if order_id:
        session["order_verified"] = True
        session["order_id"] = order_id
        session.modified = True

        if current_intent in FOLLOW_UP_REPLIES:
            return FOLLOW_UP_REPLIES[current_intent]

        return f"Thanks. I have verified order {order_id}. Please tell me the issue you want help with."

    intent = detect_intent(user_text)
    if intent:
        session["current_intent"] = intent
        session.modified = True

        if session.get("order_verified") and intent in FOLLOW_UP_REPLIES:
            return FOLLOW_UP_REPLIES[intent]

        return INTENT_REPLIES[intent]

    if session.get("order_verified"):
        return "I have your order details. Please describe the problem and I will help you with the next step."

    return GENERIC_HELP_MESSAGE


def build_response_for_turn(user_message):
    """Generate the normal bot reply, then optionally replace it with an escalation."""
    append_message("User", user_message)

    if session.get("active_complaint_id"):
        append_message("Bot", ESCALATION_MESSAGE)
        return {"response": ESCALATION_MESSAGE, "escalated": True}

    candidate_reply = build_bot_reply(user_message)
    candidate_history = get_history() + [{"role": "Bot", "message": candidate_reply}]

    if should_call_model(candidate_history):
        model_result = call_model_api(candidate_history)

        if model_result["prediction"] == 1:
            complaint = create_active_complaint(model_result["probability"], user_message)
            session["active_complaint_id"] = complaint["id"]
            session.modified = True
            append_message("Bot", ESCALATION_MESSAGE)
            return {
                "response": ESCALATION_MESSAGE,
                "escalated": True,
                "prediction": 1,
                "probability": model_result["probability"],
            }

    append_message("Bot", candidate_reply)
    return {"response": candidate_reply, "escalated": False}


@app.route("/")
def home():
    reset_session_state()
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    ensure_session_state()

    payload = request.get_json(silent=True) or {}
    user_message = payload.get("message", "")

    if not isinstance(user_message, str) or not user_message.strip():
        return jsonify({"response": "Please type a message."}), 400

    result = build_response_for_turn(user_message)
    return jsonify(result)


@app.route("/dashboard/<path:filename>")
def dashboard_assets(filename):
    return send_from_directory(DASHBOARD_DIR, filename)


@app.route("/dashboard")
@app.route("/dashboard/active")
def dashboard_active():
    return send_from_directory(DASHBOARD_DIR, "active.html")


@app.route("/dashboard/resolved")
def dashboard_resolved():
    return send_from_directory(DASHBOARD_DIR, "resolved.html")


@app.route("/dashboard/insights")
def dashboard_insights():
    return send_from_directory(DASHBOARD_DIR, "insights.html")


@app.route("/api/complaints/active", methods=["GET"])
def get_active_complaints():
    store = load_complaints_store()
    return jsonify({"complaints": store["active"]})


@app.route("/api/complaints/resolved", methods=["GET"])
def get_resolved_complaints():
    store = load_complaints_store()
    return jsonify({"complaints": store["resolved"]})


@app.route("/api/complaints/resolve", methods=["POST"])
def resolve_complaint():
    payload = request.get_json(silent=True) or {}
    complaint_id = str(payload.get("id", "")).strip()

    if not complaint_id:
        return jsonify({"error": "Complaint id is required."}), 400

    resolved_complaint = resolve_active_complaint(complaint_id)
    if not resolved_complaint:
        return jsonify({"error": "Complaint not found."}), 404

    return jsonify({"success": True, "complaint": resolved_complaint})


if __name__ == "__main__":
    app.run(debug=True)
