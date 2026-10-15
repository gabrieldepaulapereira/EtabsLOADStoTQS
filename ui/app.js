/* Pier Forces · ETABS → TQS — interface.
   Conversa com o Python pela ponte do pywebview (window.pywebview.api) e consulta poll()
   para receber log, progresso e o fim das tarefas do ETABS. */
"use strict";

const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nat = (a, b) => String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: "base" });
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const fmtNum = (v, d = 2) => v == null ? "—" : Number(v).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d });
const errMsg = e => (e && (e.message || e.toString())) || "Erro desconhecido";

const ICONS = {
  file: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  model: '<path d="M4 20h16"/><path d="M6 20V9"/><path d="M18 20V9"/><path d="M4 9h16"/><path d="M4 4h16"/><path d="M10 20v-6h4v6"/>',
  layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  pillars: '<path d="M6 4v16"/><path d="M12 4v16"/><path d="M18 4v5h-4"/><path d="M3 20h18"/><path d="M3 4h18"/>',
  ruler: '<path d="M4 20 20 4"/><path d="m7 17 2 2"/><path d="m10 14 2 2"/><path d="m13 11 2 2"/><path d="m16 8 2 2"/>',
  export: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
  check: '<path d="M5 12.5 10 17l9-10"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  alert: '<path d="M12 3 2 20h20z"/><path d="M12 10v4"/><path d="M12 17.5v.01"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 8v.01"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  terminal: '<path d="m5 8 4 4-4 4"/><path d="M12 16h7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  trash: '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>',
  right: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
  left: '<path d="M19 12H5"/><path d="m11 6-6 6 6 6"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
  up: '<path d="M12 19V5"/><path d="m6 11 6-6 6 6"/>',
  upload: '<path d="M12 21V9"/><path d="m7 14 5-5 5 5"/><path d="M5 3h14"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  dot: '<circle cx="12" cy="12" r="3" fill="currentColor"/>',
  minus: '<path d="M6 12h12"/>',
  plan: '<rect x="3" y="3" width="18" height="18" rx="2.5"/><path d="M8 7v10h8V7"/>',
};
const ic = (n, cls = "") => `<svg class="ic ${cls}" viewBox="0 0 24 24">${ICONS[n] || ""}</svg>`;
const CHECK = `<span class="check"><svg viewBox="0 0 24 24"><path d="M5 12.5 10 17l9-10"/></svg></span>`;

const STEPS = [
  { id: "modelo", t: "Modelo", title: "Modelo do ETABS",
    sub: "Escolha o arquivo .EDB analisado. O programa abre o modelo no ETABS e lê Piers, combinações e Stories." },
  { id: "combos", t: "Combinações", title: "Combinações de carga",
    sub: "Marque as combinações exportadas. As ULS-NBR-# já vêm marcadas, e a escolha fica salva para este modelo." },
  { id: "pilares", t: "Pilares", title: "Pilares",
    sub: "Cada Pier assinalado gera um CSV. Os pilares poligonais (faces P8A, P8B… → P8-1, P8-2…) geram também o pilar completo e o .txt de lances." },
  { id: "lances", t: "Lances TQS", title: "Lances do TQS",
    sub: "Informe o lance do TQS que cada Story do ETABS representa. Use exceções para pilares que nascem em outro lance." },
  { id: "exportar", t: "Exportar", title: "Exportar para a pasta ETB",
    sub: "Confira o resumo e gere os arquivos que o TQS lê." },
];

const STAGES = [
  { id: "conexao", nm: "Abrir o modelo no ETABS" },
  { id: "etapa1", nm: "Extrair os esforços (etapa 1)" },
  { id: "copia", nm: "Copiar o modelo para a pasta de trabalho", poly: true },
  { id: "reatribuicao", nm: "Reatribuir as faces ao pilar completo", poly: true },
  { id: "analise", nm: "Reanalisar a cópia", poly: true, optional: true },
  { id: "etapa2", nm: "Extrair os pilares completos (etapa 2)", poly: true },
  { id: "gravacao", nm: "Gravar a pasta ETB" },
];

const S = {
  api: null, boot: null, step: "modelo",
  card: null, model: null, reading: false, readT0: 0,
  combos: new Set(), excluded: new Set(), full: true,
  mapping: { general: {}, exceptions: [] },
  search: "", onlySel: false, focusStory: null, highlight: "",
  exporting: false, stages: {}, current: null, result: null, failed: false,
  logs: [], logOpen: false, warns: 0, errs: 0,
  apiState: { state: "wait", l1: "Conectando à API…", l2: "ETABS" },
};

/* ------------------------------------------------------------------ dados derivados */
const groups = () => (S.model ? S.model.groups : []);
const pierInfo = p => (S.model && S.model.piers.find(q => q.name === p)) || null;
const groupOf = p => { const x = pierInfo(p); return x ? x.group : null; };
const outOf = p => { const x = pierInfo(p); return x && x.out ? x.out : p; };   // P8A -> P8-1
const storyIndex = () => new Map((S.model ? S.model.stories : []).map((s, i) => [s.name, i]));

function isExcluded(p) {
  const g = groupOf(p);
  return S.excluded.has(p) || (g && S.excluded.has(g));
}
function selectedPiers() {
  if (!S.model) return [];
  return S.model.piers.filter(p => p.has_objects && !isExcluded(p.name));
}
function mapStory(pier, story) {
  const ex = S.mapping.exceptions;
  const hit = k => ex.find(e => e.pier === k && e.story === story && String(e.lance).trim() !== "");
  // exceção da face (nome do ETABS ou gravado) > exceção do pilar > geral
  for (const k of [pier, outOf(pier), groupOf(pier)]) {
    const e = k && hit(k);
    if (e) return { v: String(e.lance).trim(), exc: true };
  }
  const g = S.mapping.general[story];
  return g != null && String(g).trim() !== "" ? { v: String(g).trim(), exc: false } : null;
}
function missing() {
  const out = new Map();
  for (const p of selectedPiers())
    for (const s of p.stories)
      if (!mapStory(p.name, s)) { if (!out.has(s)) out.set(s, []); out.get(s).push(p.name); }
  return out;
}
function storyUse() {
  const use = new Map();
  for (const p of selectedPiers()) for (const s of p.stories) use.set(s, (use.get(s) || 0) + 1);
  return use;
}
function outputCounts() {
  const sel = selectedPiers();
  const gs = groups().filter(g => !S.excluded.has(g.base));
  const extra = S.full ? gs.length : 0;
  return { csv: sel.length + extra, txt: extra, groups: gs.length };
}
function stepState(id) {
  const m = !!S.model;
  switch (id) {
    case "modelo": return { done: m, sub: S.card ? S.card.name : "Selecionar .EDB" };
    case "combos": return { locked: !m, done: m && S.combos.size > 0, sub: m ? `${S.combos.size} selecionadas` : "—" };
    case "pilares": {
      if (!m) return { locked: true, sub: "—" };
      const n = selectedPiers().length, g = outputCounts().groups;
      return { done: n > 0, sub: `${n} Piers · ${plural(g, "poligonal", "poligonais")}` };
    }
    case "lances": {
      if (!m) return { locked: true, sub: "—" };
      const k = missing().size;
      return { done: k === 0, warn: k > 0, sub: k ? `faltam ${plural(k, "Story", "Stories")}` : "completo" };
    }
    case "exportar":
      return { locked: !m, done: !!S.result, sub: S.exporting ? "exportando…" : S.result ? "concluído" : "—" };
  }
  return {};
}

/* ------------------------------------------------------------------ casca */
function renderRail() {
  $("#steps").innerHTML = STEPS.map((st, i) => {
    const s = stepState(st.id);
    const cls = [st.id === S.step ? "on" : "", s.done && st.id !== S.step ? "done" : "", s.warn && st.id !== S.step ? "warn" : "", s.locked ? "locked" : ""].join(" ");
    const n = s.done && st.id !== S.step ? ic("check") : s.warn && st.id !== S.step ? "!" : String(i + 1).padStart(2, "0");
    return `<li class="step ${cls}" data-step="${st.id}"><span class="n">${n}</span><span class="t">${st.t}</span><span class="s">${esc(s.sub)}</span></li>`;
  }).join("");
  const a = S.apiState;
  $("#apiStatus").innerHTML = `<span class="dot ${a.state}"></span><span class="l1">${esc(a.l1)}</span><span class="l2">${esc(a.l2)}</span>`;
  $("#apiStatus").title = a.title || "";
}
function renderTop() {
  const i = STEPS.findIndex(s => s.id === S.step), st = STEPS[i];
  $("#kicker").textContent = `Passo ${i + 1} de ${STEPS.length}`;
  $("#title").textContent = st.title;
  $("#subtitle").textContent = st.sub;
  $("#modelChip").innerHTML = S.card ? `<div class="model-chip" title="${esc(S.card.path)}">${ic("file")}<span class="nm">${esc(S.card.name)}</span>
      ${S.model ? '<span class="badge ok">lido</span>' : S.card.analyzed ? '<span class="badge info">analisado</span>' : '<span class="badge warn">sem resultados</span>'}</div>` : "";
}
function renderLogBtn() {
  const n = S.errs ? `<span class="n err">${S.errs}</span>` : S.warns ? `<span class="n warn">${S.warns}</span>` : `<span class="n">${S.logs.length}</span>`;
  $("#logBtn").innerHTML = `${ic("terminal")} Log ${n}`;
}
function render() {
  renderRail(); renderTop(); renderLogBtn();
  const views = { modelo: vModelo, combos: vCombos, pilares: vPilares, lances: vLances, exportar: vExportar };
  $("#content").innerHTML = `<div class="view">${views[S.step]()}</div>`;
  $("#content").scrollTop = 0;
  afterRender();
  renderActions();
}
function afterRender() {
  if (S.step === "combos") renderComboGrid();
  if (S.step === "lances") { renderExceptions(); refreshLances(); }
  if (S.step === "exportar") renderTimeline();
}
function go(step) {
  const st = stepState(step);
  if (st.locked) return;
  S.step = step; render();
}
function nextStep(d = 1) {
  const i = STEPS.findIndex(s => s.id === S.step);
  const j = Math.max(0, Math.min(STEPS.length - 1, i + d));
  go(STEPS[j].id);
}

