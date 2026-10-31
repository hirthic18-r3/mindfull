const conversation = document.querySelector("#conversation");
const chatForm = document.querySelector("#chat-form");
const messageInput = document.querySelector("#message-input");
const sendButton = document.querySelector(".send-button");
const chatHistory = [];

function addMessage(role, text, typing = false) {
  const message = document.createElement("div");
  message.className = `message ${role === "user" ? "user-message" : "assistant-message"}${typing ? " typing" : ""}`;

  if (role !== "user") {
    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "☼";
    message.append(avatar);
  }

  const content = document.createElement("div");
  content.className = "message-content";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  content.append(paragraph);
  if (!typing) {
    const time = document.createElement("time");
    time.textContent = "Just now";
    content.append(time);
  }
  message.append(content);
  conversation.append(message);
  conversation.scrollTop = conversation.scrollHeight;
  return message;
}

async function submitMessage(text) {
  const cleanText = text.trim();
  if (!cleanText || sendButton.disabled) return;

  addMessage("user", cleanText);
  chatHistory.push({ role: "user", text: cleanText });
  messageInput.value = "";
  messageInput.style.height = "auto";
  sendButton.disabled = true;
  const typing = addMessage("assistant", "Taking a moment to listen…", true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatHistory.slice(-12) }),
    });
    const data = await response.json();
    typing.remove();
    if (!response.ok) {
      addMessage("assistant", data.error || "Something went wrong. Please try again.");
      return;
    }
    addMessage("assistant", data.reply);
    chatHistory.push({ role: "assistant", text: data.reply });
  } catch {
    typing.remove();
    addMessage("assistant", "I couldn’t connect just now. Please check your connection and try again.");
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitMessage(messageInput.value);
});

messageInput.addEventListener("input", () => {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 100)}px`;
});

document.querySelectorAll(".suggestion").forEach((button) => {
  button.addEventListener("click", () => submitMessage(button.textContent));
});

let selectedMood = null;
const consentCheckbox = document.querySelector("#save-consent");
const saveButton = document.querySelector("#save-checkin");
const checkinStatus = document.querySelector("#checkin-status");

document.querySelectorAll(".mood-option").forEach((button) => {
  button.addEventListener("click", () => {
    selectedMood = button.dataset.mood;
    document.querySelectorAll(".mood-option").forEach((option) => {
      option.classList.toggle("selected", option === button);
      option.setAttribute("aria-pressed", String(option === button));
    });
    saveButton.disabled = !consentCheckbox.checked;
    checkinStatus.textContent = "";
  });
});

consentCheckbox.addEventListener("change", () => {
  saveButton.disabled = !selectedMood || !consentCheckbox.checked;
});

saveButton.addEventListener("click", async () => {
  if (!selectedMood || !consentCheckbox.checked) return;
  saveButton.disabled = true;
  checkinStatus.textContent = "Saving…";
  try {
    const response = await fetch("/api/checkins", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mood: selectedMood, consent: true }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not save your check-in.");
    checkinStatus.textContent = "Saved. Thanks for checking in with yourself.";
    consentCheckbox.checked = false;
    selectedMood = null;
    document.querySelectorAll(".mood-option").forEach((option) => {
      option.classList.remove("selected");
      option.setAttribute("aria-pressed", "false");
    });
  } catch (error) {
    checkinStatus.textContent = error.message || "Could not save your check-in. Please try again.";
  } finally {
    saveButton.disabled = !selectedMood || !consentCheckbox.checked;
  }
});

document.querySelector("#delete-checkins").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  try {
    const response = await fetch("/api/checkins", { method: "DELETE" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not delete saved check-ins.");
    checkinStatus.textContent = data.deleted
      ? "Your saved check-ins have been deleted."
      : "There are no saved check-ins in this browser.";
  } catch (error) {
    checkinStatus.textContent = error.message || "Could not delete saved check-ins. Please try again.";
  } finally {
    button.disabled = false;
  }
});
