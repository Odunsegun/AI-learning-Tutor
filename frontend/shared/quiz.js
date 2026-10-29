const userId = localStorage.getItem("user_id") || crypto.randomUUID();
localStorage.setItem("user_id", userId);
const apiBase = "http://127.0.0.1:5000";
let quizVersion = 0;
let activeTopic = "";
let questions = [];
let answered = [];
let pending = [];
let correctCount = 0;

async function api(path, data) {
  const response = await fetch(apiBase + path, data === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data)
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Request failed. Please retry.");
  return result;
}

function updateScore() {
  document.getElementById("scoreDisplay").textContent = `Score: ${correctCount} / ${questions.length}`;
}

function renderQuiz(items, topic) {
  questions = items;
  activeTopic = topic;
  answered = items.map(() => false);
  pending = items.map(() => false);
  correctCount = 0;
  updateScore();
  const retry = document.getElementById("retryBtn");
  if (retry) retry.style.display = "none";
  const container = document.getElementById("quizContainer");
  container.replaceChildren();
  if (!items.length) container.textContent = "No questions available for this topic.";
  const version = quizVersion;
  items.forEach((q, index) => {
    const div = document.createElement("div");
    div.className = "question";
    const title = document.createElement("p");
    title.textContent = `Q${index + 1}: ${q.question}`;
    div.appendChild(title);
    q.options.forEach(option => {
      const label = document.createElement("label");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = `q${index}`;
      input.value = option;
      label.append(input, document.createTextNode(` ${option}`));
      div.append(label, document.createElement("br"));
    });
    const button = document.createElement("button");
    button.textContent = "Submit";
    button.onclick = () => { if (version === quizVersion) submitAnswer(index); };
    const explanation = document.createElement("div");
    explanation.id = `explanation${index}`;
    explanation.className = "explanation";
    div.append(button, explanation);
    container.appendChild(div);
  });
}

async function loadQuiz() {
  const topic = document.getElementById("topicSelect")?.value || localStorage.getItem("cyber_topic") || "intro";
  const version = ++quizVersion;
  try {
    const items = await api(`/quiz?${new URLSearchParams({ topic, user_id: userId })}`);
    if (version === quizVersion) renderQuiz(items, topic);
  } catch (error) {
    if (version === quizVersion) document.getElementById("quizContainer").textContent = error.message;
  }
}

async function submitAnswer(index) {
  if (answered[index] || pending[index]) return;
  const selected = document.querySelector(`input[name="q${index}"]:checked`);
  if (!selected) { alert("Please select an answer."); return; }
  pending[index] = true;
  const version = quizVersion;
  const q = questions[index];
  try {
    const data = await api("/submit", {
      question: q.question, user_answer: selected.value, correct_answer: q.answer,
      user_id: userId, topic: activeTopic
    });
    if (version !== quizVersion) return;
    answered[index] = true;
    document.getElementById(`explanation${index}`).textContent = data.explanation;
    if (data.correct) correctCount++;
    updateScore();
    if (answered.every(Boolean)) {
      alert(`Final Score: ${correctCount} / ${questions.length}`);
      const retry = document.getElementById("retryBtn");
      if (retry) retry.style.display = "inline-block";
    }
  } catch (error) {
    if (version === quizVersion) document.getElementById(`explanation${index}`).textContent = `${error.message} You can retry.`;
  } finally {
    if (version === quizVersion) pending[index] = false;
  }
}

async function generateQuiz() {
  const topic = document.getElementById("customTopic").value.trim();
  if (!topic) { alert("Please enter a topic."); return; }
  const version = ++quizVersion;
  try {
    const items = await api("/generate", { topic });
    if (version === quizVersion) renderQuiz(items, topic);
  } catch (error) {
    if (version === quizVersion) alert(error.message);
  }
}

window.onload = loadQuiz;
