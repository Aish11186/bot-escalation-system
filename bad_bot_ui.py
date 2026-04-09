from flask import Flask, render_template, request, jsonify, session
import re

app = Flask(__name__)
app.secret_key = "super_secret_key_for_testing"

@app.route("/")
def home():
    session.clear()
    session['order_verified'] = False
    session['conversation_stage'] = "chatting"
    # We will remember what their issue is (delay, missing, refund)
    session['issue_type'] = None 
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    user_text = user_input.strip().lower()
    bot_response = ""

    # Failsafe for memory
    if 'conversation_stage' not in session:
        session['conversation_stage'] = "chatting"
        session['order_verified'] = False

    stage = session.get('conversation_stage')

    # --- 1. HANDLE REQUESTS FOR A HUMAN ---
    if any(word in user_text for word in ["human", "agent", "person", "representative", "real", "customer service", "talk to someone"]):
        return jsonify({"response": "I completely understand you'd like to speak with a human agent. However, our support team is currently experiencing high volumes. I am an advanced AI, and I can resolve most issues right here! Let's keep trying—what exactly went wrong?"})

    # --- 2. SMALL TALK & GREETINGS ---
    if user_text in ["hi", "hello", "hey", "help", "good morning"]:
        return jsonify({"response": "Hello there! 👋 I am your automated support assistant. How can I help you with your order today?"})
    
    if user_text in ["thank you", "thanks", "ok", "okay"]:
        return jsonify({"response": "You're very welcome! Is there anything else you need help with?"})

    # --- 3. CHECK FOR ORDER ID IF WE NEED IT ---
    # If the bot asked for an Order ID, it will listen for 10 digits here
    if stage == "waiting_for_order_id":
        if re.match(r'.*\b\d{10}\b.*', user_text):
            session['order_verified'] = True
            
            # Direct them back to the issue they were talking about
            if session.get('issue_type') == "missing":
                bot_response = "Thank you, I've pulled up your account. Now, regarding the missing items—could you tell me exactly which items were not delivered?"
                session['conversation_stage'] = "asking_details"
            elif session.get('issue_type') == "delay":
                bot_response = "Thanks for the Order ID! I see your order tracking. Can you tell me roughly how many minutes late the delivery is?"
                session['conversation_stage'] = "asking_details"
            else:
                bot_response = "Thank you, I have verified your Order ID. Could you please provide a few more details about what went wrong so I can fix it?"
                session['conversation_stage'] = "chatting"
        else:
            bot_response = "I am having trouble finding a 10-digit number in your message. Could you please double-check your Order ID and type it again?"
        
        return jsonify({"response": bot_response})

    # --- 4. ASKING FOR DETAILS (MULTI-TURN) ---
    if stage == "asking_details":
        if session.get('issue_type') == "missing":
            bot_response = f"I appreciate you providing those details. I have logged that '{user_input}' was missing. Let me run a quick check with the restaurant...\n\nI apologize, but the restaurant's dispatch system confirms all items were packed. I cannot process a refund for this right now. I know this is frustrating."
        elif session.get('issue_type') == "delay":
            bot_response = f"I understand. {user_input} is definitely longer than expected. However, my system shows the delivery partner is stuck in traffic. Since it hasn't exceeded our maximum 60-minute threshold, I cannot offer compensation right now."
        else:
            bot_response = "Thank you for explaining that. Let me check my system... Unfortunately, based on our current policies, I am unable to make any changes or issue a refund for this specific order. I apologize for the inconvenience."
        
        session['conversation_stage'] = "chatting" # Reset
        return jsonify({"response": bot_response})

    # --- 5. NATURAL LANGUAGE INTENT DETECTION ---
    # This is where the bot "reads" natural sentences and acts empathetic
    
    if any(word in user_text for word in ["missing", "broken", "wrong", "spilled", "ruined", "cold"]):
        session['issue_type'] = "missing"
        if not session.get('order_verified'):
            session['conversation_stage'] = "waiting_for_order_id"
            bot_response = "Oh no, I am so sorry to hear that your food arrived like that! I definitely want to help you fix this. To get started, could you please share your 10-digit Order ID?"
        else:
            session['conversation_stage'] = "asking_details"
            bot_response = "I am really sorry about that. Could you tell me exactly which items were missing or damaged so I can log it in our system?"
            
    elif any(word in user_text for word in ["late", "where", "track", "delay", "not here", "taking so long"]):
        session['issue_type'] = "delay"
        if not session.get('order_verified'):
            session['conversation_stage'] = "waiting_for_order_id"
            bot_response = "I know waiting for food can be frustrating. Let me check the status for you! Could you please provide your 10-digit Order ID?"
        else:
            session['conversation_stage'] = "asking_details"
            bot_response = "I understand the wait is frustrating. How many minutes past the estimated delivery time is it?"

    elif any(word in user_text for word in ["refund", "money", "cancel", "return", "charge"]):
        session['issue_type'] = "refund"
        if not session.get('order_verified'):
            session['conversation_stage'] = "waiting_for_order_id"
            bot_response = "I can certainly look into a refund or cancellation for you. First, I just need your 10-digit Order ID."
        else:
            session['conversation_stage'] = "asking_details"
            bot_response = "I see. To process a refund request, could you briefly explain the main reason you are asking for your money back?"

    else:
        # A much smarter fallback response
        bot_response = "I'm listening. Could you give me a little more context? Are you dealing with a delayed delivery, a missing item, or something else entirely?"

    return jsonify({"response": bot_response})

if __name__ == "__main__":
    app.run(debug=True)