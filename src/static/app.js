document.addEventListener("DOMContentLoaded", () => {
    const tg = window.Telegram.WebApp;
    tg.expand();

    const urlParams = new URLSearchParams(window.location.search);
    const queryId = urlParams.get("query_id");
    const container = document.getElementById("questions-container");
    const form = document.getElementById("captcha-form");
    const statusDiv = document.getElementById("status");

    fetch(`/api/questions?query_id=${queryId}`)
        .then(res => res.json())
        .then(data => {
            if (data.questions) {
                data.questions.forEach((q) => {
                    const group = document.createElement("div");
                    group.className = "form-group";
                    group.innerHTML = `
                        <label for="q-${q.id}">${q.q}</label>
                        <input type="text" id="q-${q.id}" name="${q.id}" required placeholder="Ваша відповідь..." autocomplete="off">
                    `;
                    container.appendChild(group);
                });
            } else {
                showStatus("Не вдалося завантажити питання капчі", "error");
            }
        })
        .catch(() => {
            showStatus("Помилка з'єднання з сервером", "error");
        });

    form.addEventListener("submit", (e) => {
        e.preventDefault();
        
        const answers = {};
        const inputs = form.querySelectorAll("input[type='text']");
        inputs.forEach(input => {
            answers[input.name] = input.value;
        });

        const deviceInfo = navigator.userAgent;

        showStatus("Перевірка відповідей...", "");

        fetch("/api/verify", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                query_id: queryId,
                answers: answers,
                device_info: deviceInfo
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showStatus("Успішно! Вас допущено до чату. Ви можете закрити це вікно.", "success");
                setTimeout(() => {
                    tg.close();
                }, 3000);
            } else {
                showStatus(data.reason || "Перевірку не пройдено.", "error");
            }
        })
        .catch(() => {
            showStatus("Помилка надсилання перевірки.", "error");
        });
    });

    function showStatus(text, type) {
        statusDiv.className = `status ${type}`;
        statusDiv.textContent = text;
    }
});
