const topic = localStorage.getItem("cyber_topic");
const userId = localStorage.getItem("user_id") || crypto.randomUUID();
localStorage.setItem("user_id", userId);

let totalQuestions = 0;
let correctCount = 0;
let answered = [];

async function loadQuiz() {
  const res = await fetch(`http://127.0.0.1:5000/quiz?topic=${topic}&user_id=${userId}`);
  const questions = await res.json();
  totalQuestions = questions.length;
  correctCount = 0;
  answered = Array(totalQuestions).fill(false);

  const container = document.getElementById("quizContainer");
  container.innerHTML = "";
  document.getElementById("scoreDisplay").textContent = `Score: 0 / ${totalQuestions}`;

  questions.forEach((q, i) => {
    const div = document.createElement("div");
    div.className = "question";
    div.innerHTML = `
      <p><strong>Q${i + 1}: ${q.question}</strong></p>
      ${q.options.map(opt => `
        <label><input type="radio" name="q${i}" value="${opt}"> ${opt}</label><br>
      `).join("")}
      <button onclick="submitAnswer(${i}, '${escapeQuotes(q.question)}', '${escapeQuotes(q.answer)}')">Submit</button>
      <div id="explanation${i}" class="explanation"></div>
    `;
    container.appendChild(div);
  });
}

function escapeQuotes(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

async function submitAnswer(index, question, correctAnswer) {
  if (answered[index]) return;
  answered[index] = true;

  const selected = document.querySelector(`input[name="q${index}"]:checked`);
  if (!selected) {
    alert("Please select an answer.");
    return;
  }

  const userAnswer = selected.value;

  const res = await fetch("http://127.0.0.1:5000/submit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      user_answer: userAnswer,
      correct_answer: correctAnswer,
      user_id: userId,
      topic
    })
  });

  const data = await res.json();
  const output = `${data.correct ? "✅ Correct!" : "❌ Incorrect!"}<br>${data.explanation}`;
  document.getElementById(`explanation${index}`).innerHTML = output;

  if (data.correct) correctCount++;
  document.getElementById("scoreDisplay").textContent = `Score: ${correctCount} / ${totalQuestions}`;

  if (answered.every(a => a)) {
    setTimeout(() => {
      alert(`🎉 Final Score: ${correctCount} / ${totalQuestions}`);
    }, 500);
  }
}

window.onload = loadQuiz;
