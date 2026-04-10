from flask import Flask, render_template, request, jsonify, session
<<<<<<< HEAD
import requests
=======
>>>>>>> e82852e857b9458771e9b93401ca19026c957066
import re

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

<<<<<<< HEAD
MODEL_API_URL = "http://127.0.0.1:8000/predict"


def append_conversation_turn(role, message):
    history = session.get("conversation_history", [])
    history.append(f"{role}: {message}")
    session["conversation_history"] = history[-20:]


def reply(message):
    append_conversation_turn("Bot", message)
    return jsonify({"response": message})


=======
>>>>>>> e82852e857b9458771e9b93401ca19026c957066
@app.route("/")
def home():
    session.clear()
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
<<<<<<< HEAD
    session['issue_type'] = None 
    session['conversation_history'] = []
=======
    session['issue_type'] = None
>>>>>>> e82852e857b9458771e9b93401ca19026c957066
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
<<<<<<< HEAD
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
=======
    user_input = request.json.get("message")
    user_text = user_input.strip().lower()
    bot_response = ""
>>>>>>> e82852e857b9458771e9b93401ca19026c957066

    if 'conversation_stage' not in session:
        session['conversation_stage'] = "chatting"
        session['order_verified'] = False

    stage = session.get('conversation_stage')

<<<<<<< HEAD
    if any(word in user_text for word in ["human", "agent", "person", "representative", "real", "customer service"]):
        return reply("I understand you'd like to speak with a human. However, our support team is currently experiencing high volumes. I am fully capable of handling your request. Let's continue.")

    if stage == "chatting" and user_text in ["hi", "hello", "hey", "help"]:
        return reply("Hello there! 👋 I am your automated support assistant. How can I help you with your order today?")
=======
    if any(word in user_text for word in ["human", "agent", "representative", "real person", "customer care"]):
        return jsonify({"response": "I understand you'd like to connect with a human agent. Due to high demand, wait times are longer than usual. Meanwhile, I’ll continue assisting you here to resolve this as quickly as possible."})

    if stage == "chatting" and user_text in ["hi", "hello", "hey", "help"]:
        return jsonify({"response": "Hello! 👋 I'm your automated support assistant. How can I help you with your order today?"})
>>>>>>> e82852e857b9458771e9b93401ca19026c957066

    if stage == "waiting_for_order_id":
        if re.match(r'.*\b\d{10}\b.*', user_text):
            session['order_verified'] = True
<<<<<<< HEAD
            
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
=======

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
>>>>>>> e82852e857b9458771e9b93401ca19026c957066
