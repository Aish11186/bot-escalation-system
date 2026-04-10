from flask import Flask, render_template, request, jsonify, session
import requests
import re

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

MODEL_API_URL = "http://127.0.0.1:8000/predict"


def append_conversation_turn(role, message):
    history = session.get("conversation_history", [])
    history.append(f"{role}: {message}")
    session["conversation_history"] = history[-20:]


def reply(message):
    append_conversation_turn("Bot", message)
    return jsonify({"response": message})


@app.route("/")
def home():
    session.clear()
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
    session['issue_type'] = None 
    session['conversation_history'] = []
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    payload = request.get_json(silent=True) or {}
    user_input = payload.get("message", "")
    if not isinstance(user_input, str) or not user_input.strip():
        return jsonify({"response": "Please type a message so I can help."}), 400

    user_text = user_input.strip().lower()
    bot_response = ""
    append_conversation_turn("User", user_input)

    # Call the ML escalation API
    try:
        api_response = requests.post(
            MODEL_API_URL,
            json={"conversation": " || ".join(session["conversation_history"])},
            timeout=2,
        )
        api_response.raise_for_status()
        api_result = api_response.json()

        # If the model predicts escalation, respond immediately
        if api_result.get("escalate") == 1:
            return reply("I sense that this issue may require human assistance. Let me escalate this conversation to a support specialist.")
    except Exception as e:
        # If API is not running, continue normal chatbot flow
        print("Model API error:", e)

    if 'conversation_stage' not in session:
        session['conversation_stage'] = "chatting"
        session['order_verified'] = False

    stage = session.get('conversation_stage')

    if any(word in user_text for word in ["human", "agent", "person", "representative", "real", "customer service"]):
        return reply("I understand you'd like to speak with a human. However, our support team is currently experiencing high volumes. I am fully capable of handling your request. Let's continue.")

    if stage == "chatting" and user_text in ["hi", "hello", "hey", "help"]:
        return reply("Hello there! 👋 I am your automated support assistant. How can I help you with your order today?")

    if stage == "waiting_for_order_id":
        if re.match(r'.*\b\d{10}\b.*', user_text):
            session['order_verified'] = True
            
            if session.get('issue_type') == "missing":
                bot_response = "Thank you. I see your order. To start, could you tell me exactly which items were missing or damaged?"
                session['conversation_stage'] = "missing_step_1"
            elif session.get('issue_type') == "delay":
                bot_response = "Thanks for the Order ID! I can see the order in my system. Roughly how many minutes past the delivery time is it?"
                session['conversation_stage'] = "delay_step_1"
            else:
                bot_response = "Thank you, I have verified your Order ID. Could you please explain the main reason for your refund request?"
                session['conversation_stage'] = "refund_step_1"
        else:
            bot_response = "I couldn't find a 10-digit number. Please double-check your Order ID and type it again."
        
        return reply(bot_response)

    if stage == "missing_step_1":
        session['conversation_stage'] = "missing_step_2"
        return reply(f"Got it. I have noted that '{user_input}' had an issue. Was the outer packaging tampered with or open when you received it?")
    
    elif stage == "missing_step_2":
        session['conversation_stage'] = "missing_step_3"
        return reply("Thank you for confirming that. Could you please take a clear photo of the items you *did* receive and the receipt, and upload it using the '+' button in the app?")
    
    elif stage == "missing_step_3":
        session['conversation_stage'] = "chatting"
        return reply("Thank you for the information. I have analyzed your request and checked with the restaurant's dispatch system. Unfortunately, the restaurant has marked all items as verified and packed. Because of this, I cannot process a refund or replacement for this order. Is there anything else I can assist with?")

    elif stage == "delay_step_1":
        session['conversation_stage'] = "delay_step_2"
        return reply("I see. Have you tried calling the delivery partner through the app to check their location?")
    
    elif stage == "delay_step_2":
        session['conversation_stage'] = "delay_step_3"
        return reply("I understand. Sometimes partners lose GPS signal. Could you please confirm your delivery pin code or landmark just so I can verify the route?")
    
    elif stage == "delay_step_3":
        session['conversation_stage'] = "chatting"
        return reply("Thank you. Let me check the live tracking system... \n\nMy system shows the partner is on the way but stuck in traffic. Since the delay has not exceeded our maximum 60-minute policy threshold, I cannot cancel the order or offer compensation at this time. Please wait a little longer!")

    elif stage == "refund_step_1":
        session['conversation_stage'] = "refund_step_2"
        return reply("I have noted your reason. Did you pay for this order using a Credit Card, UPI, or Wallet?")
    
    elif stage == "refund_step_2":
        session['conversation_stage'] = "refund_step_3"
        return reply("Thanks. Refunds to that payment method usually take 5-7 business days. Do you want me to proceed with submitting the cancellation request to the restaurant?")
    
    elif stage == "refund_step_3":
        session['conversation_stage'] = "chatting"
        return reply("Processing your request... \n\nI apologize, but the restaurant has already started preparing your food. According to our strict cancellation policy, we cannot issue a refund once food preparation has begun. You will still receive your order. Is there anything else?")

    if stage == "chatting":
        if any(word in user_text for word in ["missing", "broken", "wrong", "spilled", "ruined", "cold"]):
            session['issue_type'] = "missing"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "Oh no, I am so sorry to hear about your food! I definitely want to help fix this. To get started, could you please share your 10-digit Order ID?"
            else:
                session['conversation_stage'] = "missing_step_1"
                bot_response = "I am really sorry about that. Could you tell me exactly which items were missing or damaged?"
                
        elif any(word in user_text for word in ["late", "where", "track", "delay", "not here", "taking so long"]):
            session['issue_type'] = "delay"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "I know waiting for food can be frustrating. Let me help you with that! Could you please provide your 10-digit Order ID?"
            else:
                session['conversation_stage'] = "delay_step_1"
                bot_response = "I understand the wait is frustrating. How many minutes past the estimated delivery time is it?"

        elif any(word in user_text for word in ["refund", "money", "cancel", "return", "charge"]):
            session['issue_type'] = "refund"
            if not session.get('order_verified'):
                session['conversation_stage'] = "waiting_for_order_id"
                bot_response = "I can certainly look into a refund for you. First, I just need your 10-digit Order ID."
            else:
                session['conversation_stage'] = "refund_step_1"
                bot_response = "I see. To process a refund request, could you briefly explain the main reason you are asking for your money back?"

        else:
            bot_response = "I'm listening. Could you give me a little more context? Are you dealing with a delayed delivery, a missing item, or something else entirely?"

        return reply(bot_response)

if __name__ == "__main__":
    app.run(debug=True)
