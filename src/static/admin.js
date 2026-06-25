document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const chatId = urlParams.get("chat_id") || "0";
    const questionsList = document.getElementById("questions-list");
    const addQuestionBtn = document.getElementById("add-question");
    const form = document.getElementById("settings-form");
    const selectorContainer = document.getElementById("chat-selector-container");
    const chatSelect = document.getElementById("chat-select");
    const selectChatBtn = document.getElementById("select-chat-btn");

    let activeChatId = chatId;

    if (activeChatId === "0") {
        form.style.display = "none";
        selectorContainer.style.display = "block";

        const userId = tg.initDataUnsafe?.user?.id || 0;
        fetch(`/api/admin/chats?user_id=${userId}`)
            .then(res => res.json())
            .then(data => {
                chatSelect.innerHTML = "";
                if (data.chats && data.chats.length > 0) {
                    data.chats.forEach(c => {
                        const opt = document.createElement("option");
                        opt.value = c.id;
                        opt.textContent = c.title;
                        chatSelect.appendChild(opt);
                    });
                } else {
                    const opt = document.createElement("option");
                    opt.value = "";
                    opt.textContent = "Не знайдено підключених груп, де ви є адміном";
                    chatSelect.appendChild(opt);
                }
            });

        selectChatBtn.addEventListener("click", () => {
            const val = chatSelect.value;
            if (val) {
                activeChatId = val;
                selectorContainer.style.display = "none";
                form.style.display = "block";
                loadSettings(activeChatId);
            } else {
                alert("Будь ласка, оберіть дійсний чат.");
            }
        });
    } else {
        loadSettings(activeChatId);
    }

    function loadSettings(cid) {
        fetch(`/api/settings?chat_id=${cid}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById("action").value = data.action;
                document.getElementById("check-ip").checked = data.check_ip;
                document.getElementById("check-device").checked = data.check_device;
                document.getElementById("check-avatar").checked = data.check_avatar;
                document.getElementById("avatar-min-days").value = data.avatar_min_days;
                document.getElementById("log-channel").value = data.log_channel || "";

                questionsList.innerHTML = "";
                if (data.questions) {
                    data.questions.forEach(q => renderQuestion(q.q, q.a.join(", ")));
                }
            });
    }

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

        fetch(`/api/settings?chat_id=${activeChatId}`, {
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
