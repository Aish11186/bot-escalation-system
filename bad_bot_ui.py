from flask import Flask, render_template, request, jsonify, session
import re

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

@app.route("/")
def home():
    session.clear()
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
    session['issue_type'] = None
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    user_text = user_input.strip().lower()
    bot_response = ""

    if 'conversation_stage' not in session:
        session['conversation_stage'] = "chatting"
        session['order_verified'] = False

    stage = session.get('conversation_stage')

    if any(word in user_text for word in ["human", "agent", "representative", "real person", "customer care"]):
        return jsonify({"response": "I understand you'd like to connect with a human agent. Due to high demand, wait times are longer than usual. Meanwhile, I’ll continue assisting you here to resolve this as quickly as possible."})

    if stage == "chatting" and user_text in ["hi", "hello", "hey", "help"]:
        return jsonify({"response": "Hello! 👋 I'm your automated support assistant. How can I help you with your order today?"})

    if stage == "waiting_for_order_id":
        if re.match(r'.*\b\d{10}\b.*', user_text):
            session['order_verified'] = True

            issue = session.get('issue_type')

            if issue == "missing":
                bot_response = "Thanks, I’ve found your order. Can you tell me which items were missing or incorrect?"
                session['conversation_stage'] = "missing_step_1"

            elif issue == "delay":
                bot_response = "Order located. How long has it been delayed beyond the expected delivery time?"
                session['conversation_stage'] = "delay_step_1"

            elif issue == "payment":
                bot_response = "I see your order. Could you describe the payment issue you're facing?"
                session['conversation_stage'] = "payment_step_1"

            elif issue == "address":
                bot_response = "Got it. What would you like to change in the delivery details?"
                session['conversation_stage'] = "address_step_1"

            else:
                bot_response = "Order verified. Please explain your issue in a bit more detail so I can assist you better."
                session['conversation_stage'] = "general_step_1"
        else:
            bot_response = "That doesn't seem like a valid 10-digit Order ID. Please try again."

        return jsonify({"response": bot_response})

    if stage == "missing_step_1":
        session['conversation_stage'] = "missing_step_2"
        return jsonify({"response": "Thanks for the details. I’m checking with the system to verify the issue."})

    elif stage == "missing_step_2":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "I’ve reviewed your case. A replacement or refund has been initiated if applicable. You’ll be notified shortly."})

    elif stage == "delay_step_1":
        session['conversation_stage'] = "delay_step_2"
        return jsonify({"response": "Thanks. I’m checking the live status of your order."})

    elif stage == "delay_step_2":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Your order is currently in transit and should reach you soon. I appreciate your patience."})

    elif stage == "payment_step_1":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "I’ve checked the transaction. If any amount was incorrectly charged, it will be automatically refunded within 5-7 business days."})

    elif stage == "address_step_1":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Your request has been noted. If the order is still in progress, the updated details will be shared with the delivery partner."})

    elif stage == "general_step_1":
        session['conversation_stage'] = "chatting"
        return jsonify({"response": "Thanks for sharing that. I’ve processed your request and appropriate action has been taken."})

    if stage == "chatting":

        if any(word in user_text for word in ["missing", "wrong", "broken", "damaged", "defective"]):
            session['issue_type'] = "missing"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "I’m sorry to hear that. Please share your 10-digit Order ID so I can help you."
            else:
                session['conversation_stage'] = "missing_step_1"
                bot_response = "Could you specify what exactly was missing or incorrect?"

        elif any(word in user_text for word in ["late", "delay", "not arrived", "where is my order", "taking long"]):
            session['issue_type'] = "delay"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "I understand the delay can be frustrating. Please provide your 10-digit Order ID."
            else:
                session['conversation_stage'] = "delay_step_1"
                bot_response = "How long has the order been delayed?"

        elif any(word in user_text for word in ["refund", "money", "charged", "payment", "double payment"]):
            session['issue_type'] = "payment"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "I’ll help you with the payment issue. Please share your 10-digit Order ID."
            else:
                session['conversation_stage'] = "payment_step_1"
                bot_response = "Please describe the payment issue."

        elif any(word in user_text for word in ["address", "location", "change address", "wrong address"]):
            session['issue_type'] = "address"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "Sure, I can help update details. Please provide your 10-digit Order ID."
            else:
                session['conversation_stage'] = "address_step_1"
                bot_response = "What changes would you like to make?"

        elif any(word in user_text for word in ["status", "track", "update"]):
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "Please provide your 10-digit Order ID to check the status."
            else:
                bot_response = "Your order is currently being processed and is on track."

        elif any(word in user_text for word in ["cancel"]):
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "Please share your 10-digit Order ID to proceed with cancellation."
            else:
                bot_response = "If the order has not been processed yet, cancellation will be completed. Otherwise, it may not be possible."

        else:
            bot_response = "I’m here to help. Could you tell me more about the issue you're facing with your order?"

        return jsonify({"response": bot_response})

if __name__ == "__main__":
    app.run(debug=True)