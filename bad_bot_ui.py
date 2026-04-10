from flask import Flask, render_template, request, jsonify, session
import re
import random
from difflib import get_close_matches

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

# Patterns
missing_patterns = r"(missing|not received|didn't get|broken|damaged|wrong item|incorrect|defective)"
delay_patterns = r"(late|delay|not arrived|taking too long)"
track_patterns = r"(track|status|where is my order)"
refund_patterns = r"(refund|money back|charged|double payment|payment issue)"
cancel_patterns = r"(cancel|stop order|don't want it)"
address_patterns = r"(change address|wrong address|update address|phone number)"

@app.route("/")
def home():
    session.clear()
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
    session['issue_type'] = None
    session['escalation_count'] = 0
    session['details'] = {}
    session['order_attempts'] = 0
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    user_text = user_input.strip().lower() if user_input else ""

    # Ensure session keys exist
    if 'details' not in session:
        session['details'] = {}
    if 'order_attempts' not in session:
        session['order_attempts'] = 0

    # Reset
    if user_text in ["reset", "start over", "restart"]:
        session.clear()
        session['conversation_stage'] = "chatting"
        session['order_verified'] = False
        return jsonify({"response": "Conversation reset. How can I help you today?"})

    # Greeting
    if user_text in ["hi", "hello", "hey"]:
        return jsonify({"response": "Hello! 👋 How can I help you today?"})

    # Escalation
    escalation_keywords = ["human", "agent", "person", "representative", "real", "customer service", "escalate", "manager"]
    if any(word in user_text for word in escalation_keywords):
        session['escalation_count'] = session.get('escalation_count', 0) + 1
        count = session['escalation_count']

        if count == 1:
            return jsonify({"response": "I understand you'd prefer a human. Let me try to resolve this quickly first. What's the issue?"})
        elif count == 2:
            return jsonify({"response": "Connecting to a human may take time. I can resolve most issues instantly. Tell me what happened."})
        else:
            return jsonify({"response": "I've logged your request for a human agent. You’ll be contacted shortly."})

    stage = session.get('conversation_stage', 'chatting')

    # Quick replies
    if user_text in ["1", "2", "3", "4"]:
        mapping = {"1": "delay", "2": "missing", "3": "refund", "4": "address"}
        session['issue_type'] = mapping[user_text]
        session['conversation_stage'] = "waiting_for_order_id"
        return jsonify({"response": "Got it! Please provide your 10-digit Order ID."})

    # Extract items
    items = re.findall(r"(pizza|burger|fries|drink|pasta|sandwich|shake|combo)", user_text)
    if items:
        session['details']['items'] = items

    # Order ID detection
    order_match = re.search(r"\b\d{10}\b", user_text)

    if stage == "waiting_for_order_id":
        if order_match:
            session['order_verified'] = True
            session['order_id'] = order_match.group()
            session['order_attempts'] = 0
            issue = session.get('issue_type')

            if issue == "missing":
                session['conversation_stage'] = "missing_step_1"
                return jsonify({"response": "Thanks! What item is missing or damaged?"})

            elif issue == "delay":
                session['conversation_stage'] = "delay_step_1"
                return jsonify({"response": "How many minutes late is your order?"})

            elif issue == "refund":
                session['conversation_stage'] = "refund_step_1"
                return jsonify({"response": "Please explain the payment issue."})

            elif issue == "address":
                session['conversation_stage'] = "address_step_1"
                return jsonify({"response": "What is the new address or phone number?"})

            elif issue == "cancel":
                return jsonify({"response": "This order is already processed and cannot be canceled. You may refuse delivery."})

            elif issue == "track":
                return jsonify({"response": "Your order is currently in transit and will arrive soon."})

            return jsonify({"response": "Order verified. Please explain your issue."})

        else:
            session['order_attempts'] += 1
            if session['order_attempts'] > 2:
                return jsonify({"response": "If you don’t have the Order ID, please describe your issue and I’ll try to help."})
            return jsonify({"response": "Please provide a valid 10-digit Order ID."})

    # Conversation stages
    if stage == "missing_step_1":
        session['conversation_stage'] = "missing_step_2"
        items = session.get('details', {}).get('items', [])
        if items:
            return jsonify({"response": f"I see your {', '.join(items)} is affected. Would you like a refund or replacement?"})
        return jsonify({"response": "Would you like a refund or replacement?"})

    elif stage == "missing_step_2":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Request processed. You'll receive confirmation shortly."})

    elif stage == "delay_step_1":
        session['conversation_stage'] = "delay_step_2"
        responses = [
            "I understand the wait is frustrating.",
            "Sorry about the delay, that shouldn't happen.",
            "I can imagine that's annoying — let me help."
        ]
        return jsonify({"response": random.choice(responses) + " Have you contacted the delivery partner?"})

    elif stage == "delay_step_2":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Your order has been prioritized and should arrive soon."})

    elif stage == "refund_step_1":
        session['conversation_stage'] = "refund_step_2"
        return jsonify({"response": "What was the payment method?"})

    elif stage == "refund_step_2":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Refund processed. It will reflect in 5-7 business days."})

    elif stage == "address_step_1":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Address updated successfully."})

    # Intent detection
    if re.search(missing_patterns, user_text):
        session['issue_type'] = "missing"
    elif re.search(track_patterns, user_text):
        session['issue_type'] = "track"
    elif re.search(delay_patterns, user_text):
        session['issue_type'] = "delay"
    elif re.search(refund_patterns, user_text):
        session['issue_type'] = "refund"
    elif re.search(cancel_patterns, user_text):
        session['issue_type'] = "cancel"
    elif re.search(address_patterns, user_text):
        session['issue_type'] = "address"
    else:
        # Improved fuzzy matching
        keywords = ["refund", "delay", "missing", "cancel"]
        for word in user_text.split():
            match = get_close_matches(word, keywords, n=1, cutoff=0.8)
            if match:
                session['issue_type'] = match[0]
                break
        else:
            return jsonify({
                "response": "Are you facing:\n1. Delivery delay\n2. Missing/damaged item\n3. Payment/refund\n4. Address change\nReply with a number."
            })

    # Move to order ID step
    if not session.get('order_verified'):
        session['conversation_stage'] = "waiting_for_order_id"
        return jsonify({"response": "Please provide your 10-digit Order ID."})

    return jsonify({"response": "How can I assist further?"})


if __name__ == "__main__":
    app.run(debug=True)