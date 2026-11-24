// AdaptiveDesk front end: renders whatever the adaptation engine returns
// and reports every interaction back so the model keeps learning.
const $ = (id) => document.getElementById(id);
let state = null;
let openedAt = 0;
let openTool = null;

const user = () => $("user").value.trim() || "guest";

async function api(path, body) {
  const opts = body ? { method: "POST", headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ user: user(), ...body }) } : {};
  const res = await fetch(path, opts);
  return res.json();
}

async function refresh() {
  state = await api(`/api/ui?user=${encodeURIComponent(user())}`);
  render();
}

function render() {
  const expert = state.expertise.level === "expert";
  document.body.classList.toggle("expert", expert);
  $("mode").textContent = state.expertise.level;
  $("mode").className = "badge " + state.expertise.level;
  $("freeze").textContent = state.frozen ? "Resume adaptation" : "Pause adaptation";

  const pred = state.prediction;
  $("grid").innerHTML = "";
  state.layout.forEach((t, i) => {
    const el = document.createElement("div");
    el.className = "tile" + (i === 0 && t.score > 0 ? " rank1" : "") +
                   (pred && pred.tool === t.id ? " predicted" : "");
    el.innerHTML = `<div class="icon">${t.icon}</div><div><div class="name">${t.name}</div>
      <div class="help">${t.help}</div></div><span class="key">${t.key}</span>
      <span class="score">${t.score ? "score " + t.score : ""}</span>`;
    el.onclick = () => open(t);
    $("grid").appendChild(el);
  });

  if (pred) {
    const t = state.layout.find((x) => x.id === pred.tool);
    $("suggest-name").textContent = `${t.icon} ${t.name}`;
    $("suggest-conf").textContent = `(${Math.round(pred.confidence * 100)}% confidence)`;
    $("suggest-open").onclick = () => open(t);
    $("suggest").classList.remove("hidden");
  } else {
    $("suggest").classList.add("hidden");
  }

  $("why").innerHTML = state.explanations.map((e) => `<li>${e}</li>`).join("");
  $("meta").textContent = `${state.event_count} interactions logged for "${user()}".`;
}

async function open(t) {
  openTool = t.id;
  openedAt = Date.now();
  await api("/api/event", { tool: t.id });
  $("panel-title").textContent = `${t.icon} ${t.name}`;
  $("panel-body").textContent = `${t.help} (Demo panel - in a real product this would be the ${t.name} tool.)`;
  ["grid", "suggest"].forEach((id) => $(id).classList.add("hidden"));
  $("panel").classList.remove("hidden");
}

async function back() {
  if (Date.now() - openedAt < 1500 && openTool) {
    await api("/api/event", { tool: openTool, undo: true });   // mis-selection
  }
  openTool = null;
  $("panel").classList.add("hidden");
  $("grid").classList.remove("hidden");
  refresh();
}

$("back").onclick = back;
$("freeze").onclick = async () => { await api("/api/freeze", { frozen: !state.frozen }); refresh(); };
$("reset").onclick = async () => { await api("/api/reset", {}); refresh(); };
$("user").onchange = refresh;

// Keyboard shortcuts (shown to expert users)
document.addEventListener("keydown", (e) => {
  if (e.target.tagName === "INPUT" || !state) return;
  if (e.key === "Escape") return back();
  const t = state.layout.find((x) => x.key.toLowerCase() === e.key.toLowerCase());
  if (t && $("panel").classList.contains("hidden")) open(t);
});

refresh();
