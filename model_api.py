from flask import Flask, request, jsonify
import pickle
import pandas as pd
from nltk.sentiment import SentimentIntensityAnalyzer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

model = pickle.load(open("escalation_model.pkl","rb"))
scaler = pickle.load(open("scaler.pkl","rb"))
sia = SentimentIntensityAnalyzer()

FEATURE_NAMES = [
    "num_turns",
    "num_user_msgs",
    "num_bot_msgs",
    "user_bot_ratio",
    "avg_sentiment",
    "min_sentiment",
    "sentiment_trend",
    "fallback_count",
    "frustration_score",
    "generic_response_ratio",
]

fallback_phrases = [
    "i don't understand",
    "sorry",
    "can you rephrase",
    "i didn't get that",
    "unable to help",
    "not sure",
    "cannot help",
    "please clarify",
]

frustration_keywords = [
    "frustrated",
    "angry",
    "not working",
    "still",
    "again",
    "why",
    "worst",
    "hate",
    "useless",
    "issue",
    "problem",
    "error",
    "human",
    "agent",
    "refund",
    "late",
]

generic_responses = [
    "i am here to help",
    "please clarify",
    "can you provide more details",
    "let me check",
    "i will assist you",
    "thanks for reaching out",
]


def explicit_escalation_request(user_msgs):
    escalation_terms = [
        "human",
        "agent",
        "person",
        "representative",
        "real person",
        "customer service",
    ]

    return any(
        term in message.lower()
        for message in user_msgs
        for term in escalation_terms
    )


def parse_conversation(text):
    parsed = []

    for turn in text.split("||"):
        if ":" in turn:
            role, message = turn.split(":", 1)
            parsed.append((role.strip(), message.strip()))

    if not parsed and text.strip():
        parsed.append(("User", text.strip()))

    return parsed


def split_roles(parsed):
    user_msgs = [message for role, message in parsed if role.lower() == "user"]
    bot_msgs = [message for role, message in parsed if role.lower() == "bot"]
    return user_msgs, bot_msgs


def sentiment_scores(messages):
    return [sia.polarity_scores(message)["compound"] for message in messages]


def repetition_score(user_msgs):
    if len(user_msgs) < 2:
        return 0

    try:
        vectorizer = TfidfVectorizer().fit(user_msgs)
        vectors = vectorizer.transform(user_msgs)
    except ValueError:
        return 0

    sim_scores = []

    for i in range(1, len(user_msgs)):
        sim = cosine_similarity(vectors[i], vectors[i - 1])[0][0]
        sim_scores.append(sim)

    return max(sim_scores) if sim_scores else 0


def fallback_count(bot_msgs):
    count = 0

    for message in bot_msgs:
        message_lower = message.lower()
        if any(phrase in message_lower for phrase in fallback_phrases):
            count += 1

    return count


def frustration_score(user_msgs):
    score = 0

    for message in user_msgs:
        message_lower = message.lower()
        if any(keyword in message_lower for keyword in frustration_keywords):
            score += 1

    return score


def generic_ratio(bot_msgs):
    if not bot_msgs:
        return 0

    generic_count = 0

    for message in bot_msgs:
        message_lower = message.lower()
        if any(generic in message_lower for generic in generic_responses):
            generic_count += 1

    return generic_count / len(bot_msgs)


def extract_features(conversation_text):
    parsed = parse_conversation(conversation_text)
    user_msgs, bot_msgs = split_roles(parsed)

    num_turns = len(parsed)
    num_user_msgs = len(user_msgs)
    num_bot_msgs = len(bot_msgs)
    user_bot_ratio = num_user_msgs / num_bot_msgs if num_bot_msgs else num_user_msgs

    sentiments = sentiment_scores(user_msgs)
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
    min_sentiment = min(sentiments) if sentiments else 0
    sentiment_trend = sentiments[-1] - sentiments[0] if len(sentiments) > 1 else 0

    features = [[
        num_turns,
        num_user_msgs,
        num_bot_msgs,
        user_bot_ratio,
        avg_sentiment,
        min_sentiment,
        -sentiment_trend if sentiment_trend < 0 else 0,
        fallback_count(bot_msgs) * 1.5,
        frustration_score(user_msgs) * 1.5,
        generic_ratio(bot_msgs) * 1.2,
    ]]

    return pd.DataFrame(features, columns=FEATURE_NAMES)


@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True) or {}
    data = payload.get("conversation", "")

    if not isinstance(data, str) or not data.strip():
        return jsonify({"error": "conversation must be a non-empty string"}), 400

    parsed = parse_conversation(data)
    user_msgs, _ = split_roles(parsed)

    if explicit_escalation_request(user_msgs):
        return jsonify({"escalate": 1, "probability": 1.0})

    features = extract_features(data)
    features_scaled = scaler.transform(features)
    probability = model.predict_proba(features_scaled)[0][1]
    prediction = 1 if probability >= 0.5 else 0

    return jsonify({"escalate": prediction, "probability": float(probability)})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(port=8000, debug=True)