function renderActions() {
  const A = [], hint = [];
  const back = `<button class="btn ghost" data-act="back">${ic("left")} Voltar</button>`;
  const next = (ok = true) => `<button class="btn primary" data-act="next" ${ok ? "" : "disabled"}>Continuar ${ic("right")}</button>`;
  switch (S.step) {
    case "modelo":
      if (!S.card) { A.push(`<button class="btn primary" data-act="pick">${ic("folder")} Procurar .EDB</button>`); hint.push("O modelo precisa estar analisado (arquivos .Y00 ao lado do .EDB)."); }
      else if (S.reading) { A.push(`<button class="btn primary" disabled><span class="spinner"></span> Lendo o modelo…</button>`); hint.push("O ETABS está abrindo o modelo. Isso pode levar alguns segundos."); }
      else if (!S.model) { A.push(`<button class="btn" data-act="pick">${ic("folder")} Trocar arquivo</button>`, `<button class="btn primary" data-act="read">${ic("model")} Ler modelo no ETABS</button>`); hint.push("Abre o modelo no ETABS (sem alterá-lo) e lê Piers, combinações e Stories."); }
      else { A.push(`<button class="btn ghost" data-act="pick">${ic("folder")} Trocar</button>`, `<button class="btn" data-act="read">${ic("refresh")} Reler</button>`, next()); hint.push("Modelo lido. Revise as combinações."); }
      break;
    case "combos":
      A.push(back, next(S.combos.size > 0));
      hint.push(S.combos.size ? `${plural(S.combos.size, "combinação será exportada", "combinações serão exportadas")}.` : "Marque ao menos uma combinação.");
      break;
    case "pilares": {
      const c = outputCounts();
      A.push(back, next(selectedPiers().length > 0));
      hint.push(`Serão gerados ${plural(c.csv, "CSV", "CSV")}${c.txt ? ` e ${plural(c.txt, "TXT", "TXT")}` : ""}.`);
      break;
    }
    case "lances": {
      const k = missing().size;
      A.push(back, next(k === 0));
      hint.push(k ? `Preencha o lance de ${plural(k, "Story", "Stories")} destacado${k > 1 ? "s" : ""} em amarelo.` : "Todos os Stories usados têm lance do TQS.");
      break;
    }
    case "exportar":
      if (S.exporting) { A.push(`<button class="btn primary" disabled><span class="spinner"></span> Exportando…</button>`); hint.push("Não feche o ETABS aberto pelo programa."); }
      else if (S.result) { A.push(back, `<button class="btn" data-act="export">${ic("refresh")} Exportar novamente</button>`, `<button class="btn primary" data-act="openetb">${ic("folder")} Abrir pasta ETB</button>`); hint.push(`Arquivos gravados em ${S.result.out_dir}`); }
      else { A.push(back, `<button class="btn primary" data-act="export" ${readyToExport() ? "" : "disabled"}>${ic("export")} Exportar para ETB</button>`); hint.push(readyToExport() ? "Tudo pronto." : "Há pendências no resumo."); }
      break;
  }
  $("#actions").innerHTML = A.join("");
  $("#hint").textContent = hint.join(" ");
}

/* ------------------------------------------------------------------ passo 1 · modelo */
const HERO_ART = `<svg class="hero-art" viewBox="0 0 230 150" aria-hidden="true">
  ${[0, 1, 2, 3, 4, 5].map(i => `<rect x="8" y="${14 + i * 22}" width="120" height="3" rx="1.5" style="fill:var(--concrete-edge);opacity:.55"/>`).join("")}
  <rect x="20" y="14" width="7" height="113" rx="1" style="fill:var(--concrete-edge);opacity:.45"/>
  <rect x="58" y="14" width="7" height="113" rx="1" style="fill:var(--concrete-edge);opacity:.45"/>
  <path d="M92 14v113M92 127h24M116 127V14" style="stroke:var(--accent);stroke-width:7;fill:none;stroke-linecap:square"/>
  <path d="M92 14v113M92 127h24M116 127V14" style="stroke:var(--accent);stroke-width:18;fill:none;opacity:.12"/>
  <path d="M138 70h24" style="stroke:var(--muted);stroke-width:2;stroke-dasharray:3 4"/><path d="m158 64 7 6-7 6" style="stroke:var(--muted);stroke-width:2;fill:none"/>
  <g transform="translate(174 30)">
    <rect width="46" height="58" rx="6" style="fill:var(--surface);stroke:var(--border2)"/>
    <rect x="9" y="12" width="28" height="3" rx="1.5" style="fill:var(--muted);opacity:.6"/><rect x="9" y="20" width="22" height="3" rx="1.5" style="fill:var(--muted);opacity:.4"/>
    <rect x="9" y="28" width="26" height="3" rx="1.5" style="fill:var(--muted);opacity:.4"/>
    <text x="23" y="49" text-anchor="middle" style="font:700 11px Barlow;fill:var(--accent);letter-spacing:.08em">CSV</text>
  </g>
  <g transform="translate(186 96)">
    <rect width="38" height="42" rx="6" style="fill:var(--surface);stroke:var(--border2)"/>
    <text x="19" y="27" text-anchor="middle" style="font:700 10px Barlow;fill:var(--warn);letter-spacing:.08em">TXT</text>
  </g>
</svg>`;

function vModelo() {
  if (!S.card) {
    const rec = (S.boot && S.boot.recent) || [];
    return `<div class="hero">
      <div style="position:relative;z-index:1">
        <div class="kicker">ETABS → pasta ETB do TQS</div>
        <h2>Exporte os esforços dos pilares em poucos cliques</h2>
        <p>Lê as combinações ULS-NBR-# pela API do ETABS, monta os pilares poligonais completos numa cópia do modelo e grava os CSV e TXT no formato que o TQS lê.</p>
        <div class="cta"><button class="btn primary lg" data-act="pick">${ic("folder")} Selecionar modelo .EDB</button></div>
      </div>${HERO_ART}</div>
      ${rec.length ? `<div class="card recent"><div class="card-h"><span class="card-t">Modelos recentes</span></div>
        ${rec.map((r, i) => `<div class="recent-item" data-recent="${i}"><span class="fi">${ic("file")}</span>
          <div style="min-width:0"><div class="nm">${esc(r.name)}</div><div class="pt">${esc(r.folder)}</div></div>
          <span class="muted" style="font-size:12.5px">${esc(r.modified)}</span>
          ${r.analyzed ? '<span class="badge ok">analisado</span>' : '<span class="badge warn">sem resultados</span>'}</div>`).join("")}</div>` : ""}`;
  }
  const c = S.card;
  const tiles = `<div class="tiles" style="margin-top:16px">
      <div class="tile ${c.analyzed ? "ok" : "warn"}"><div class="lbl">Resultados</div><div class="val sm">${c.analyzed ? "Analisado" : "Sem .Y00"}</div><div class="sub">${c.analyzed ? "arquivos de análise encontrados" : "rode a análise no ETABS"}</div></div>
      <div class="tile"><div class="lbl">Tamanho</div><div class="val sm">${fmtNum(c.size_mb, 1)}<span class="unit">MB</span></div><div class="sub">modificado ${esc(c.modified)}</div></div>
      <div class="tile ${c.story_map ? "accent" : ""}"><div class="lbl">Lances TQS</div><div class="val sm">${c.story_map ? "story_map.csv" : "—"}</div><div class="sub">${c.story_map ? "será carregado" : "preencha no passo 4"}</div></div>
      <div class="tile"><div class="lbl">Pasta ETB</div><div class="val sm">${c.etb ? "Existe" : "Nova"}</div><div class="sub">${c.etb ? "a atual vira ETB_anterior_…" : "será criada"}</div></div>
    </div>`;
  let body = "";
  if (S.reading) {
    body = `<div class="reading" style="margin-top:16px"><span class="spinner"></span><div><div style="font-weight:600">Lendo o modelo no ETABS…</div>
      <div class="muted" style="font-size:13px" id="readTimer">abrindo o arquivo</div></div><div class="bar indet"><i></i></div></div>`;
  } else if (S.model) {
    const m = S.model, withObj = m.piers.filter(p => p.has_objects).length;
    body = `<div class="sep"></div><div class="tiles">
      <div class="tile accent"><div class="lbl">Piers com objetos</div><div class="val">${withObj}</div><div class="sub">de ${m.piers.length} Pier Labels</div></div>
      <div class="tile accent"><div class="lbl">Poligonais</div><div class="val">${m.groups.length}</div><div class="sub">${esc(m.groups.slice(0, 5).map(g => g.base).join(", "))}${m.groups.length > 5 ? "…" : ""}</div></div>
      <div class="tile"><div class="lbl">Combinações</div><div class="val">${m.combos.length}</div><div class="sub">${m.default_combos.length} pela regra padrão</div></div>
      <div class="tile"><div class="lbl">Stories</div><div class="val">${m.stories.length}</div><div class="sub">${esc(m.stories[m.stories.length - 1]?.name || "")} → ${esc(m.stories[0]?.name || "")}</div></div>
      <div class="tile"><div class="lbl">ETABS</div><div class="val sm">${esc(m.version)}</div><div class="sub">versão do programa</div></div>
    </div>
    <div class="insight ok" style="margin-top:14px">${ic("check")}<div><div class="tt">Modelo lido</div><div class="tx">Nada foi alterado no modelo. Continue para revisar as combinações.</div></div></div>`;
  }
  return `<div class="card"><div class="model-card"><span class="fi">${ic("model")}</span>
      <div style="min-width:0"><div class="nm">${esc(c.name)}</div><div class="pt sel">${esc(c.folder)}</div></div>
      <div>${c.analyzed ? '<span class="badge ok">analisado</span>' : '<span class="badge warn">sem resultados</span>'}</div></div>
      ${tiles}${body}</div>
      ${!c.analyzed && !S.model ? `<div class="insight warn" style="margin-top:14px">${ic("alert")}<div><div class="tt">Modelo sem resultados de análise</div><div class="tx">Não há arquivos .Y00/.Y ao lado do .EDB. Rode a análise no ETABS (F5), salve e volte aqui.</div></div></div>` : ""}`;
}

