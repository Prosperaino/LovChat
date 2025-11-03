const form = document.getElementById("gptlov-form");
const textarea = document.getElementById("question");
const statusLine = document.getElementById("status");
const results = document.getElementById("results");
const answerBlock = document.getElementById("answer");
const sourcesContainer = document.getElementById("sources");
const suggestions = document.querySelectorAll("[data-question]");

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
  answerBlock.textContent = "";
  sourcesContainer.innerHTML = "";

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
    answerBlock.textContent = payload.answer || "Jeg klarte ikke å finne et svar denne gangen.";
    renderSources(payload.sources || []);
    results.classList.add("visible");
    statusLine.textContent = "Her er svaret ditt:";
  } catch (error) {
    console.error(error);
    statusLine.textContent =
      "Beklager! Noe gikk galt. Vennligst prøv igjen senere eller kontakt oss hvis problemet vedvarer.";
  } finally {
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
