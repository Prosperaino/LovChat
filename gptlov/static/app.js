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

const maybeParseJson = (value) => {
  if (typeof value !== "string") {
    return value;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return "";
  }
  const firstChar = trimmed[0];
  const jsonLike =
    firstChar === "{" ||
    firstChar === "[" ||
    firstChar === '"' ||
    firstChar === "-" ||
    (firstChar >= "0" && firstChar <= "9");
  if (!jsonLike && trimmed !== "true" && trimmed !== "false" && trimmed !== "null") {
    return trimmed;
  }
  try {
    return JSON.parse(trimmed);
  } catch (_error) {
    return trimmed;
  }
};

const parseSseEvent = (rawEvent) => {
  const event = {
    type: "",
    data: "",
  };
  const lines = rawEvent.split("\n");
  const dataLines = [];

  for (const line of lines) {
    if (!line || line.startsWith(":")) {
      continue;
    }
    const separatorIndex = line.indexOf(":");
    if (separatorIndex === -1) {
      continue;
    }
    const field = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trimStart();
    if (field === "event") {
      event.type = value;
    } else if (field === "data") {
      dataLines.push(value);
    }
  }

  event.data = dataLines.join("\n");
  return event;
};

const formatSeconds = (ms) => (ms / 1000).toFixed(1);

const estimateDuration = () => 70000;

const escapeHtml = (text) =>
  text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");

const createExcerptHtml = (content) => {
  if (!content) {
    return "<p>Ingen utdrag tilgjengelig.</p>";
  }
  const trimmed = content.trim();
  if (!trimmed) {
    return "<p>Ingen utdrag tilgjengelig.</p>";
  }

  const lines = trimmed.split(/\r?\n+/).map((line) => line.trim());
  const paragraphs = [];
  let totalLength = 0;

  for (const line of lines) {
    if (!line) {
      continue;
    }
    paragraphs.push(line);
    totalLength += line.length;
    if (paragraphs.length >= 3 || totalLength >= 600) {
      break;
    }
  }

  return paragraphs
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join("");
};

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
    const scoreValue = Number(entry.score);
    if (Number.isFinite(scoreValue)) {
      score.textContent = `Relevans: ${(scoreValue * 100).toFixed(1)}%`;
    } else {
      score.textContent = "Relevans: ukjent";
    }

    const content = document.createElement("div");
    content.className = "source-excerpt";

    card.appendChild(title);
    card.appendChild(ref);
    card.appendChild(score);
    content.innerHTML = createExcerptHtml(entry.content);
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

const streamQuestion = async (question) => {
  const response = await fetch("ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error(`Tjenesten svarte med ${response.status}`);
  }

  if (!response.body) {
    throw new Error("Nettleseren støtter ikke strømming av svar.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let doneReceived = false;
  let answerPlainText = "";
  let hasShownResults = false;

  const showResults = () => {
    if (!hasShownResults) {
      results.classList.add("visible");
      hasShownResults = true;
    }
  };

  const handleEvent = (rawEvent) => {
    if (!rawEvent) {
      return;
    }
    const parsed = parseSseEvent(rawEvent);
    if (!parsed.type) {
      return;
    }

    const payload = maybeParseJson(parsed.data);
    if (parsed.type === "status") {
      if (typeof payload === "string") {
        statusLine.textContent = payload;
      } else if (payload && typeof payload.message === "string") {
        statusLine.textContent = payload.message;
      }
    } else if (parsed.type === "contexts") {
      const contextList = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.contexts)
          ? payload.contexts
          : [];
      renderSources(contextList);
      showResults();
    } else if (parsed.type === "chunk") {
      const chunk =
        typeof payload === "string"
          ? payload
          : payload && typeof payload.text === "string"
            ? payload.text
            : "";
      if (chunk) {
        answerPlainText += chunk;
        answerBlock.textContent = answerPlainText;
        showResults();
      }
    } else if (parsed.type === "answer_html") {
      const html =
        typeof payload === "string"
          ? payload
          : payload && typeof payload.html === "string"
            ? payload.html
            : "";
      if (html) {
        answerBlock.innerHTML = html;
        showResults();
      }
    } else if (parsed.type === "error") {
      const message =
        typeof payload === "string"
          ? payload
          : payload && typeof payload.message === "string"
            ? payload.message
            : "Ukjent feil fra tjenesten.";
      throw new Error(message);
    } else if (parsed.type === "done") {
      doneReceived = true;
    } else if (parsed.data) {
      // Fallback: vis ukjent hendelse som statusmelding
      if (typeof payload === "string") {
        statusLine.textContent = payload;
      }
    }
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      if (!value) {
        continue;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r/g, "");

      let separatorIndex = buffer.indexOf("\n\n");
      while (separatorIndex !== -1) {
        const rawEvent = buffer.slice(0, separatorIndex);
        buffer = buffer.slice(separatorIndex + 2);
        handleEvent(rawEvent);
        separatorIndex = buffer.indexOf("\n\n");
      }
    }

    const remaining = buffer.trim();
    if (remaining) {
      handleEvent(remaining);
    }
  } finally {
    reader.releaseLock();
  }

  if (!doneReceived) {
    throw new Error("Strømmen ble avbrutt før svaret var ferdig.");
  }

  if (!hasShownResults) {
    const hasContent = answerBlock.textContent.trim() || answerBlock.innerHTML.trim();
    if (hasContent) {
      results.classList.add("visible");
    }
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
    await streamQuestion(question);
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