/* ------------------------------------------------------------------ passo 2 · combinações */
function vCombos() {
  const m = S.model;
  return `<div class="toolbar">
      <label class="search">${ic("search")}<input class="input" id="comboSearch" placeholder="Filtrar combinações…" value="${esc(S.search)}"></label>
      <button class="btn sm" data-act="combos-default" title="Regra: ${esc(m.default_rule)}">${ic("check")} Só ULS-NBR-#</button>
      <button class="btn sm" data-act="combos-all">Todas</button>
      <button class="btn sm" data-act="combos-none">Nenhuma</button>
      <label class="switch" style="margin-left:6px"><input type="checkbox" id="onlySel" ${S.onlySel ? "checked" : ""}><span class="track"></span><span class="muted" style="font-size:13px">Só marcadas</span></label>
      <div class="spacer"></div>
      <span class="pill" id="comboCount"></span>
    </div>
    <div class="combo-grid" id="comboGrid"></div>
    <div class="legend"><span><i></i>regra padrão (ULS-NBR-#)</span><span>Clique para marcar ou desmarcar.</span></div>`;
}
function renderComboGrid() {
  const m = S.model, def = new Set(m.default_combos), q = S.search.trim().toLowerCase();
  const list = m.combos.filter(c => (!q || c.toLowerCase().includes(q)) && (!S.onlySel || S.combos.has(c)));
  $("#comboGrid").innerHTML = list.length ? list.map(c => `<div class="combo ${S.combos.has(c) ? "on" : ""}" data-combo="${esc(c)}">${CHECK}<span class="nm">${esc(c)}</span>${def.has(c) ? '<span class="def" title="regra padrão"></span>' : ""}</div>`).join("")
    : `<div class="empty" style="grid-column:1/-1">${ic("search")}<div>Nenhuma combinação encontrada.</div></div>`;
  $("#comboCount").innerHTML = `<b>${S.combos.size}</b> de ${m.combos.length} selecionadas`;
}

/* ------------------------------------------------------------------ passo 3 · pilares */
function spanText(stories) {
  const idx = storyIndex(), ss = [...stories].sort((a, b) => (idx.get(b) ?? 0) - (idx.get(a) ?? 0));
  return ss.length ? `${ss[0]} → ${ss[ss.length - 1]}` : "—";
}
/* ------------------------------------------------------------------ geometria real dos pilares
   Cada face é um Pier do ETABS; PierLabel.GetSectionProperties dá, por Story, o ângulo do eixo
   local 2 (a partir do X global), a largura (ao longo do eixo 2), a espessura e o centro de
   gravidade na base do Story. Cada face vira um retângulo na planta. */
const FACE_COLORS = ["#3B82F6", "#2DBE7F", "#E0A526", "#E5484D", "#A78BFA", "#22D3EE", "#F472B6", "#8A94A8"];
const faceColor = i => FACE_COLORS[i % FACE_COLORS.length];

