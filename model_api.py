from flask import Flask, jsonify, request
import pickle
import re

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = Flask(__name__)

with open("escalation_model.pkl", "rb") as model_file:
    model = pickle.load(model_file)

with open("scaler.pkl", "rb") as scaler_file:
    scaler = pickle.load(scaler_file)

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

FALLBACK_PHRASES = [
    "i don't understand",
    "sorry",
    "can you rephrase",
    "i didn't get that",
    "unable to help",
    "not sure",
    "cannot help",
    "please clarify",
]

FRUSTRATION_KEYWORDS = [
    "frustrated",
    "angry",
    "still",
    "again",
    "same",
    "issue",
    "problem",
    "error",
    "human",
    "agent",
    "refund",
    "late",
    "waiting",
    "unacceptable",
]

GENERIC_RESPONSES = [
    "i can help",
    "please share your 10-digit order id",
    "please describe the problem",
    "how can i help",
]

POSITIVE_WORDS = {
    "thanks", "thank", "great", "good", "resolved", "helpful", "fine", "ok", "okay"
}

NEGATIVE_WORDS = {
    "frustrated", "angry", "late", "missing", "broken", "damaged", "wrong",
    "refund", "problem", "issue", "error", "terrible", "bad", "useless", "again"
}


def parse_conversation(conversation_text):
    """Convert the serialized history string into ordered role/message pairs."""
    parsed_turns = []

    for turn in conversation_text.split("||"):
        clean_turn = turn.strip()
        if not clean_turn:
            continue

        if ":" in clean_turn:
            role, message = clean_turn.split(":", 1)
            parsed_turns.append((role.strip(), message.strip()))
        else:
            parsed_turns.append(("User", clean_turn))

    return parsed_turns


def split_roles(parsed_turns):
    user_messages = [message for role, message in parsed_turns if role.lower() == "user"]
    bot_messages = [message for role, message in parsed_turns if role.lower() == "bot"]
    return user_messages, bot_messages


def score_message_sentiment(message):
    """Use a tiny rule-based fallback sentiment scorer so the API runs without NLTK data."""
    tokens = re.findall(r"\b\w+\b", message.lower())
    if not tokens:
        return 0.0

    positive_hits = sum(token in POSITIVE_WORDS for token in tokens)
    negative_hits = sum(token in NEGATIVE_WORDS for token in tokens)
    return (positive_hits - negative_hits) / len(tokens)


def sentiment_scores(messages):
    return [score_message_sentiment(message) for message in messages]


def repetition_score(user_messages):
    if len(user_messages) < 2:
        return 0.0

    try:
        vectorizer = TfidfVectorizer()
        vectors = vectorizer.fit_transform(user_messages)
    except ValueError:
        return 0.0

    similarities = []
    for index in range(1, len(user_messages)):
        similarity = cosine_similarity(vectors[index], vectors[index - 1])[0][0]
        similarities.append(float(similarity))

    return max(similarities) if similarities else 0.0


def count_phrase_matches(messages, phrases):
    count = 0
    for message in messages:
        lowered = message.lower()
        if any(phrase in lowered for phrase in phrases):
            count += 1
    return count


def generic_ratio(bot_messages):
    if not bot_messages:
        return 0.0
    return count_phrase_matches(bot_messages, GENERIC_RESPONSES) / len(bot_messages)


def frustration_score(user_messages):
    score = count_phrase_matches(user_messages, FRUSTRATION_KEYWORDS)
    score += 1 if repetition_score(user_messages) > 0.6 else 0
    return float(score)


def extract_features(conversation_text):
    """Build the exact 10 features expected by the trained model and scaler."""
    parsed_turns = parse_conversation(conversation_text)
    user_messages, bot_messages = split_roles(parsed_turns)

    user_sentiments = sentiment_scores(user_messages)
    avg_sentiment = float(np.mean(user_sentiments)) if user_sentiments else 0.0
    min_sentiment = float(np.min(user_sentiments)) if user_sentiments else 0.0
    sentiment_trend = (
        float(user_sentiments[-1] - user_sentiments[0]) if len(user_sentiments) > 1 else 0.0
    )

    feature_row = [[
        float(len(parsed_turns)),
        float(len(user_messages)),
        float(len(bot_messages)),
        float(len(user_messages) / len(bot_messages)) if bot_messages else float(len(user_messages)),
        avg_sentiment,
        min_sentiment,
        abs(sentiment_trend) if sentiment_trend < 0 else 0.0,
        float(count_phrase_matches(bot_messages, FALLBACK_PHRASES)),
        frustration_score(user_messages),
        float(generic_ratio(bot_messages)),
    ]]

    return pd.DataFrame(feature_row, columns=FEATURE_NAMES, dtype=float)


@app.route("/predict", methods=["POST"])
def predict():
    payload = request.get_json(silent=True) or {}
    conversation = payload.get("conversation", "")

    if not isinstance(conversation, str) or not conversation.strip():
        return jsonify({"error": "conversation must be a non-empty string"}), 400

    features = extract_features(conversation)
    scaled_features = scaler.transform(features)
    prediction = int(model.predict(scaled_features)[0])
    probability = float(model.predict_proba(scaled_features)[0][1])

    return jsonify({
        "prediction": prediction,
        "probability": probability,
        "escalate": prediction,
        "feature_names": FEATURE_NAMES,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(port=8000, debug=True)
