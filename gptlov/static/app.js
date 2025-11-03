const form = document.getElementById("gptlov-form");
const textarea = document.getElementById("question");
const statusLine = document.getElementById("status");
const results = document.getElementById("results");
const answerBlock = document.getElementById("answer");
const sourcesContainer = document.getElementById("sources");
const suggestions = document.querySelectorAll("[data-question]");
const progressBar = document.getElementById("progress-bar");
const progressContainer = progressBar ? progressBar.parentElement : null;

const BASELINE_DURATION_MS = 4500;
const MIN_EXPECTED_MS = 1200;
const MAX_HISTORY = 12;
const durationSamples = [];
let progressHideTimeout = null;

const formatSeconds = (ms) => (ms / 1000).toFixed(1);

const estimateDuration = () => 70000;

const recordDuration = (duration) => {
  if (!Number.isFinite(duration) || duration <= 0) {
    return;
  }
  durationSamples.push(duration);
  if (durationSamples.length > MAX_HISTORY) {
    durationSamples.shift();
  }
};

const startProgress = (expectedMs) => {
  if (!progressBar || !progressContainer) {
    return;
  }
  if (progressHideTimeout) {
    clearTimeout(progressHideTimeout);
    progressHideTimeout = null;
  }
  const safeDuration = Math.max(expectedMs, MIN_EXPECTED_MS);
  progressContainer.classList.add("visible");
  progressBar.style.transition = "none";
  progressBar.style.width = "0%";
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      progressBar.style.transition = `width ${safeDuration}ms linear`;
      progressBar.style.width = "100%";
    });
  });
};

const stopProgress = () => {
  if (!progressBar || !progressContainer) {
    return;
  }
  progressBar.style.transition = "width 220ms ease-out";
  progressBar.style.width = "100%";
  progressHideTimeout = window.setTimeout(() => {
    progressContainer.classList.remove("visible");
    progressBar.style.transition = "none";
    progressBar.style.width = "0%";
  }, 260);
};

const renderSources = (sources) => {
  sourcesContainer.innerHTML = "";

  if (!sources.length) {
    const fallback = document.createElement("p");
    fallback.textContent = "Ingen kilder ble funnet for dette svaret.";
    fallback.className = "source-ref";
    sourcesContainer.appendChild(fallback);
    return;
  }

  for (const entry of sources) {
    const card = document.createElement("article");
    card.className = "source";

    const title = document.createElement("div");
    title.className = "source-title";
    title.textContent = entry.title || "Kilde uten tittel";

    const ref = document.createElement("div");
    ref.className = "source-ref";
    ref.textContent = entry.refid || entry.source_path || "Ukjent referanse";

    const score = document.createElement("div");
    score.className = "source-score";
    score.textContent = `Relevans: ${(entry.score * 100).toFixed(1)}%`;

    const content = document.createElement("p");
    content.className = "source-ref";
    content.textContent = entry.content.slice(0, 220) + (entry.content.length > 220 ? "…" : "");

    card.appendChild(title);
    card.appendChild(ref);
    card.appendChild(score);
    card.appendChild(content);
    sourcesContainer.appendChild(card);
  }
};

const setLoading = (isLoading) => {
  if (isLoading) {
    form.querySelector("button").disabled = true;
    statusLine.textContent = "Tenker hardt på lovverket…";
  } else {
    form.querySelector("button").disabled = false;
  }
};

const handleSubmit = async (event) => {
  event.preventDefault();
  const question = textarea.value.trim();

  if (!question) {
    statusLine.textContent = "Skriv inn et spørsmål, så hjelper jeg deg.";
    return;
  }

  setLoading(true);
  results.classList.remove("visible");
  answerBlock.innerHTML = "";
  sourcesContainer.innerHTML = "";

  const expectedMs = estimateDuration();
  statusLine.textContent = `Forventer svar om cirka ${formatSeconds(expectedMs)} sekunder…`;
  startProgress(expectedMs);
  const startedAt = performance.now();
  let recordedDuration = false;

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });

    if (!response.ok) {
      throw new Error(`Tjenesten svarte med ${response.status}`);
    }

    const payload = await response.json();
    if (payload.answer_html) {
      answerBlock.innerHTML = payload.answer_html;
    } else {
      answerBlock.textContent = payload.answer || "Jeg klarte ikke å finne et svar denne gangen.";
    }
    renderSources(payload.sources || []);
    results.classList.add("visible");
    const durationMs = performance.now() - startedAt;
    recordDuration(durationMs);
    recordedDuration = true;
    const averageMs = estimateDuration();
    statusLine.textContent = `Her er svaret ditt (tok ${formatSeconds(durationMs)} s, gjennomsnitt ${formatSeconds(
      averageMs,
    )} s).`;
  } catch (error) {
    console.error(error);
    const durationMs = performance.now() - startedAt;
    if (!recordedDuration) {
      recordDuration(durationMs);
      recordedDuration = true;
    }
    statusLine.textContent =
      "Beklager! Noe gikk galt. Vennligst prøv igjen senere eller kontakt oss hvis problemet vedvarer.";
  } finally {
    stopProgress();
    setLoading(false);
  }
};

form.addEventListener("submit", handleSubmit);

suggestions.forEach((chip) => {
  chip.addEventListener("click", () => {
    textarea.value = chip.dataset.question;
    textarea.focus();
  });
});
