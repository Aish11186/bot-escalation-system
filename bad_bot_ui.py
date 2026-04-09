import streamlit as st
import re

st.set_page_config(page_title="Delivery Support Bot", page_icon="🤖")
st.title("🤖 Delivery Support Bot")
st.caption("This is just a bot")


if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I am your automated assistant. Please enter your 10-digit Order ID so I can look up your details."}
    ]
    st.session_state.order_verified = False
    st.session_state.conversation_stage = "start" 

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("Type your message here..."):
    
    with st.chat_message("user"):
        st.markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    user_text = user_input.strip().lower()
    bot_response = ""

    
    if not st.session_state.order_verified:
        if re.match(r'.*\b\d{10}\b.*', user_text):
            st.session_state.order_verified = True
            bot_response = "Thank you. I have pulled up your order details. Are you contacting us regarding a delay, a missing item, or a refund?"
        else:
            bot_response = "I couldn't find a 10-digit number in your message. I need your Order ID before I can access your account."

    
    elif any(word in user_text for word in ["human", "agent", "person", "representative", "real"]):
        bot_response = "I understand you'd like to speak to an agent. However, I can resolve 95% of issues right here! Let's try. What is the main issue with the order?"

    
    
    
    elif st.session_state.conversation_stage == "asking_missing_item":
        
        bot_response = f"Got it. I have noted that '{user_input}' is missing from your bag. Let me check the system... \n\nUnfortunately, the restaurant marked all items as packed. We cannot issue a refund right now. Is there anything else?"
        st.session_state.conversation_stage = "start" 
        
    
    elif st.session_state.conversation_stage == "asking_time":
        bot_response = "Thank you for the timeline. Since it has not been more than 45 minutes past the original ETA, our system cannot compensate you yet. Please wait a bit longer!"
        st.session_state.conversation_stage = "start" 

    
    elif st.session_state.conversation_stage == "start":
        
        
        if "refund" in user_text and any(neg in user_text for neg in ["don't", "not", "do not"]):
            bot_response = "I understand you DO NOT want a refund. In that case, would you like me to track the delivery or report a missing item?"
            
        elif any(word in user_text for word in ["refund", "money", "cancel", "return"]):
            bot_response = "I see you are inquiring about a refund. Was your order paid via Credit Card or UPI/Wallet?"
            st.session_state.conversation_stage = "start" 
            
        elif any(word in user_text for word in ["missing", "broken", "spilled", "wrong"]):
            bot_response = "I am so sorry to hear there is an issue with the items. Which exact item was missing or damaged?"
            st.session_state.conversation_stage = "asking_missing_item" 
            
        elif any(word in user_text for word in ["where", "late", "track", "delay", "not here"]):
            bot_response = "I see your order is delayed. How many minutes past the original estimated delivery time is it?"
            st.session_state.conversation_stage = "asking_time" 
            
        else:
            bot_response = "I'm analyzing your request... I am not quite sure how to categorize that. Could you please specify if this is about delivery tracking, missing items, or refunds?"

    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})