function pierSet(key) {
  // grupo poligonal (faces) ou Pier comum (uma "face" só)
  const g = S.model.groups.find(x => x.base === key);
  if (g) return { key, poly: true, faces: g.faces, outs: g.outs };
  return { key, poly: false, faces: [key], outs: [outOf(key)] };
}
function geomAt(p, story) {
  const x = pierInfo(p);
  return x && x.geom ? x.geom.find(g => g.story === story && g.width > 0) || null : null;
}
function hasGeometry(set) { return set.faces.some(f => (pierInfo(f)?.geom || []).some(g => g.width > 0)); }
function setStories(set) {
  const idx = storyIndex(), st = new Set();
  for (const f of set.faces) for (const g of pierInfo(f)?.geom || []) if (g.width > 0) st.add(g.story);
  return [...st].sort((a, b) => (idx.get(a) ?? 0) - (idx.get(b) ?? 0));      // de cima para baixo
}
function repStory(set) {
  // o Story com mais faces; no empate, o mais baixo
  let best = null, bestN = -1;
  for (const s of setStories(set)) {
    const n = set.faces.filter(f => geomAt(f, s)).length;
    if (n >= bestN) { best = s; bestN = n; }
  }
  return best;
}
function faceBoxes(set, story) {
  const out = [];
  set.faces.forEach((f, i) => {
    const g = geomAt(f, story);
    if (!g) return;
    const a = g.angle * Math.PI / 180, ux = Math.cos(a), uy = Math.sin(a);
    const hw = g.width / 2, ht = g.thick / 2;
    const pts = [[-hw, -ht], [hw, -ht], [hw, ht], [-hw, ht]].map(([p, q]) => [g.x + p * ux - q * uy, g.y + p * uy + q * ux]);
    out.push({ face: f, out: set.outs[i], i, g, ux, uy, pts });
  });
  return out;
}
function fitBoxes(boxes, W, H, pad) {
  const xs = boxes.flatMap(b => b.pts.map(p => p[0])), ys = boxes.flatMap(b => b.pts.map(p => p[1]));
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const k = Math.min((W - 2 * pad) / Math.max(x1 - x0, 1e-6), (H - 2 * pad) / Math.max(y1 - y0, 1e-6));
  const ox = (W - (x1 - x0) * k) / 2, oy = (H - (y1 - y0) * k) / 2;
  return { k, X: x => ox + (x - x0) * k, Y: y => oy + (y1 - y) * k };          // Y do ETABS para cima
}
function boxPath(b, T, minPx) {
  // retângulo em coordenadas de tela, com espessura mínima visível
  const cx = T.X(b.g.x), cy = T.Y(b.g.y), ux = b.ux, uy = -b.uy;               // eixo 2 na tela
  const hw = b.g.width * T.k / 2, ht = Math.max(b.g.thick * T.k, minPx) / 2;
  const P = [[-hw, -ht], [hw, -ht], [hw, ht], [-hw, ht]].map(([p, q]) => [cx + p * ux - q * uy, cy + p * uy + q * ux]);
  return { d: "M" + P.map(p => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("L") + "Z", cx, cy, ux, uy, ht, hw };
}
function meanderGlyph(n, on) {
  // sem geometria (ETABS antigo ou Pier sem dados): desenho esquemático com n faces
  const dirs = [[0, 1], [1, 0], [0, -1], [1, 0], [0, 1], [1, 0], [0, -1], [1, 0]];
  let x = 0, y = 0; const pts = [[0, 0]];
  for (let i = 0; i < n; i++) { const d = dirs[i % dirs.length]; x += d[0] * (d[0] ? 1 : 1.4); y += d[1] * 1.4; pts.push([x, y]); }
  const xs = pts.map(p => p[0]), ys = pts.map(p => p[1]);
  const w = Math.max(...xs) - Math.min(...xs) || 1, h = Math.max(...ys) - Math.min(...ys) || 1;
  const k = 30 / Math.max(w, h), ox = 22 - (Math.min(...xs) + w / 2) * k, oy = 22 - (Math.min(...ys) + h / 2) * k;
  const P = pts.map(p => [p[0] * k + ox, p[1] * k + oy]);
  return P.slice(1).map((p, i) => `<line x1="${P[i][0].toFixed(1)}" y1="${P[i][1].toFixed(1)}" x2="${p[0].toFixed(1)}" y2="${p[1].toFixed(1)}"
      style="stroke:var(--accent);stroke-width:5;stroke-linecap:square;opacity:${on ? 0.55 + 0.45 * ((i % 2) ? 0.6 : 1) : 0.3}"/>`).join("");
}
function pierGlyph(key, on = true, size = 44) {
  const set = pierSet(key);
  let body;
  if (hasGeometry(set)) {
    const boxes = faceBoxes(set, repStory(set));
    const T = fitBoxes(boxes, 44, 44, 6);
    body = boxes.map(b => `<path d="${boxPath(b, T, 3.2).d}" style="fill:${on ? faceColor(b.i) : "var(--faint)"};opacity:${on ? 0.95 : 0.5}"/>`).join("");
  } else body = meanderGlyph(set.faces.length, on);
  return `<svg class="sect" viewBox="0 0 44 44" style="width:${size}px;height:${size}px"><rect x="1" y="1" width="42" height="42" rx="7" style="fill:var(--bg);stroke:var(--border)"/>${body}</svg>`;
}

/* ------------------------------------------------------------------ pop-up da seção */
const niceStep = v => { const p = 10 ** Math.floor(Math.log10(v)), m = v / p; return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p; };
function planSVG(set, story) {
  const W = 660, H = 470, boxes = faceBoxes(set, story);
  if (!boxes.length) return `<div class="empty">${ic("info")}<div>Sem geometria neste Story.</div></div>`;
  const T = fitBoxes(boxes, W, H, 92), u = S.model.length_unit || "";
  // grade de referência (passo "redondo" em unidades do modelo)
  const step = niceStep(70 / T.k), gx = [], gy = [];
  const wx0 = (0 - T.X(0)) / T.k, wx1 = (W - T.X(0)) / T.k;                    // mundo visível em x
  for (let x = Math.ceil(wx0 / step) * step; x <= wx1; x += step) gx.push(T.X(x));
  const wy1 = (T.Y(0) - 0) / T.k, wy0 = (T.Y(0) - H) / T.k;
  for (let y = Math.ceil(wy0 / step) * step; y <= wy1; y += step) gy.push(T.Y(y));
  const grid = gx.map(x => `<line x1="${x.toFixed(1)}" y1="0" x2="${x.toFixed(1)}" y2="${H}"/>`).join("")
    + gy.map(y => `<line x1="0" y1="${y.toFixed(1)}" x2="${W}" y2="${y.toFixed(1)}"/>`).join("");
  // centro do conjunto: os rótulos saem para fora dele
  const gcx = boxes.reduce((a, b) => a + T.X(b.g.x), 0) / boxes.length, gcy = boxes.reduce((a, b) => a + T.Y(b.g.y), 0) / boxes.length;
  const shapes = [], labels = [];
  for (const b of boxes) {
    const P = boxPath(b, T, 4), c = faceColor(b.i);
    let nx = -P.uy, ny = P.ux;                                                // normal à face na tela
    if (boxes.length > 1 && (nx * (P.cx - gcx) + ny * (P.cy - gcy)) < 0) { nx = -nx; ny = -ny; }
    if (boxes.length === 1) { nx = 0; ny = -1; }
    const d0 = P.ht + 6, d1 = P.ht + 30;
    let lx = P.cx + nx * d1, ly = P.cy + ny * d1;
    const text = b.face === b.out ? b.face : `${b.face} → ${b.out}`;
    const tw = text.length * 7.2 + 18, th = 24;
    lx = Math.min(W - tw / 2 - 6, Math.max(tw / 2 + 6, lx)); ly = Math.min(H - th / 2 - 6, Math.max(th / 2 + 6, ly));
    shapes.push(`<g class="fp" data-face="${esc(b.face)}"><title>${esc(b.face)} → ${esc(b.out)}.csv · ${fmtNum(b.g.width)} × ${fmtNum(b.g.thick)} ${u} · ${fmtNum(b.g.angle, 1)}°</title>
      <path d="${P.d}" style="fill:${c};fill-opacity:.28;stroke:${c};stroke-width:1.6"/>
      <line x1="${(P.cx - P.ux * P.hw).toFixed(1)}" y1="${(P.cy - P.uy * P.hw).toFixed(1)}" x2="${(P.cx + P.ux * P.hw).toFixed(1)}" y2="${(P.cy + P.uy * P.hw).toFixed(1)}" style="stroke:${c};stroke-width:1;stroke-dasharray:5 4;opacity:.8"/></g>`);
    const fx = b.face.slice(0, set.poly ? set.key.length : b.face.length), sfx = set.poly ? b.face.slice(set.key.length) : "";
    labels.push(`<g class="fl" data-face="${esc(b.face)}">
      <line x1="${(P.cx + nx * d0).toFixed(1)}" y1="${(P.cy + ny * d0).toFixed(1)}" x2="${lx.toFixed(1)}" y2="${ly.toFixed(1)}" style="stroke:${c};stroke-width:1.2"/>
      <circle cx="${P.cx.toFixed(1)}" cy="${P.cy.toFixed(1)}" r="3" style="fill:${c}"/>
      <rect x="${(lx - tw / 2).toFixed(1)}" y="${(ly - th / 2).toFixed(1)}" width="${tw.toFixed(1)}" height="${th}" rx="6" style="fill:var(--surface2);stroke:${c};stroke-width:1.3"/>
      <text x="${lx.toFixed(1)}" y="${(ly + 4.5).toFixed(1)}" text-anchor="middle" style="font:600 13px Barlow,Segoe UI,sans-serif;fill:var(--text)">${esc(fx)}<tspan style="fill:${c};font-weight:700">${esc(sfx)}</tspan>${b.face !== b.out ? `<tspan style="fill:var(--muted);font-weight:500"> → ${esc(b.out)}</tspan>` : ""}</text></g>`);
  }
  // eixos globais e escala
  const bar = niceStep(110 / T.k), barPx = bar * T.k;
  const axes = `<g transform="translate(22 ${H - 22})" style="stroke:var(--muted);stroke-width:1.6;fill:none">
      <path d="M0 0H34M28 -4L34 0L28 4"/><path d="M0 0V-34M-4 -28L0 -34L4 -28"/></g>
      <text x="62" y="${H - 18}" style="font:600 11px Barlow;fill:var(--muted)">X</text><text x="17" y="${H - 62}" style="font:600 11px Barlow;fill:var(--muted)">Y</text>`;
  const scale = `<g transform="translate(${W - 22 - barPx} ${H - 22})"><path d="M0 -5V0H${barPx.toFixed(1)}V-5" style="stroke:var(--muted);stroke-width:1.6;fill:none"/>
      <text x="${(barPx / 2).toFixed(1)}" y="-9" text-anchor="middle" style="font:600 11px Barlow;fill:var(--muted)">${fmtNum(bar, bar < 1 ? 2 : 0)} ${esc(u)}</text></g>`;
  return `<svg class="plan" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
    <g style="stroke:var(--grid-line);stroke-width:1">${grid}</g>${shapes.join("")}${labels.join("")}${axes}${scale}</svg>`;
}
function faceTable(set, story) {
  const u = S.model.length_unit || "", idx = storyIndex();
  return `<table class="kv faces-kv"><thead><tr><th></th><th>Face (ETABS)</th><th>Arquivo</th><th class="num">Compr.</th><th class="num">Esp.</th><th class="num">Ângulo</th><th>Stories</th></tr></thead><tbody>
    ${set.faces.map((f, i) => {
      const g = geomAt(f, story), st = (pierInfo(f)?.stories || []).slice().sort((a, b) => (idx.get(b) ?? 0) - (idx.get(a) ?? 0));
      return `<tr class="face-row ${g ? "" : "absent"}" data-face="${esc(f)}"><td><span class="sw" style="background:${faceColor(i)}"></span></td>
        <td><b>${esc(f)}</b></td><td class="mono">${esc(set.outs[i])}.csv</td>
        <td class="num">${g ? fmtNum(g.width) : "—"}</td><td class="num">${g ? fmtNum(g.thick) : "—"}</td><td class="num">${g ? fmtNum(g.angle, 1) + "°" : "—"}</td>
        <td class="muted" title="${esc(st.join(", "))}">${st.length ? `${esc(st[0])} → ${esc(st[st.length - 1])}` : "—"}</td></tr>`;
    }).join("")}</tbody></table>
    <div class="muted" style="font-size:12px;margin-top:8px">Comprimento, espessura e ângulo em ${esc(u)} e graus, na base do ${esc(story)}. ${set.faces.some(f => !geomAt(f, story)) ? "Faces em cinza não existem neste Story." : ""}</div>`;
}
function showPier(key, story) {
  const set = pierSet(key);
  if (!hasGeometry(set)) { toast("O ETABS não devolveu a geometria deste pilar.", "warn"); return; }
  const stories = setStories(set);
  story = story || repStory(set);
  S.pierView = { key, story };
  $("#modalRoot").innerHTML = `<div class="modal-bg" data-act="modal-bg"><div class="modal wide" role="dialog">
    <div class="pm-head">${pierGlyph(key, true, 40)}<div><div class="pm-title">${esc(key)}</div>
      <div class="muted" style="font-size:13px">${set.poly ? `pilar poligonal · ${set.faces.length} faces · ${esc(set.key)}.csv + ${esc(set.key)}.txt` : "pilar comum"}</div></div>
      <div class="spacer"></div>
      <label class="muted" style="font-size:12.5px">Story</label>
      <select class="input sm" id="pmStory" style="width:190px">${stories.map(s => `<option ${s === story ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>
      <button class="btn ghost sm icon" data-act="modal-close" title="Fechar (Esc)">${ic("x")}</button></div>
    <div class="pm-body"><div class="pm-plan">${planSVG(set, story)}</div><div class="pm-side">${faceTable(set, story)}</div></div>
    <div class="pm-foot muted">Planta no sistema global do ETABS, com as faces na posição real (centro de gravidade, largura, espessura e ângulo de cada Pier). Passe o mouse numa linha da tabela para destacar a face.</div>
  </div></div>`;
}

function vPilares() {
  const m = S.model;
  const byName = new Map(m.piers.map(p => [p.name, p]));
  const gcards = m.groups.map(g => {
    const off = S.excluded.has(g.base);
    const st = new Set(g.faces.flatMap(f => (byName.get(f) || { stories: [] }).stories));
    const faceChip = (f, i) => {
      const out = g.outs[i];
      return f === out ? `<span class="chip face">${esc(g.base)}<b>${esc(f.slice(g.base.length))}</b></span>`
        : `<span class="chip face" title="${esc(f)} no ETABS é gravada como ${esc(out)}.csv">${esc(g.base)}<b>${esc(f.slice(g.base.length))}</b><span class="to">→ ${esc(out)}</span></span>`;
    };
    return `<div class="gcard ${off ? "off" : ""}">
      <div class="hd"><span class="glyph-btn" data-pier-view="${esc(g.base)}" title="Ver a seção de ${esc(g.base)}">${pierGlyph(g.base, !off)}</span>
        <div><div class="base">${esc(g.base)}</div><span class="badge info">${g.faces.length} faces</span></div>
        <div class="spacer"></div>
        <button class="btn sm" data-pier-view="${esc(g.base)}" title="Abrir a planta do pilar com o nome de cada face">${ic("plan")} Seção</button>
        <span class="toggle ${off ? "" : "on"}" data-group="${esc(g.base)}" title="Incluir/excluir">${CHECK}</span></div>
      <div class="faces">${g.faces.map(faceChip).join("")}</div>
      <div class="ft"><span>${esc(spanText(st))} · ${st.size} Stories</span>
        <span class="files">${S.full ? `<b>${esc(g.base)}.csv</b> + <b>.txt</b>` : `<span class="no">${esc(g.base)}.csv + .txt</span>`}</span></div>
    </div>`;
  }).join("");
  const others = m.piers.filter(p => !p.group).sort((a, b) => nat(a.name, b.name));
  const chips = others.map(p => {
    if (!p.has_objects) return `<span class="chip pier-chip none" title="Pier sem objetos no modelo: não gera arquivo">${esc(p.name)}</span>`;
    const off = S.excluded.has(p.name);
    return `<span class="chip pier-chip ${off ? "off" : ""}" data-pier="${esc(p.name)}" title="${esc(spanText(p.stories))}">${esc(p.name)} <span class="n">${p.stories.length}</span></span>`;
  }).join("");
  const c = outputCounts();
  return `<div class="card switch-card">
      <label class="switch"><input type="checkbox" id="fullSwitch" ${S.full ? "checked" : ""}><span class="track"></span></label>
      <div><div style="font-weight:600;font-size:15px">Gerar os pilares poligonais completos</div>
        <div class="muted" style="font-size:13.5px">Numa cópia do modelo, as faces P8A, P8B… são reatribuídas ao Pier P8 e os esforços são extraídos de novo, gerando P8.csv e P8.txt. Cada face também gera o seu CSV (P8A → P8-1.csv). O modelo original não é alterado.</div></div>
    </div>
    <div class="card">
      <div class="card-h"><span class="card-t">Pilares poligonais <span class="count">${m.groups.length}</span></span>
        <span class="muted" style="font-size:12.5px">${c.groups} incluídos</span></div>
      ${m.groups.length ? `<div class="group-grid">${gcards}</div>` : `<div class="empty">${ic("pillars")}<div>Nenhum Pier com nome &lt;pilar&gt;-&lt;n&gt; no modelo.</div></div>`}
    </div>
    <div class="card">
      <div class="card-h"><span class="card-t">Demais Piers <span class="count">${others.length}</span></span>
        <span class="muted" style="font-size:12.5px">Clique para incluir ou excluir · o número é a quantidade de Stories</span></div>
      <div class="pier-grid">${chips || '<span class="muted">—</span>'}</div>
    </div>
    <div class="insight" style="margin-top:14px">${ic("info")}<div><div class="tt">Serão gerados ${plural(c.csv, "arquivo CSV", "arquivos CSV")}${c.txt ? ` e ${plural(c.txt, "TXT", "TXT")}` : ""}</div>
      <div class="tx">Um CSV por Pier${c.txt ? " (cada face incluída), mais o CSV do pilar completo e o TXT de lances de cada pilar poligonal" : ""}.</div></div></div>`;
}

/* ------------------------------------------------------------------ passo 4 · lances */
function vLances() {
  const m = S.model;
  const opts = [`<option value="">Nenhum</option>`]
    .concat(m.groups.map(g => `<option value="${esc(g.base)}" ${S.highlight === g.base ? "selected" : ""}>${esc(g.base)} · poligonal (${g.faces.length} faces)</option>`))
    .concat(m.piers.filter(p => !p.group && p.has_objects).sort((a, b) => nat(a.name, b.name))
      .map(p => `<option value="${esc(p.name)}" ${S.highlight === p.name ? "selected" : ""}>${esc(p.name)}</option>`));
  const rows = m.stories.map((s, i) => `<tr data-story="${esc(s.name)}" data-i="${i}">
      <td class="mono">${esc(s.name)}</td><td class="num muted">${s.elev == null ? "—" : fmtNum(s.elev)}</td>
      <td class="num use"></td><td class="sect"></td>
      <td class="num"><input class="input lance" data-story="${esc(s.name)}" inputmode="numeric" value="${esc(S.mapping.general[s.name] ?? "")}"></td></tr>`).join("");
  return `<div class="toolbar">
      <span class="pill" id="lanceStatus"></span>
      <div class="spacer"></div>
      <button class="btn sm" data-act="fill-up" id="fillUp" title="Na linha selecionada, preenche os Stories de cima com +1 a cada Story usado">${ic("up")} Preencher para cima</button>
      <button class="btn sm" data-act="import-map">${ic("upload")} Importar story_map…</button>
      <button class="btn sm ghost" data-act="clear-map">${ic("trash")} Limpar</button>
    </div>
    <div class="lances">
      <div class="table-wrap"><table class="grid" id="lanceTable"><thead><tr><th>Story ETABS</th><th class="num">Cota (m)</th><th class="num">Piers</th>
        <th>Corte${S.highlight ? ` · <span style="color:var(--accent)">${esc(S.highlight)}</span>` : ""}</th><th class="num">Lance TQS</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="stack">
        <div class="card inspector">
          <div class="card-h"><span class="card-t">Pilar em destaque</span>
            <select class="input sm" id="hlSelect" style="width:220px">${opts.join("")}</select></div>
          <div id="inspector"></div>
        </div>
        <div class="card">
          <div class="card-h"><span class="card-t">Exceções por pilar <span class="count" id="excCount">0</span></span>
            <button class="btn sm" data-act="exc-add">${ic("plus")} Adicionar</button></div>
          <div id="excList"></div>
          <div class="muted" style="font-size:12.5px;margin-top:6px">Uma exceção do pilar <span class="mono">P106</span> vale também para as faces <span class="mono">P106A</span>, <span class="mono">P106B</span>… (gravadas como <span class="mono">P106-1</span>, <span class="mono">P106-2</span>…). Na Torre C, por exemplo: Story1 → 2 no P106.</div>
        </div>
      </div>
    </div>`;
}
function hlPiers() {
  if (!S.highlight || !S.model) return [];
  const g = S.model.groups.find(x => x.base === S.highlight);
  return g ? g.faces : [S.highlight];
}
function refreshLances() {
  if (S.step !== "lances" || !$("#lanceTable")) return;
  const m = S.model, use = storyUse(), miss = missing();
  const byName = new Map(m.piers.map(p => [p.name, p]));
  // colunas do corte: pilares poligonais incluídos + o pilar comum em destaque
  const cols = groups().filter(g => !S.excluded.has(g.base)).map(g => ({ key: g.base, stories: new Set(g.faces.flatMap(f => (byName.get(f) || { stories: [] }).stories)), faces: g.faces }));
  if (S.highlight && !cols.find(c => c.key === S.highlight) && byName.get(S.highlight))
    cols.push({ key: S.highlight, stories: new Set(byName.get(S.highlight).stories), faces: [S.highlight] });
  const W = 150, pad = 16, step = cols.length > 1 ? (W - 2 * pad) / (cols.length - 1) : 0;
  for (const tr of $$("#lanceTable tbody tr")) {
    const s = tr.dataset.story, n = use.get(s) || 0;
    tr.classList.toggle("need", miss.has(s));
    tr.classList.toggle("unused", n === 0);
    tr.classList.toggle("hl", S.focusStory === s);
    tr.querySelector(".use").textContent = n || "";
    tr.querySelector(".sect").innerHTML = (n ? `<span class="slab"></span>` : "") + cols.map((c, i) => {
      if (!c.stories.has(s)) return "";
      const hi = c.key === S.highlight;
      const exc = hi && c.faces.some(f => { const r = mapStory(f, s); return r && r.exc; });
      const x = cols.length > 1 ? pad + i * step : W / 2;
      return `<span class="col ${hi ? "hi" : ""} ${exc ? "exc" : ""}" style="left:${(x - (hi ? 4.5 : 3.5)).toFixed(1)}px;${hi ? "width:9px" : ""}" title="${esc(c.key)}"></span>`;
    }).join("");
  }
  const k = miss.size;
  $("#lanceStatus").innerHTML = k ? `<span style="color:var(--warn)">${ic("alert")}</span> Faltam lances em <b style="color:var(--warn)">${plural(k, "Story", "Stories")}</b>`
    : `<span style="color:var(--ok)">${ic("check")}</span> Todos os Stories usados têm lance`;
  const f = S.focusStory, fv = f && S.mapping.general[f];
  $("#fillUp").disabled = !(f && /^\d+$/.test(String(fv || "").trim()));
  renderInspector();
  renderRail(); renderActions();
}
function renderInspector() {
  const box = $("#inspector"); if (!box) return;
  if (!S.highlight) { box.innerHTML = `<div class="muted" style="font-size:13.5px">Escolha um pilar para ver no corte os Stories em que ele existe e os lances do TQS resultantes (as exceções aparecem em amarelo).</div>`; return; }
  const idx = storyIndex(), piers = hlPiers();
  const byName = new Map(S.model.piers.map(p => [p.name, p]));
  const st = [...new Set(piers.flatMap(p => (byName.get(p) || { stories: [] }).stories))].sort((a, b) => (idx.get(b) ?? 0) - (idx.get(a) ?? 0));
  const lances = [], excs = new Set(); let miss = 0;
  for (const s of st) {
    const r = mapStory(piers[0], s);
    for (const p of piers) { const q = mapStory(p, s); if (q && q.exc) excs.add(s); }
    if (r && /^\d+$/.test(r.v)) lances.push(+r.v); else miss++;
  }
  const g = S.model.groups.find(x => x.base === S.highlight);
  box.innerHTML = `<div class="row" style="align-items:center;margin-bottom:10px"><span class="glyph-btn" data-pier-view="${esc(S.highlight)}" title="Ver a seção">${pierGlyph(S.highlight, true)}</span>
      <div class="grow"><div class="big">${esc(S.highlight)}</div><div class="muted" style="font-size:12.5px">${g ? `pilar poligonal · ${g.faces.length} faces: ${esc(g.faces.join(", "))}` : "pilar comum"}</div></div>
      <button class="btn sm" data-pier-view="${esc(S.highlight)}">${ic("plan")} Seção</button></div>
    <table class="kv"><tbody>
      <tr><td>Stories no ETABS</td><td>${st.length}</td></tr>
      <tr><td>Do Story</td><td class="mono">${esc(st[0] || "—")}</td></tr>
      <tr><td>Até o Story</td><td class="mono">${esc(st[st.length - 1] || "—")}</td></tr>
      <tr><td>Lances do TQS</td><td>${lances.length ? `<span class="lance-tag ${excs.size ? "exc" : ""}">${Math.min(...lances)}</span> → <span class="lance-tag">${Math.max(...lances)}</span>` : "—"}</td></tr>
      <tr><td>Exceções aplicadas</td><td>${excs.size ? `<span style="color:var(--warn)">${[...excs].map(esc).join(", ")}</span>` : "nenhuma"}</td></tr>
      ${miss ? `<tr><td>Sem lance</td><td style="color:var(--warn)">${miss}</td></tr>` : ""}
      <tr><td>Arquivos</td><td class="mono" style="font-size:12px">${g ? (S.full ? `${esc(g.base)}.csv, ${esc(g.base)}.txt + ${esc(g.outs[0])}…${esc(g.outs[g.outs.length - 1])}` : `${esc(g.outs[0])}…${esc(g.outs[g.outs.length - 1])}`) : `${esc(outOf(S.highlight))}.csv`}</td></tr>
    </tbody></table>`;
}
function renderExceptions() {
  const m = S.model, list = $("#excList"); if (!list) return;
  const pierOpts = [...new Set([...m.groups.map(g => g.base), ...m.piers.filter(p => p.has_objects).map(p => p.name)])].sort(nat);
  const exc = S.mapping.exceptions;
  $("#excCount").textContent = exc.length;
  list.innerHTML = exc.length ? `<div class="exc-head"><span>Pilar</span><span>Story ETABS</span><span>Lance</span><span></span></div>` + exc.map((e, i) => `<div class="exc-row" data-exc="${i}">
      <select class="input sm" data-f="pier"><option value=""></option>${pierOpts.map(p => `<option ${p === e.pier ? "selected" : ""}>${esc(p)}</option>`).join("")}${e.pier && !pierOpts.includes(e.pier) ? `<option selected>${esc(e.pier)}</option>` : ""}</select>
      <select class="input sm" data-f="story"><option value=""></option>${m.stories.map(s => `<option ${s.name === e.story ? "selected" : ""}>${esc(s.name)}</option>`).join("")}</select>
      <input class="input sm" data-f="lance" style="text-align:center;font-weight:600" value="${esc(e.lance)}">
      <button class="btn ghost sm icon" data-act="exc-del" title="Remover">${ic("trash")}</button></div>`).join("")
    : `<div class="muted" style="font-size:13.5px;padding:4px 0 8px">Nenhuma exceção. Todos os pilares seguem a tabela geral.</div>`;
}
function fillUp() {
  const f = S.focusStory, v = parseInt(String(S.mapping.general[f] || "").trim(), 10);
  if (!f || isNaN(v)) return;
  const st = S.model.stories, i = st.findIndex(s => s.name === f), use = storyUse();
  let n = v, count = 0;
  for (let j = i - 1; j >= 0; j--) {
    if (!use.get(st[j].name)) continue;
    n += 1; count++; S.mapping.general[st[j].name] = String(n);
  }
  for (const inp of $$("#lanceTable input.lance")) inp.value = S.mapping.general[inp.dataset.story] ?? "";
  refreshLances();
  toast(`${plural(count, "Story preenchido", "Stories preenchidos")} acima de ${f} (${v + 1} → ${n}).`);
}

/* ------------------------------------------------------------------ passo 5 · exportar */
function readyToExport() { return !!S.model && S.combos.size > 0 && selectedPiers().length > 0 && missing().size === 0; }
function vExportar() {
  const m = S.model, c = outputCounts(), k = missing().size, sel = selectedPiers();
  const combos = m.combos.filter(x => S.combos.has(x));
  const exclN = m.piers.filter(p => p.has_objects && isExcluded(p.name)).length;
  const item = (ok, kk, v, step) => `<div class="it"><span class="st ${ok ? "ok" : "warn"}">${ic(ok ? "check" : "alert")}</span>
      <div style="min-width:0"><div class="k">${kk}</div><div class="v" title="${esc(v)}">${esc(v)}</div></div>
      <button class="btn ghost sm" data-go="${step}">Editar</button></div>`;
  const folder = S.card.folder.replace(/[\\/]+$/, "");
  return `${S.result ? vResult() : ""}<div class="export">
    <div class="card">
      <div class="card-h"><span class="card-t">Resumo</span></div>
      <div class="checklist">
        ${item(true, "Modelo", S.card.name, "modelo")}
        ${item(combos.length > 0, `${plural(combos.length, "combinação", "combinações")}`, combos.join(", ") || "nenhuma marcada", "combos")}
        ${item(sel.length > 0, `${sel.length} Piers`, `${c.groups} poligonais${exclN ? ` · ${exclN} excluídos` : ""}`, "pilares")}
        ${item(true, S.full && c.groups ? "Pilares completos: sim" : "Pilares completos: não", S.full && c.groups ? "cópia de trabalho do modelo, com as faces reatribuídas ao pilar" : "só os Piers como estão no modelo", "pilares")}
        ${item(k === 0, "Lances do TQS", k ? `faltam ${plural(k, "Story", "Stories")}` : `${Object.keys(S.mapping.general).length} Stories + ${plural(S.mapping.exceptions.length, "exceção", "exceções")} · salvos em story_map.csv`, "lances")}
      </div>
      <div class="dest">${ic("folder")}<div style="min-width:0"><div class="mono sel" style="word-break:break-all">${esc(folder)}\\${esc(S.boot.output)}</div>
        <div class="muted" style="font-size:12.5px">${plural(c.csv, "CSV", "CSV")}${c.txt ? ` · ${plural(c.txt, "TXT", "TXT")}` : ""}${S.card.etb ? " · a pasta atual será renomeada para ETB_anterior_&lt;data&gt;" : ""}</div></div></div>
      <div class="go"><button class="btn primary lg" data-act="export" ${readyToExport() && !S.exporting ? "" : "disabled"}>${S.exporting ? '<span class="spinner"></span> Exportando…' : `${ic("export")} Exportar para ETB`}</button>
        <span class="muted" style="font-size:13px">${combos.length} × ${S.full && c.groups ? "2 etapas" : "1 etapa"} de extração</span></div>
    </div>
    <div class="stack">
      <div class="card"><div class="card-h"><span class="card-t">Progresso</span><span class="muted" id="elapsed" style="font-size:12.5px"></span></div><ol class="timeline" id="timeline"></ol></div>
    </div></div>`;
}
function vResult() {
  const r = S.result;
  return `<div class="card result" style="margin-bottom:16px"><div class="big-ok"><span class="medal">${ic("check")}</span><div>
      <div style="font-size:20px;font-weight:600">Exportação concluída</div>
      <div class="muted">${plural(r.csv, "CSV", "CSV")} e ${plural(r.txt, "TXT", "TXT")} em ${fmtNum(r.seconds, 1)} s${r.reanalyzed ? " · a cópia foi reanalisada" : " · sem reanálise"}</div></div></div>
    <div class="dest" style="margin-top:0">${ic("folder")}<div class="mono sel grow" style="word-break:break-all">${esc(r.out_dir)}</div>
      <button class="btn sm" data-act="openetb">${ic("folder")} Abrir</button></div>
    ${r.backup ? `<div class="muted" style="font-size:12.5px;margin-top:8px">A pasta anterior foi renomeada para <span class="mono">${esc(r.backup)}</span>.</div>` : ""}
    <div class="files">${r.files.map(f => `<span class="chip ${f.toLowerCase().endsWith(".txt") ? "txt" : ""}">${esc(f)}</span>`).join("")}</div>
    ${(r.warnings || []).map(w => `<div class="insight warn" style="margin-top:10px">${ic("alert")}<div class="tx" style="margin:0;color:var(--text)">${esc(w)}</div></div>`).join("")}
  </div>`;
}
function stageApplies(st) {
  if (!st.poly) return true;
  return S.full && outputCounts().groups > 0;
}
const UNITS = {
  etapa1: n => plural(n, "combinação extraída", "combinações extraídas"),
  etapa2: n => plural(n, "combinação extraída", "combinações extraídas"),
  copia: n => `modelo + ${plural(n, "arquivo de resultado", "arquivos de resultado")}`,
  reatribuicao: n => plural(n, "objeto reatribuído", "objetos reatribuídos"),
};
function renderTimeline() {
  const tl = $("#timeline"); if (!tl) return;
  const now = performance.now();
  tl.innerHTML = STAGES.map(st => {
    const x = S.stages[st.id] || {};
    let state = x.state || "pending";
    if (!stageApplies(st)) state = "skip";
    const icon = state === "done" ? ic("check") : state === "fail" ? ic("x") : state === "skip" ? ic("minus") : state === "active" ? '<span class="spinner" style="width:12px;height:12px"></span>' : "";
    let det = "";
    if (state === "skip") det = st.poly ? (S.full ? "sem pilares poligonais" : "pilares completos desativados") : "";
    else if (st.id === "analise" && state === "pending" && (S.result || S.exporting)) det = S.result ? "não foi necessária" : "só se o ETABS exigir";
    else if (state === "done" && x.total != null && UNITS[st.id]) det = UNITS[st.id](x.total);
    else if (x.text) det = x.text;
    const pct = x.total ? Math.round(100 * (x.done || 0) / x.total) : null;
    const tm = x.t1 ? `${fmtNum((x.t1 - x.t0) / 1000, 1)} s` : state === "active" && x.t0 ? `${fmtNum((now - x.t0) / 1000, 0)} s` : "";
    return `<li class="tl ${st.id === "analise" && state === "pending" && S.result ? "skip" : state}"><span class="dot">${icon}</span><span class="nm">${st.nm}</span><span class="tm">${tm}</span>
      ${det ? `<span class="det">${esc(det)}${x.total && state === "active" ? ` · ${x.done}/${x.total}` : ""}</span>` : ""}
      ${state === "active" && pct != null ? `<div class="bar"><i style="width:${pct}%"></i></div>` : state === "active" ? '<div class="bar indet"><i></i></div>' : ""}</li>`;
  }).join("");
  if (S.exportT0) $("#elapsed").textContent = S.exporting ? `${fmtNum((now - S.exportT0) / 1000, 0)} s` : S.result ? `total ${fmtNum(S.result.seconds, 1)} s` : "";
}
function onProgress(e) {
  const now = performance.now();
  const cur = S.current;
  if (cur !== e.stage) {
    if (cur && S.stages[cur]) { S.stages[cur].state = "done"; S.stages[cur].t1 = now; }
    // etapas puladas entre a anterior e a atual
    const ia = STAGES.findIndex(s => s.id === cur), ib = STAGES.findIndex(s => s.id === e.stage);
    for (let i = ia + 1; i < ib; i++) if (!S.stages[STAGES[i].id]) S.stages[STAGES[i].id] = { state: "pending" };
    S.stages[e.stage] = { state: "active", t0: now };
    S.current = e.stage;
  }
  Object.assign(S.stages[e.stage], { done: e.done, total: e.total, text: e.text || S.stages[e.stage].text });
  if (S.step === "exportar") renderTimeline();
}

/* ------------------------------------------------------------------ ações */
async function pickModel() {
  try {
    const card = await S.api.pick_model(S.card ? S.card.path : "");
    if (card) setCard(card);
  } catch (e) { showError("Não foi possível abrir o arquivo", errMsg(e)); }
}
function setCard(card) {
  S.card = card; S.model = null; S.result = null; S.stages = {}; S.current = null;
  S.step = "modelo"; render();
}
async function readModel() {
  if (!S.card) return;
  S.reading = true; S.readT0 = performance.now(); S.model = null; S.result = null; render();
  try { await S.api.read_model(S.card.path); } catch (e) { S.reading = false; render(); showError("Erro ao ler o modelo", errMsg(e)); }
}
function onModelRead(data) {
  S.reading = false; S.model = data;
  const prefs = data.prefs || {};
  const valid = new Set(data.combos);
  const saved = (prefs.combos || []).filter(c => valid.has(c));
  S.combos = new Set(saved.length ? saved : data.default_combos);
  S.excluded = new Set(prefs.excluded || []);
  S.full = prefs.full !== undefined ? !!prefs.full : true;
  S.mapping = { general: { ...(data.mapping.general || {}) }, exceptions: (data.mapping.exceptions || []).map(e => ({ ...e })) };
  S.highlight = data.groups[0] ? data.groups[0].base : "";
  S.card.story_map = S.card.story_map || Object.keys(S.mapping.general).length > 0;
  render();
  toast(`Modelo lido: ${data.piers.length} Piers, ${data.combos.length} combinações, ${data.stories.length} Stories.`);
}
async function doExport() {
  if (!readyToExport() || S.exporting) return;
  const req = {
    path: S.card.path, combos: S.model.combos.filter(c => S.combos.has(c)),
    excluded: [...S.excluded], full: S.full, mapping: S.mapping,
  };
  S.exporting = true; S.result = null; S.stages = {}; S.current = null; S.failed = false; S.exportT0 = performance.now();
  render();
  try { await S.api.export(req); }
  catch (e) { S.exporting = false; render(); showError("Não foi possível exportar", errMsg(e)); }
}
function onExportDone(ok, data) {
  S.exporting = false;
  const now = performance.now();
  if (S.current && S.stages[S.current]) {
    S.stages[S.current].state = ok ? "done" : "fail"; S.stages[S.current].t1 = now;
  }
  if (ok) {
    S.result = data; S.card.etb = true;
    toast(`Pronto: ${data.csv} CSV e ${data.txt} TXT gravados.`);
  } else {
    S.failed = true;
    showError("A exportação falhou", data, true);
  }
  render();
}
async function importMap() {
  try {
    const mp = await S.api.import_story_map(S.card ? S.card.path : "");
    if (!mp) return;
    S.mapping = { general: { ...(mp.general || {}) }, exceptions: (mp.exceptions || []).map(e => ({ ...e })) };
    render(); toast(`Lances importados: ${Object.keys(S.mapping.general).length} Stories, ${plural(S.mapping.exceptions.length, "exceção", "exceções")}.`);
  } catch (e) { showError("Não foi possível importar", errMsg(e)); }
}

/* ------------------------------------------------------------------ log, toasts, modal */
function addLog(e) {
  S.logs.push(e);
  if (e.lvl === "warn") S.warns++;
  if (e.lvl === "error") S.errs++;
  const body = $("#logBody");
  const atEnd = body.scrollTop + body.clientHeight >= body.scrollHeight - 20;
  body.insertAdjacentHTML("beforeend", `<div class="ln ${e.lvl}"><span class="tm">${esc(e.time)}</span><span>${esc(e.msg)}</span></div>`);
  if (atEnd) body.scrollTop = body.scrollHeight;
  renderLogBtn();
}
function setLog(open) { S.logOpen = open; $("#drawer").classList.toggle("open", open); if (open) { const b = $("#logBody"); b.scrollTop = b.scrollHeight; } }
function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`; el.innerHTML = `${ic(kind === "warn" ? "alert" : "check")}<span>${esc(msg)}</span>`;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.transition = "opacity .3s"; el.style.opacity = "0"; setTimeout(() => el.remove(), 320); }, 3800);
}
function showError(title, msg, withLog = false) {
  $("#modalRoot").innerHTML = `<div class="modal-bg"><div class="modal" role="dialog"><div class="mh">${ic("alert")}${esc(title)}</div>
    <div class="mb">${esc(msg)}</div><div class="mf">${withLog ? '<button class="btn" data-act="modal-log">Ver log</button>' : ""}<button class="btn primary" data-act="modal-close">OK</button></div></div></div>`;
}

