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
    const customLangContainer = document.getElementById("custom-lang-tags");
    const customLangInput = document.getElementById("custom-lang-input");
    const addCustomLangBtn = document.getElementById("add-custom-lang-btn");
    let customLanguages = [];

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

    function renderCustomLangTag(lang) {
        const tag = document.createElement("span");
        tag.style.cssText = "background:rgba(0,136,204,0.2); border:1px solid var(--accent-color); border-radius:4px; padding:2px 8px; font-size:12px; display:flex; align-items:center; gap:4px;";
        tag.innerHTML = `${lang.toUpperCase()} <button type="button" style="background:none; border:none; color:#ff4a4a; cursor:pointer; padding:0; font-size:14px; line-height:1;">&times;</button>`;
        tag.querySelector("button").addEventListener("click", () => {
            customLanguages = customLanguages.filter(l => l !== lang);
            tag.remove();
        });
        customLangContainer.appendChild(tag);
    }

    addCustomLangBtn.addEventListener("click", () => {
        const val = customLangInput.value.trim().toLowerCase();
        if (val && !customLanguages.includes(val) && !document.querySelector(`.lang-cb[value="${val}"]`)) {
            customLanguages.push(val);
            renderCustomLangTag(val);
            customLangInput.value = "";
        }
    });

    function getLogLanguages() {
        const checked = [];
        document.querySelectorAll(".lang-cb:checked").forEach(cb => checked.push(cb.value));
        return [...checked, ...customLanguages];
    }

    const PRESETS = {
        simple: {
            check_ip: true, check_avatar: true, avatar_min_count: 1,
            check_fingerprint: true, check_account_age: true, min_account_age_months: 3,
            check_cas: true, cas_action: "block",
            check_device: false, check_premium: false, check_language: false,
            check_osint: false, osint_action: "log"
        },
        balanced: {
            check_ip: true, check_avatar: true, avatar_min_count: 1,
            check_fingerprint: true, check_account_age: true, min_account_age_months: 3,
            check_cas: true, cas_action: "block",
            check_device: false, check_premium: false, check_language: false,
            check_osint: false, osint_action: "log"
        },
        strict: {
            check_ip: true, check_avatar: true, avatar_min_count: 1,
            check_fingerprint: true, check_account_age: true, min_account_age_months: 6,
            check_cas: true, cas_action: "block",
            check_device: true, check_premium: true, check_language: true,
            check_osint: false, osint_action: "log"
        },
        ultra: {
            check_ip: true, check_avatar: true, avatar_min_count: 2,
            check_fingerprint: true, check_account_age: true, min_account_age_months: 12,
            check_cas: true, cas_action: "block",
            check_device: true, check_premium: true, check_language: true,
            check_osint: true, osint_action: "block"
        }
    };

    function applyPreset(presetName) {
        const preset = PRESETS[presetName];
        if (!preset) return;
        
        Object.keys(preset).forEach(key => {
            const el = document.getElementById(key);
            if (!el) return;
            if (el.type === "checkbox") {
                el.checked = preset[key];
            } else {
                el.value = preset[key];
            }
        });
    }

    function loadSettings(cid) {
        fetch(`/api/settings?chat_id=${cid}`)
            .then(res => res.json())
            .then(data => {
                document.getElementById("action").value = data.action || "decline";
                document.getElementById("guard-mode").checked = data.guard_mode !== false;
                document.getElementById("check-ip").checked = data.check_ip;
                document.getElementById("check-device").checked = data.check_device;
                document.getElementById("check-avatar").checked = data.check_avatar;
                document.getElementById("avatar-min-count").value = data.avatar_min_count ?? 1;
                document.getElementById("check-premium").checked = data.check_premium !== false;
                document.getElementById("check-language").checked = data.check_language !== false;
                document.getElementById("check-fingerprint").checked = data.check_fingerprint !== false;
                document.getElementById("check-account-age").checked = data.check_account_age !== false;
                document.getElementById("min-account-age-months").value = data.min_account_age_months ?? 3;
                document.getElementById("check-cas").checked = data.check_cas === true;
                document.getElementById("cas-action").value = data.cas_action || "block";
                document.getElementById("check-osint").checked = data.check_osint === true;
                document.getElementById("osint-action").value = data.osint_action || "log";
                document.getElementById("questions-count").value = data.questions_count ?? 1;
                document.getElementById("log-channel").value = data.log_channel || "";
                document.getElementById("contact-link").value = data.contact_link || "";
                document.getElementById("decline-msg-captcha").value = data.decline_msg_captcha || "";
                document.getElementById("decline-msg-twink").value = data.decline_msg_twink || "";

                // Load language checkboxes
                const logLangs = data.log_languages || [];
                document.querySelectorAll(".lang-cb").forEach(cb => {
                    cb.checked = logLangs.includes(cb.value);
                });
                customLanguages = logLangs.filter(l => !document.querySelector(`.lang-cb[value="${l}"]`));
                customLangContainer.innerHTML = "";
                customLanguages.forEach(l => renderCustomLangTag(l));

                questionsList.innerHTML = "";
                if (data.questions) {
                    data.questions.forEach(q => {
                        if (q.type === "emoji") {
                            renderEmojiQuestion(q.q, q.correct, (q.distractors || []).join(", "));
                        } else if (q.type === "choice") {
                            renderChoiceQuestion(q.q, (q.a || [])[0] || "", (q.choices || []).join(", "));
                        } else {
                            renderQuestion(q.q, (q.a || []).join(", "));
                        }
                    });
                }
            });
    }

    function renderQuestion(questionText = "", answersText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "text";
        item.innerHTML = `
            <div style="font-size:11px; color:#8f9cae; margin-bottom:6px;">📝 Текстове питання</div>
            <input type="text" placeholder="Запитання (наприклад, Чий Крим?)" class="q-text" value="${questionText}" required>
            <input type="text" placeholder="Варіанти відповідей через кому (наприклад, України, український)" class="q-ans" value="${answersText}" required>
            <button type="button" class="btn-secondary remove-btn" style="background:#ff4a4a; padding:6px 12px; font-size:12px;">Видалити</button>
        `;
        item.querySelector(".remove-btn").addEventListener("click", () => item.remove());
        questionsList.appendChild(item);
    }

    function renderChoiceQuestion(questionText = "", answersText = "", choicesText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "choice";
        item.innerHTML = `
            <div style="font-size:11px; color:#8f9cae; margin-bottom:6px;">📋 Питання з вибором</div>
            <input type="text" placeholder="Запитання (наприклад, Чий Крим?)" class="q-text" value="${questionText}" required>
            <input type="text" placeholder="Правильна відповідь (наприклад, Україна)" class="q-ans" value="${answersText}" required>
            <input type="text" placeholder="Варіанти вибору через кому (наприклад, Україна, Росія, Нічий, Спірний)" class="q-choices" value="${choicesText}" required>
            <button type="button" class="btn-secondary remove-btn" style="background:#ff4a4a; padding:6px 12px; font-size:12px;">Видалити</button>
        `;
        item.querySelector(".remove-btn").addEventListener("click", () => item.remove());
        questionsList.appendChild(item);
    }

    function renderEmojiQuestion(questionText = "", correctEmoji = "", distractorsText = "") {
        const item = document.createElement("div");
        item.className = "question-item";
        item.dataset.type = "emoji";
        item.innerHTML = `
            <div style="font-size:11px; color:#8f9cae; margin-bottom:6px;">🎯 Emoji питання</div>
            <input type="text" placeholder="Текст питання (наприклад, Де паляниця?)" class="q-text" value="${questionText}" required>
            <input type="text" placeholder="Правильне емодзі (наприклад, 🫓)" class="q-correct" value="${correctEmoji}" required style="width:100%; margin-bottom:8px; box-sizing:border-box;">
            <input type="text" placeholder="Відволікаючі емодзі через кому (наприклад, 🍓, 🍓, 🍓, 🍓, 🍓)" class="q-distractors" value="${distractorsText}" required>
            <button type="button" class="btn-secondary remove-btn" style="background:#ff4a4a; padding:6px 12px; font-size:12px;">Видалити</button>
        `;
        item.querySelector(".remove-btn").addEventListener("click", () => item.remove());
        questionsList.appendChild(item);
    }

    const presetSelect = document.getElementById("preset");
    let currentPreset = "balanced";
    
    presetSelect.addEventListener("change", () => {
        currentPreset = presetSelect.value;
        applyPreset(presetSelect.value);
    });
    
    // Track manual changes and switch to custom preset
    const trackedInputs = [
        "action", "guard-mode", "check-ip", "check-device", "check-avatar",
        "avatar-min-count", "check-premium", "check-language", "check-fingerprint",
        "check-account-age", "min-account-age-months", "check-cas", "cas-action",
        "check-osint", "osint-action", "questions-count"
    ];
    
    trackedInputs.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        
        el.addEventListener("change", () => {
            if (currentPreset !== "custom") {
                currentPreset = "custom";
                presetSelect.value = "custom";
            }
        });
        
        el.addEventListener("input", () => {
            if (currentPreset !== "custom") {
                currentPreset = "custom";
                presetSelect.value = "custom";
            }
        });
    });

    addQuestionBtn.addEventListener("click", () => renderQuestion());
    document.getElementById("add-choice-question").addEventListener("click", () => renderChoiceQuestion());
    document.getElementById("add-emoji-question").addEventListener("click", () => renderEmojiQuestion());

    form.addEventListener("submit", (e) => {
        e.preventDefault();

        const questions = [];
        const items = questionsList.querySelectorAll(".question-item");
        items.forEach(item => {
            const q = item.querySelector(".q-text").value.trim();
            if (item.dataset.type === "emoji") {
                const correct = item.querySelector(".q-correct").value.trim();
                const distractors = item.querySelector(".q-distractors").value
                    .split(",").map(s => s.trim()).filter(Boolean);
                if (q && correct) questions.push({ type: "emoji", q, correct, distractors });
            } else if (item.dataset.type === "choice") {
                const a = item.querySelector(".q-ans").value.trim();
                const choices = item.querySelector(".q-choices").value
                    .split(",").map(s => s.trim()).filter(Boolean);
                if (q && a && choices.length >= 2) questions.push({ type: "choice", q, a: [a], choices });
            } else {
                const a = item.querySelector(".q-ans").value.split(",").map(s => s.trim()).filter(Boolean);
                if (q && a.length > 0) questions.push({ q, a });
            }
        });

        const settings = {
            action: document.getElementById("action").value,
            guard_mode: document.getElementById("guard-mode").checked,
            check_ip: document.getElementById("check-ip").checked,
            check_device: document.getElementById("check-device").checked,
            check_avatar: document.getElementById("check-avatar").checked,
            avatar_min_count: parseInt(document.getElementById("avatar-min-count").value, 10),
            check_premium: document.getElementById("check-premium").checked,
            check_language: document.getElementById("check-language").checked,
            log_languages: getLogLanguages(),
            check_fingerprint: document.getElementById("check-fingerprint").checked,
            check_account_age: document.getElementById("check-account-age").checked,
            min_account_age_months: parseInt(document.getElementById("min-account-age-months").value, 10),
            check_cas: document.getElementById("check-cas").checked,
            cas_action: document.getElementById("cas-action").value,
            check_osint: document.getElementById("check-osint").checked,
            osint_action: document.getElementById("osint-action").value,
            questions_count: parseInt(document.getElementById("questions-count").value, 10),
            log_channel: document.getElementById("log-channel").value.trim(),
            contact_link: document.getElementById("contact-link").value.trim(),
            decline_msg_captcha: document.getElementById("decline-msg-captcha").value.trim(),
            decline_msg_twink: document.getElementById("decline-msg-twink").value.trim(),
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