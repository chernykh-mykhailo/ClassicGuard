document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const chatId = urlParams.get("chat_id") || "0"; // Default or fallback chat_id
    const questionsList = document.getElementById("questions-list");
    const addQuestionBtn = document.getElementById("add-question");
    const form = document.getElementById("settings-form");

    // Fetch existing settings for this specific chat
    fetch(`/api/settings?chat_id=${chatId}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById("action").value = data.action;
            document.getElementById("check-ip").checked = data.check_ip;
            document.getElementById("check-device").checked = data.check_device;
            document.getElementById("check-avatar").checked = data.check_avatar;
            document.getElementById("avatar-min-days").value = data.avatar_min_days;
            document.getElementById("log-channel").value = data.log_channel || "";

            questionsList.innerHTML = ""; // Clear loader/default
            if (data.questions) {
                data.questions.forEach(q => renderQuestion(q.q, q.a.join(", ")));
            }
        });

    function renderQuestion(questionText = "", answersText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.innerHTML = `
            <input type="text" placeholder="Запитання (наприклад, Чий Крим?)" class="q-text" value="${questionText}" required>
            <input type="text" placeholder="Варіанти відповідей через кому (наприклад, України, український)" class="q-ans" value="${answersText}" required>
            <button type="button" class="btn-secondary remove-btn" style="background:#ff4a4a; padding:6px 12px; font-size:12px;">Видалити</button>
        `;
        item.querySelector(".remove-btn").addEventListener("click", () => item.remove());
        questionsList.appendChild(item);
    }

    addQuestionBtn.addEventListener("click", () => renderQuestion());

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const questions = [];
        const items = questionsList.querySelectorAll(".question-item");
        items.forEach(item => {
            const q = item.querySelector(".q-text").value.trim();
            const a = item.querySelector(".q-ans").value.split(",").map(ans => ans.trim()).filter(Boolean);
            if (q && a.length > 0) {
                questions.push({ q, a });
            }
        });

        const settings = {
            action: document.getElementById("action").value,
            check_ip: document.getElementById("check-ip").checked,
            check_device: document.getElementById("check-device").checked,
            check_avatar: document.getElementById("check-avatar").checked,
            avatar_min_days: parseInt(document.getElementById("avatar-min-days").value, 10),
            log_channel: document.getElementById("log-channel").value.trim(),
            questions: questions
        };

        fetch(`/api/settings?chat_id=${chatId}`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(settings)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert("Налаштування успішно збережено!");
                tg.close();
            } else {
                alert("Помилка збереження налаштувань.");
            }
        })
        .catch(() => {
            alert("Помилка підключення до сервера.");
        });
    });
});