/* ------------------------------------------------------------------ eventos */
document.addEventListener("click", ev => {
  const t = ev.target;
  const step = t.closest(".step"); if (step) return go(step.dataset.step);
  const g = t.closest("[data-go]"); if (g) return go(g.dataset.go);
  const rec = t.closest("[data-recent]"); if (rec) return setCard(S.boot.recent[+rec.dataset.recent]);
  const combo = t.closest("[data-combo]");
  if (combo) { const c = combo.dataset.combo; S.combos.has(c) ? S.combos.delete(c) : S.combos.add(c); renderComboGrid(); renderRail(); renderActions(); return; }
  const pv = t.closest("[data-pier-view]");
  if (pv) return showPier(pv.dataset.pierView);
  if (t.matches && t.matches(".modal-bg")) { $("#modalRoot").innerHTML = ""; return; }
  const grp = t.closest("[data-group]");
  if (grp) { const b = grp.dataset.group; S.excluded.has(b) ? S.excluded.delete(b) : S.excluded.add(b); keepScroll(render); return; }
  const pc = t.closest("[data-pier]");
  if (pc) { const p = pc.dataset.pier; S.excluded.has(p) ? S.excluded.delete(p) : S.excluded.add(p); keepScroll(render); return; }
  const th = t.closest("[data-theme]"); if (th && th.closest("#themeSeg")) return setTheme(th.dataset.theme);
  const tr = t.closest("#lanceTable tbody tr");
  if (tr) { S.focusStory = tr.dataset.story; refreshLances(); }
  const a = t.closest("[data-act]"); if (!a || a.disabled) return;
  switch (a.dataset.act) {
    case "pick": return pickModel();
    case "read": return readModel();
    case "next": return nextStep(1);
    case "back": return nextStep(-1);
    case "combos-default": S.combos = new Set(S.model.default_combos); renderComboGrid(); renderRail(); renderActions(); return;
    case "combos-all": S.combos = new Set(S.model.combos); renderComboGrid(); renderRail(); renderActions(); return;
    case "combos-none": S.combos = new Set(); renderComboGrid(); renderRail(); renderActions(); return;
    case "fill-up": return fillUp();
    case "import-map": return importMap();
    case "clear-map":
      S.mapping = { general: {}, exceptions: [] };
      $$("#lanceTable input.lance").forEach(i => { i.value = ""; }); renderExceptions(); refreshLances(); return;
    case "exc-add": S.mapping.exceptions.push({ pier: S.highlight || "", story: "", lance: "" }); renderExceptions(); refreshLances(); return;
    case "exc-del": { const i = +a.closest("[data-exc]").dataset.exc; S.mapping.exceptions.splice(i, 1); renderExceptions(); refreshLances(); return; }
    case "export": return doExport();
    case "openetb": return S.api.open_folder(S.result ? S.result.out_dir : `${S.card.folder}\\${S.boot.output}`);
    case "modal-close": $("#modalRoot").innerHTML = ""; return;
    case "modal-log": $("#modalRoot").innerHTML = ""; setLog(true); return;
  }
});
document.addEventListener("input", ev => {
  const t = ev.target;
  if (t.id === "comboSearch") { S.search = t.value; renderComboGrid(); return; }
  if (t.classList.contains("lance")) {
    const v = t.value.replace(/[^\d]/g, ""); if (v !== t.value) t.value = v;
    if (v) S.mapping.general[t.dataset.story] = v; else delete S.mapping.general[t.dataset.story];
    S.focusStory = t.dataset.story; refreshLances(); return;
  }
  const row = t.closest("[data-exc]");
  if (row) { S.mapping.exceptions[+row.dataset.exc][t.dataset.f] = t.value.trim(); refreshLances(); }
});
document.addEventListener("change", ev => {
  const t = ev.target;
  if (t.id === "onlySel") { S.onlySel = t.checked; renderComboGrid(); }
  if (t.id === "fullSwitch") { S.full = t.checked; keepScroll(render); }
  if (t.id === "pmStory" && S.pierView) { showPier(S.pierView.key, t.value); return; }
  if (t.id === "hlSelect") { S.highlight = t.value; const th = $("#lanceTable thead th:nth-child(4)"); if (th) th.innerHTML = `Corte${S.highlight ? ` · <span style="color:var(--accent)">${esc(S.highlight)}</span>` : ""}`; refreshLances(); }
  const row = t.closest("[data-exc]");
  if (row) { S.mapping.exceptions[+row.dataset.exc][t.dataset.f] = t.value.trim(); refreshLances(); }
});
document.addEventListener("focusin", ev => {
  const t = ev.target;
  if (t.classList && t.classList.contains("lance")) { S.focusStory = t.dataset.story; refreshLances(); }
});
document.addEventListener("keydown", ev => {
  const t = ev.target;
  if (t.classList && t.classList.contains("lance") && (ev.key === "Enter" || ev.key === "ArrowDown" || ev.key === "ArrowUp")) {
    ev.preventDefault();
    const all = $$("#lanceTable input.lance"), i = all.indexOf(t);
    const j = ev.key === "ArrowUp" ? i - 1 : i + 1;
    if (all[j]) { all[j].focus(); all[j].select(); }
  }
  if (ev.key === "Escape" && $("#modalRoot").innerHTML) $("#modalRoot").innerHTML = "";
  if (ev.ctrlKey && (ev.key === "l" || ev.key === "L")) { ev.preventDefault(); setLog(!S.logOpen); }
});
// destaque da face: linha da tabela <-> desenho
function hlFace(face, on) {
  $$("#modalRoot [data-face]").forEach(el => el.classList.toggle("hl", on && el.dataset.face === face));
}
document.addEventListener("mouseover", ev => {
  const el = ev.target.closest && ev.target.closest("#modalRoot [data-face]");
  hlFace(el ? el.dataset.face : null, !!el);
});
function keepScroll(fn) { const c = $("#content"), y = c.scrollTop; fn(); c.scrollTop = y; }
$("#logBtn").addEventListener("click", () => setLog(!S.logOpen));
$("#logClose").addEventListener("click", () => setLog(false));
$("#logCopy").addEventListener("click", () => {
  const txt = S.logs.map(l => `${l.time} ${l.lvl.toUpperCase().padEnd(5)} ${l.msg}`).join("\n");
  navigator.clipboard.writeText(txt).then(() => toast("Log copiado."), () => toast("Não foi possível copiar.", "warn"));
});

