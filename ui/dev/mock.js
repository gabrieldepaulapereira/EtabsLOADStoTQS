/* API simulada para desenvolver a interface no navegador (index.html?mock).
   Não vai para o .exe. Dados: ui/dev/demo.json (Torre C, gerado a partir da planilha). */
(function () {
  const Q = [];
  const now = () => new Date().toTimeString().slice(0, 8);
  const log = (msg, lvl = "info") => Q.push({ t: "log", lvl, msg, time: now() });
  const later = (ms, fn) => new Promise(r => setTimeout(() => r(fn && fn()), ms));
  let demo = null;
  const card = {
    path: "E:\\ETABS\\GARDEN PARK\\Torre C\\Garden-Park-C-v109.EDB", name: "Garden-Park-C-v109.EDB",
    folder: "E:\\ETABS\\GARDEN PARK\\Torre C", size_mb: 48.6, modified: "25/09/2026 18:42",
    analyzed: true, story_map: true, etb: true,
  };
  const fail = /[?&]mock=fail/.test(location.search);
  const api = {
    boot: async () => {
      later(700, () => { log("Exportador de Pier Forces 1.0.0 | Python 3.13.7 (demo)"); log("ETABS instalados: ETABS 22");
        log("API do ETABS OK (versão 2.01). ETABS abertos agora: nenhum"); Q.push({ t: "job", name: "diag", ok: true, data: { api: "2.01", installs: ["ETABS 22"] } }); });
      return { version: "1.0.0", recent: [card, { ...card, name: "Garden-Park-A-v91.EDB", path: "E:\\ETABS\\GARDEN PARK\\Torre A\\Garden-Park-A-v91.EDB", folder: "E:\\ETABS\\GARDEN PARK\\Torre A", modified: "12/09/2026 09:10" },
        { ...card, name: "MARAMBAIA-V46.EDB", path: "E:\\ETABS\\MARAMBAIA\\MARAMBAIA-V46.EDB", folder: "E:\\ETABS\\MARAMBAIA", analyzed: false, modified: "02/09/2026 16:55" }],
        theme: "dark", output: "ETB", story_map: "story_map.csv" };
    },
    set_theme: async () => null,
    pick_model: async () => later(250, () => card),
    model_card: async p => card,
    open_folder: async () => null,
    read_model: async () => {
      demo = demo || await (await fetch("dev/demo.json")).json();
      log("Iniciando o ETABS..."); log("Abrindo Garden-Park-C-v109.EDB ...");
      later(1800, () => {
        log("ETABS 22.0.0 | modelo analisado (travado): sim");
        log(`Encontrados ${demo.piers.length} Piers, ${demo.combos.length} combinações e ${demo.stories.length} Stories.`);
        log("Lances carregados de story_map.csv (75 entradas).");
        Q.push({ t: "job", name: "read", ok: true, data: JSON.parse(JSON.stringify(demo)) });
      });
      return true;
    },
    import_story_map: async () => later(200, () => JSON.parse(JSON.stringify(demo.mapping))),
    export: async req => {
      const combos = req.combos, poly = req.full && demo.groups.some(g => !req.excluded.includes(g.base));
      const steps = [["conexao", null, "Garden-Park-C-v109.EDB", 700]];
      combos.forEach((c, i) => steps.push(["etapa1", [i, combos.length], c, 650]));
      steps.push(["etapa1", [combos.length, combos.length], "", 50]);
      if (poly) {
        ["Garden-Park-C-v109.Y00", "Garden-Park-C-v109.Y01", "Garden-Park-C-v109.K_I"].forEach((f, i) => steps.push(["copia", [i, 3], f, 450]));
        [0, 500, 1000, 1500].forEach(i => steps.push(["reatribuicao", [i, 1612], "Lendo AreaObj", 300]));
        steps.push(["reatribuicao", [67, 67], "", 300]);
        combos.forEach((c, i) => steps.push(["etapa2", [i, combos.length], c, 550]));
        steps.push(["etapa2", [combos.length, combos.length], "", 50]);
      }
      steps.push(["gravacao", null, card.folder + "\\ETB", 600]);
      (async () => {
        log("Modelo: " + card.path);
        for (const [stage, dt, text, ms] of steps) {
          Q.push({ t: "progress", stage, done: dt ? dt[0] : null, total: dt ? dt[1] : null, text });
          if (stage === "etapa1" && text) log(`[${combos.indexOf(text) + 1}/${combos.length}] ${text}: 6256 resultados (0.4s)`);
          if (fail && stage === "reatribuicao") {
            await later(600);
            log("Reatribuição incompleta: a cópia ainda tem esforços em P8-7", "error");
            Q.push({ t: "job", name: "export", ok: false, data: "Reatribuição incompleta: a cópia ainda tem esforços em P8-7" });
            return;
          }
          await later(ms);
        }
        log("Conferência: os 15 Piers não reatribuídos têm esforços idênticos na cópia.");
        log("Piers sem resultados (sem arquivo): CHK", "warn");
        const files = demo.piers.filter(p => p.has_objects).map(p => p.out + ".csv")
          .concat(poly ? demo.groups.flatMap(g => [g.base + ".csv", g.base + ".txt"]) : [])
          .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
        Q.push({ t: "job", name: "export", ok: true, data: {
          out_dir: card.folder + "\\ETB", csv: files.filter(f => f.endsWith(".csv")).length, txt: files.filter(f => f.endsWith(".txt")).length,
          backup: "ETB_anterior_20260927_163012", reanalyzed: false, warnings: ["Piers sem resultados (sem arquivo): CHK"],
          files, seconds: 11.8 } });
      })();
      return { queued: true };
    },
    poll: async () => Q.splice(0, Q.length),
  };
  window.pywebview = { api };
  window.dispatchEvent(new Event("pywebviewready"));
})();
