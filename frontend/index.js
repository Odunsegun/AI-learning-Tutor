if (!localStorage.getItem("user_id")) {
      localStorage.setItem("user_id", crypto.randomUUID());
    }
    const userId = localStorage.getItem("user_id");

    let totalQuestions = 0;
    let correctCount = 0;
    let hasAnswered = [];

    async function loadQuiz() {
      const topic = document.getElementById("topicSelect").value;
      const res = await fetch(`http://127.0.0.1:5000/quiz?topic=${topic}&user_id=${userId}`);
      const questions = await res.json();
      totalQuestions = questions.length;
      correctCount = 0;
      hasAnswered = Array(totalQuestions).fill(false);
      document.getElementById("scoreDisplay").textContent = `Score: 0 / ${totalQuestions}`;
      document.getElementById("quizContainer").innerHTML = "";
      document.getElementById("retryBtn").style.display = "none";

      questions.forEach((q, i) => {
        const div = document.createElement("div");
        div.className = "question";
        div.innerHTML = `
          <p><strong>Q${i + 1}: ${q.question}</strong></p>
          ${q.options.map(opt => `
            <label><input type="radio" name="q${i}" value="${opt}"> ${opt}</label><br>
          `).join("")}
          <button onclick="submitAnswer(${i}, '${q.question.replace(/'/g, "\\'")}', '${q.answer.replace(/'/g, "\\'")}')">Submit</button>
          <div id="explanation${i}" class="explanation"></div>
        `;
        document.getElementById("quizContainer").appendChild(div);
      });
    }

    async function submitAnswer(index, question, correctAnswer) {
      if (hasAnswered[index]) return; // prevent double submission
      hasAnswered[index] = true;

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
          topic: document.getElementById("topicSelect").value
        })
      });

      const data = await res.json();
      const output = `
        ${data.correct ? "✅ Correct!" : "❌ Incorrect!"}
        <br>${data.explanation}
      `;
      document.getElementById(`explanation${index}`).innerHTML = output;

      if (data.correct) correctCount++;
      document.getElementById("scoreDisplay").textContent = `Score: ${correctCount} / ${totalQuestions}`;

      if (hasAnswered.every(Boolean)) {
        setTimeout(() => {
          alert(`🎉 Final Score: ${correctCount} / ${totalQuestions}`);
          document.getElementById("retryBtn").style.display = "inline-block";
        }, 500);
      }
    }

    async function generateQuiz() {
      const topic = document.getElementById("customTopic").value;
      if (!topic) return alert("Please enter a topic.");

      const res = await fetch("http://127.0.0.1:5000/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic })
      });

      const questions = await res.json();

      if (questions.error) {
        alert("Error generating quiz: " + questions.error);
        return;
      }

      // Reuse existing rendering logic
      totalQuestions = questions.length;
      correctCount = 0;
      hasAnswered = Array(totalQuestions).fill(false);
      document.getElementById("scoreDisplay").textContent = `Score: 0 / ${totalQuestions}`;
      const container = document.getElementById("quizContainer");
      container.innerHTML = "";

      questions.forEach((q, i) => {
        const div = document.createElement("div");
        div.className = "question";
        div.innerHTML = `
          <p><strong>Q${i + 1}: ${q.question}</strong></p>
          ${q.options.map(opt => `
            <label><input type="radio" name="q${i}" value="${opt}"> ${opt}</label><br>
          `).join("")}
          <button onclick="submitAnswer(${i}, '${q.question.replace(/'/g, "\\'")}', '${q.answer.replace(/'/g, "\\'")}')">Submit</button>
          <div id="explanation${i}" class="explanation"></div>
        `;
        container.appendChild(div);
      });
    }


    // Auto-load first quiz
    window.onload = () => {
      loadQuiz();
    };