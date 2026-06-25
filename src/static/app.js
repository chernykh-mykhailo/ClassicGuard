document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const queryId = urlParams.get("query_id");
    const session = urlParams.get("session");
    const container = document.getElementById("questions-container");
    const form = document.getElementById("captcha-form");
    const statusDiv = document.getElementById("status");

    const paramStr = queryId ? `query_id=${queryId}` : `session=${session}`;
    const emojiSelections = {}; // questionId -> selected emoji index

    if (!queryId && !session) {
        showStatus("Невірне посилання для верифікації.", "error");
        return;
    }

    fetch(`/api/questions?${paramStr}`)
        .then(res => res.json())
        .then(data => {
            if (data.questions && data.questions.length > 0) {
                data.questions.forEach((q) => {
                    if (q.type === "emoji") {
                        renderEmojiQuestion(q);
                    } else {
                        renderTextQuestion(q);
                    }
                });
            } else if (data.detail) {
                showStatus("Невірна або застаріла сесія.", "error");
            } else {
                showStatus("Не вдалося завантажити питання капчі", "error");
            }
        })
        .catch(() => showStatus("Помилка з'єднання з сервером", "error"));

    function renderTextQuestion(q) {
        const group = document.createElement("div");
        group.className = "form-group";
        group.innerHTML = `
            <label for="q-${q.id}">${q.q}</label>
            <input type="text" id="q-${q.id}" name="${q.id}" required placeholder="Ваша відповідь..." autocomplete="off">
        `;
        container.appendChild(group);
    }

    function renderEmojiQuestion(q) {
        const group = document.createElement("div");
        group.className = "form-group";

        const label = document.createElement("label");
        label.textContent = q.q;
        group.appendChild(label);

        const grid = document.createElement("div");
        grid.className = "emoji-grid";

        q.emojis.forEach((emoji, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = "emoji-btn";
            btn.textContent = emoji;
            btn.dataset.idx = idx;
            btn.addEventListener("click", () => {
                // Deselect all in this grid
                grid.querySelectorAll(".emoji-btn").forEach(b => b.classList.remove("selected"));
                btn.classList.add("selected");
                emojiSelections[q.id] = idx;
            });
            grid.appendChild(btn);
        });

        group.appendChild(grid);
        container.appendChild(group);
    }

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const answers = {};

        // Text inputs
        const inputs = form.querySelectorAll("input[type='text']");
        inputs.forEach(input => {
            answers[input.name] = input.value;
        });

        // Emoji selections
        Object.entries(emojiSelections).forEach(([qId, idx]) => {
            answers[qId] = idx;
        });

        const deviceInfo = navigator.userAgent;
        showStatus("Перевірка відповідей...", "");

        const payload = { answers, device_info: deviceInfo };
        if (queryId) payload.query_id = queryId;
        if (session) payload.session = session;

        fetch("/api/verify", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showStatus("✅ Успішно! Вас допущено до чату.", "success");
                setTimeout(() => tg.close(), 3000);
            } else {
                showStatus(data.reason || "Перевірку не пройдено.", "error");
            }
        })
        .catch(() => showStatus("Помилка надсилання перевірки.", "error"));
    });

    function showStatus(text, type) {
        statusDiv.className = `status ${type}`;
        statusDiv.textContent = text;
    }
});
