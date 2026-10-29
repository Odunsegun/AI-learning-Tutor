from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import random
from openai import OpenAI, OpenAIError
from pathlib import Path


# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

import os

BASE_DIR = Path(__file__).resolve().parent
QUESTIONS_FILE = BASE_DIR / "questions.json"
USER_DATA_FILE = BASE_DIR / "user_data.json"
client = None


def get_client():
    global client
    if client is None:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("Set OPENAI_API_KEY to enable AI features.")
        client = OpenAI(timeout=30.0, max_retries=1)
    return client


def payload(*fields):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required.")
    for field in fields:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"{field} must be a non-empty string.")
    return data


def valid_question(q):
    return (isinstance(q, dict)
            and isinstance(q.get("question"), str) and bool(q["question"].strip())
            and isinstance(q.get("options"), list) and len(q["options"]) == 4
            and all(isinstance(o, str) and o.strip() for o in q["options"])
            and len(set(q["options"])) == 4
            and q.get("answer") in q["options"])


@app.errorhandler(ValueError)
def invalid_input(error):
    return jsonify(error=str(error)), 400


@app.route("/quiz", methods=["GET"])
def get_quiz():
    topic = request.args.get("topic", "math")
    user_id = request.args.get("user_id", None)

    with open(QUESTIONS_FILE, encoding="utf-8") as f:
        all_questions = json.load(f)

    topic_questions = all_questions.get(topic, [])

    if not user_id:
        filtered = [q for q in topic_questions if q.get("difficulty") == "easy"]
        return jsonify(random.sample(filtered, min(5, len(filtered))))

    try:
        with open(USER_DATA_FILE, encoding="utf-8") as f:
            user_data = json.load(f)
    except FileNotFoundError:
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
        data = payload("question", "user_answer", "correct_answer")
        question = data["question"]
        user_answer = data["user_answer"]
        correct_answer = data["correct_answer"]
        user_id = data.get("user_id", "anonymous")
        topic = data.get("topic", "unknown")

        if not all(isinstance(value, str) and value.strip() for value in (user_id, topic)):
            raise ValueError("user_id and topic must be non-empty strings.")

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
                response = get_client().chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o"),
                    messages=[{"role": "user", "content": prompt}]
                )
                explanation = response.choices[0].message.content or f"The correct answer is {correct_answer}."

            except (OpenAIError, RuntimeError):
                explanation = f"Incorrect. The correct answer is {correct_answer}. AI explanation is unavailable."


        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except FileNotFoundError:
            user_data = {}

        if user_id not in user_data:
            user_data[user_id] = {}
        if topic not in user_data[user_id]:
            user_data[user_id][topic] = {"correct": 0, "total": 0}

        user_data[user_id][topic]["total"] += 1
        if is_correct:
            user_data[user_id][topic]["correct"] += 1

        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(user_data, f, indent=2)

        return jsonify({
            "correct": is_correct,
            "explanation": explanation
        })

    except ValueError as e:
        return invalid_input(e)
    except Exception:
        app.logger.exception("Request failed")
        return jsonify(error="Unable to save your request."), 500


@app.route("/add-question", methods=["POST"])
def add_question():
    try:
        data = payload("topic", "question", "answer", "difficulty")
        if not valid_question(data) or data["difficulty"] not in ("easy", "medium", "hard"):
            raise ValueError("Provide four distinct options, an answer matching an option, and a valid difficulty.")
        topic = data["topic"]
        question = data["question"]
        options = data["options"]
        answer = data["answer"]
        difficulty = data["difficulty"]

        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            questions = json.load(f)

        if topic not in questions:
            questions[topic] = []

        questions[topic].append({
            "question": question,
            "options": options,
            "answer": answer,
            "difficulty": difficulty
        })

        with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(questions, f, indent=2)

        return jsonify({"message": "✅ Question added successfully."})

    except ValueError as e:
        return invalid_input(e)
    except Exception:
        app.logger.exception("Request failed")
        return jsonify(error="Unable to save your request."), 500


@app.route("/generate", methods=["POST"])
def generate_quiz():
    data = payload("topic")
    question_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "answer": {"type": "string"},
        },
        "required": ["question", "options", "answer"],
        "additionalProperties": False,
    }
    try:
        response = get_client().chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            messages=[
                {"role": "system", "content": "Generate exactly 5 beginner-friendly multiple-choice questions, each with 4 distinct options. The answer must exactly match one option."},
                {"role": "user", "content": data["topic"]},
            ],
            response_format={"type": "json_schema", "json_schema": {
                "name": "quiz", "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"questions": {"type": "array", "items": question_schema}},
                    "required": ["questions"], "additionalProperties": False,
                },
            }},
        )
        choice = response.choices[0]
        if choice.finish_reason != "stop" or choice.message.refusal:
            return jsonify(error="AI could not complete this quiz. Try another topic."), 502
        generated = json.loads(choice.message.content)
        questions = generated.get("questions") if isinstance(generated, dict) else None
        if not isinstance(questions, list) or len(questions) != 5 or not all(valid_question(q) for q in questions):
            raise ValueError("Invalid generated quiz")
        return jsonify(questions)
    except RuntimeError as error:
        return jsonify(error=str(error)), 503
    except (OpenAIError, ValueError, TypeError, IndexError):
        return jsonify(error="AI quiz generation failed. Please try again."), 502


if __name__ == "__main__":
    app.run(debug=False)
