import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as tutor


class TutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.question = dict(question="2 + 2?", options=["1", "2", "3", "4"], answer="4", difficulty="easy")
        (self.root / "questions.json").write_text(json.dumps({"math": [self.question]}), encoding="utf-8")
        for name, value in [("QUESTIONS_FILE", self.root / "questions.json"), ("USER_DATA_FILE", self.root / "user_data.json"), ("client", None)]:
            patcher = patch.object(tutor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.http = tutor.app.test_client()

    def response(self, content, finish="stop", refusal=None):
        return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish, message=SimpleNamespace(content=content, refusal=refusal))])

    def test_saved_quiz_and_score_without_key(self):
        self.assertEqual(self.http.get("/quiz?topic=math").status_code, 200)
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            for answer in ["4", "3"]:
                result = self.http.post("/submit", json=dict(question="2 + 2?", user_answer=answer, correct_answer="4", user_id="test", topic="math"))
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json["correct"], answer == "4")
                self.assertNotIn("GPT error", result.json["explanation"])
        stats = json.loads(tutor.USER_DATA_FILE.read_text())["test"]["math"]
        self.assertEqual(stats, {"correct": 1, "total": 2})

    def test_generation_without_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            self.assertEqual(self.http.post("/generate", json={"topic": "math"}).status_code, 503)

    def test_client_initializes_from_environment(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only"}), patch.object(tutor, "OpenAI") as constructor:
            self.assertIs(tutor.get_client(), constructor.return_value)
            tutor.get_client()
            constructor.assert_called_once()

    def test_generation_validates_responses(self):
        tutor.client = Mock()
        create = tutor.client.chat.completions.create
        create.return_value = self.response(json.dumps({"questions": [self.question] * 5}))
        self.assertEqual(len(self.http.post("/generate", json={"topic": "math"}).json), 5)
        self.assertTrue(create.call_args.kwargs["response_format"]["json_schema"]["strict"])
        for response in [self.response("```json"), self.response('{}'), self.response('[]'), self.response(None, refusal="No"), self.response('{}', finish="length"), self.response(json.dumps({"questions": [dict(self.question, answer="wrong")] * 5}))]:
            create.return_value = response
            self.assertEqual(self.http.post("/generate", json={"topic": "math"}).status_code, 502)

    def test_explanation_uses_client(self):
        tutor.client = Mock()
        tutor.client.chat.completions.create.return_value = self.response("Two plus two is four.")
        result = self.http.post("/submit", json=dict(question="2 + 2?", user_answer="3", correct_answer="4"))
        self.assertEqual(result.json["explanation"], "Two plus two is four.")

    def test_invalid_requests_and_teacher_write(self):
        for endpoint in ["/generate", "/submit", "/add-question"]:
            for value in [[], {}, {"topic": 42}]:
                self.assertEqual(self.http.post(endpoint, json=value).status_code, 400)
        result = self.http.post("/add-question", json=dict(self.question, topic="science"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(self.http.get("/quiz?topic=science").json), 1)
        self.assertEqual(self.http.post("/add-question", json=dict(self.question, topic="science", answer="missing")).status_code, 400)


if __name__ == "__main__":
    unittest.main()
