const startButton = document.querySelector("#breath-start");
const resetButton = document.querySelector("#breath-reset");
const visual = document.querySelector("#breath-visual");
const phaseLabel = document.querySelector("#breath-phase");
const countdownLabel = document.querySelector("#breath-countdown");
const progressLabel = document.querySelector("#breath-progress");
const announcement = document.querySelector("#breath-announcement");

const phases = [
  { label: "Breathe in", className: "inhale" },
  { label: "Hold gently", className: "hold-in" },
  { label: "Breathe out", className: "exhale" },
  { label: "Pause", className: "hold-out" },
];
const secondsPerPhase = 4;
const totalRounds = 4;
let phaseIndex = 0;
let round = 1;
let deadline = 0;
let remaining = secondsPerPhase;
let timer = null;
let running = false;

function renderPhase(seconds = remaining) {
  const phase = phases[phaseIndex];
  phaseLabel.textContent = phase.label;
  countdownLabel.textContent = String(Math.max(1, Math.ceil(seconds)));
  announcement.textContent = `${phase.label}. ${Math.max(1, Math.ceil(seconds))} seconds. Round ${round} of ${totalRounds}.`;
  progressLabel.textContent = `Round ${round} of ${totalRounds} · ${phaseIndex + 1} of 4`;
  visual.dataset.phase = phase.className;
}

function finishBreathing() {
  clearInterval(timer);
  timer = null;
  running = false;
  phaseLabel.textContent = "Well done";
  countdownLabel.textContent = "♡";
  announcement.textContent = "Breathing practice complete. Take a moment before you move on.";
  progressLabel.textContent = "Four gentle rounds complete";
  visual.dataset.phase = "complete";
  startButton.textContent = "Practice again";
  resetButton.disabled = false;
  phaseIndex = 0;
  round = 1;
  remaining = secondsPerPhase;
}

function advancePhase() {
  phaseIndex += 1;
  if (phaseIndex === phases.length) {
    phaseIndex = 0;
    round += 1;
    if (round > totalRounds) {
      finishBreathing();
      return;
    }
  }
  remaining = secondsPerPhase;
  deadline = Date.now() + remaining * 1000;
  renderPhase();
}

function tick() {
  remaining = Math.max(0, (deadline - Date.now()) / 1000);
  if (remaining <= 0) {
    advancePhase();
    return;
  }
  countdownLabel.textContent = String(Math.ceil(remaining));
}

function start() {
  if (running) {
    clearInterval(timer);
    timer = null;
    running = false;
    remaining = Math.max(0.1, (deadline - Date.now()) / 1000);
    phaseLabel.textContent = "Paused";
    announcement.textContent = `Paused. ${phases[phaseIndex].label} when you are ready.`;
    visual.dataset.phase = "paused";
    startButton.textContent = "Continue";
    resetButton.disabled = false;
    return;
  }

  running = true;
  deadline = Date.now() + remaining * 1000;
  renderPhase();
  startButton.textContent = "Pause";
  resetButton.disabled = false;
  timer = window.setInterval(tick, 100);
}

function reset() {
  clearInterval(timer);
  timer = null;
  running = false;
  phaseIndex = 0;
  round = 1;
  remaining = secondsPerPhase;
  phaseLabel.textContent = "Ready when you are";
  countdownLabel.textContent = String(secondsPerPhase);
  progressLabel.textContent = "4 rounds · 16 seconds each";
  announcement.textContent = "Ready when you are";
  visual.dataset.phase = "ready";
  startButton.textContent = "Begin breathing";
  resetButton.disabled = true;
}

startButton.addEventListener("click", start);
resetButton.addEventListener("click", reset);