function setTheme(t) {
  document.documentElement.dataset.theme = t;
  $$("#themeSeg button").forEach(b => b.classList.toggle("on", b.dataset.theme === t));
  if (S.api) S.api.set_theme(t);
}

/* ------------------------------------------------------------------ ponte com o Python */
function handleEvents(list) {
  for (const e of list || []) {
    if (e.t === "log") addLog(e);
    else if (e.t === "progress") onProgress(e);
    else if (e.t === "job") {
      if (e.name === "diag") {
        S.apiState = e.ok ? { state: "ok", l1: `API do ETABS · v${e.data.api}`, l2: (e.data.installs || []).join(", ") || "ETABS instalado", title: "A API do ETABS está acessível." }
          : { state: "err", l1: "API do ETABS indisponível", l2: "veja o log", title: e.data };
        renderRail();
        if (!e.ok) showError("API do ETABS indisponível", e.data);
      } else if (e.name === "read") {
        if (e.ok) onModelRead(e.data); else { S.reading = false; render(); showError("Erro ao ler o modelo", e.data, true); }
      } else if (e.name === "export") onExportDone(e.ok, e.data);
    }
  }
}
let polling = false;
async function pollLoop() {
  if (polling) return; polling = true;
  try { handleEvents(await S.api.poll()); } catch (e) { /* janela fechando */ }
  polling = false;
}
function tick() {
  if (S.reading) { const el = $("#readTimer"); if (el) el.textContent = `${Math.round((performance.now() - S.readT0) / 1000)} s`; }
  if (S.exporting && S.step === "exportar") renderTimeline();
}

