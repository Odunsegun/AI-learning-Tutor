from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import json
import random
from openai import OpenAI


# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

import os
openai.api_key = os.getenv("OPENAI_API_KEY")

# Set OpenAI API key
#client = OpenAI(api_key="OPENAI-API-KEY")  # ✅ Replace with your real key

# Load questions from file
with open("questions.json") as f:
    questions = json.load(f)


@app.route("/quiz", methods=["GET"])
def get_quiz():
    topic = request.args.get("topic", "math")
    user_id = request.args.get("user_id", None)

    with open("questions.json") as f:
        all_questions = json.load(f)

    topic_questions = all_questions.get(topic, [])

    if not user_id:
        filtered = [q for q in topic_questions if q.get("difficulty") == "easy"]
        return jsonify(random.sample(filtered, min(5, len(filtered))))

    try:
        with open("user_data.json") as f:
            user_data = json.load(f)
    except:
        user_data = {}

    topic_stats = user_data.get(user_id, {}).get(topic, {"correct": 0, "total": 0})
    correct = topic_stats.get("correct", 0)
    total = topic_stats.get("total", 0)
    accuracy = correct / total if total > 0 else 0

    if accuracy >= 0.8:
        difficulty = "hard"
    elif accuracy >= 0.5:
        difficulty = "medium"
    else:
        difficulty = "easy"

    # ✅ First try to get questions with matching difficulty
    filtered_questions = [q for q in topic_questions if q.get("difficulty") == difficulty]

    # ✅ If fewer than 4, fill in from other difficulties
    if len(filtered_questions) < 4:
        extra = [q for q in topic_questions if q.get("difficulty") != difficulty]
        random.shuffle(extra)
        filtered_questions.extend(extra)

    random.shuffle(filtered_questions)

    return jsonify(filtered_questions[:min(8, max(4, len(filtered_questions)))])


@app.route("/submit", methods=["POST"])
def submit_answer():
    try:
        data = request.get_json()
        question = data["question"]
        user_answer = data["user_answer"]
        correct_answer = data["correct_answer"]
        user_id = data.get("user_id", "anonymous")
        topic = data.get("topic", "unknown")

        is_correct = user_answer.strip().lower() == correct_answer.strip().lower()

        if is_correct:
            explanation = "✅ Correct!"
        else:
            prompt = f"""
You are an AI tutor.

Question: {question}
User Answer: {user_answer}
Correct Answer: {correct_answer}

Explain why the user's answer is incorrect in a helpful, beginner-friendly way.
"""
            try:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": prompt}]
                )
                explanation = response.choices[0].message.content

            except Exception as e:
                explanation = f"❌ Incorrect. (GPT error: {e})"

        try:
            with open("user_data.json", "r") as f:
                user_data = json.load(f)
        except:
            user_data = {}

        if user_id not in user_data:
            user_data[user_id] = {}
        if topic not in user_data[user_id]:
            user_data[user_id][topic] = {"correct": 0, "total": 0}

        user_data[user_id][topic]["total"] += 1
        if is_correct:
            user_data[user_id][topic]["correct"] += 1

        with open("user_data.json", "w") as f:
            json.dump(user_data, f, indent=2)

        return jsonify({
            "correct": is_correct,
            "explanation": explanation
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/add-question", methods=["POST"])
def add_question():
    try:
        data = request.get_json()
        topic = data["topic"]
        question = data["question"]
        options = data["options"]
        answer = data["answer"]
        difficulty = data["difficulty"]

        with open("questions.json", "r") as f:
            questions = json.load(f)

        if topic not in questions:
            questions[topic] = []

        questions[topic].append({
            "question": question,
            "options": options,
            "answer": answer,
            "difficulty": difficulty
        })

        with open("questions.json", "w") as f:
            json.dump(questions, f, indent=2)

        return jsonify({"message": "✅ Question added successfully."})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/generate", methods=["POST"])
def generate_quiz():
    try:
        data = request.get_json()
        topic = data.get("topic", "")

        prompt = f"""
Generate 5 beginner-friendly multiple-choice questions on the topic: {topic}.
Each question should have:
- A question string
- 4 answer options
- The correct answer marked

Return the result in JSON format like this:

[
  {{
    "question": "...",
    "options": ["A", "B", "C", "D"],
    "answer": "B"
  }},
  ...
]
"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.choices[0].message.content
        generated_questions = json.loads(text)

        return jsonify(generated_questions)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