const bridgeReady = () => !!(window.pywebview && window.pywebview.api && typeof window.pywebview.api.boot === "function");
async function start() {
  if (S.api || !bridgeReady()) return;          // a ponte existe mas os métodos Python ainda não
  S.api = window.pywebview.api;
  try { S.boot = await S.api.boot(); }
  catch (e) { S.boot = { version: "?", recent: [], theme: "dark", output: "ETB" }; showError("Erro ao iniciar", errMsg(e)); }
  $("#themeSeg").innerHTML = `<button data-theme="dark" title="Tema escuro">${ic("moon")}</button><button data-theme="light" title="Tema claro">${ic("sun")}</button>`;
  setTheme(S.boot.theme || "dark");
  $("#ver").textContent = `v${S.boot.version}`;
  $("#logCopy").innerHTML = `${ic("copy")} Copiar`;
  $("#logClose").innerHTML = ic("x");
  render();
  setInterval(pollLoop, 200);
  setInterval(tick, 500);
  setTimeout(() => $("#boot").classList.add("gone"), 60);
}
window.addEventListener("pywebviewready", start);
start();
// Garantia: se o evento chegar antes dos métodos, tenta de novo por alguns segundos.
const retry = setInterval(() => { if (S.api) clearInterval(retry); else start(); }, 250);
setTimeout(() => clearInterval(retry), 15000);
// Desenvolvimento no navegador: index.html?mock carrega uma API simulada (ui/dev/mock.js).
if (/[?&]mock/.test(location.search)) setTimeout(() => {
  if (S.api) return;
  const s = document.createElement("script"); s.src = "dev/mock.js"; document.body.appendChild(s);
}, 150);
