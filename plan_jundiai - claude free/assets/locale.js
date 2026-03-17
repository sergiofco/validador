(function () {

  // -----------------------------------------------
  // 1. Traduções PT-BR
  // -----------------------------------------------
  const traducoes_curto = {
    "Jan": "JAN", "Feb": "FEV", "Mar": "MAR", "Apr": "ABR",
    "May": "MAI", "Jun": "JUN", "Jul": "JUL", "Aug": "AGO",
    "Sep": "SET", "Oct": "OUT", "Nov": "NOV", "Dec": "DEZ"
};

const traducoes_longo = {
    "January": "Janeiro", "February": "Fevereiro", "March": "Março",
    "April": "Abril", "May": "Maio", "June": "Junho",
    "July": "Julho", "August": "Agosto", "September": "Setembro",
    "October": "Outubro", "November": "Novembro", "December": "Dezembro"
};

  // nomes PT para comparação (índice = getMonth())
  const nomesMes = [
    "JAN","FEV","MAR","ABR","MAI","JUN",
    "JUL","AGO","SET","OUT","NOV","DEZ"
  ];

  function traduzir(texto) {
    let s = texto;
    // longo primeiro (evita "Mar" casar antes de "March")
    Object.keys(traducoes_longo).forEach(function(k) {
        s = s.replace(new RegExp("\\b" + k + "\\b", "g"), traducoes_longo[k]);
    });
    Object.keys(traducoes_curto).forEach(function(k) {
        s = s.replace(new RegExp("\\b" + k + "\\b", "g"), traducoes_curto[k]);
    });
    return s;
}

  // -----------------------------------------------
  // 2. Semana ISO
  // -----------------------------------------------
  function isoWeek(d) {
    const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
    const jan1 = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil((((t - jan1) / 86400000) + 1) / 7);
  }

  const hoje       = new Date();
  const semAtual   = isoWeek(hoje);
  const mesAtual   = hoje.getMonth();   // 0-based
  const anoAtual   = hoje.getFullYear();

  // -----------------------------------------------
  // 3. Processar cabeçalhos
  // -----------------------------------------------
  function processar() {

    /* --- linha primária: mês / ano --- */
    document.querySelectorAll(".rct-dateHeader-primary").forEach(function (el) {
      // O formato Moment é "MMMM YYYY" → chega como "March⏎2026"
      let txt = el.textContent || "";
      txt = traduzir(txt);
      txt = txt.replace(/⏎/g, "\n").replace(/\\n/g, "\n");

      if (el.textContent !== txt) el.textContent = txt;

      // destaque do mês atual
      const partes   = txt.split("\n");
      const nomeMes  = (partes[0] || "").trim().toLowerCase();
      const anoStr   = parseInt((partes[1] || "").trim(), 10);
      const ehAtual  = (nomeMes === nomesMes[mesAtual] && anoStr === anoAtual);

      el.classList.toggle("mes-atual", ehAtual);
    });

    /* --- linha secundária: semana (número) ou dia (visão detalhada) --- */
    document.querySelectorAll(".rct-dateHeader:not(.rct-dateHeader-primary)").forEach(function (el) {
      let txt = (el.textContent || "").trim();

      // traduz dias da semana (visão diária)
      const trad = traduzir(txt);
      if (txt !== trad) { el.textContent = trad; txt = trad; }

      const num = parseInt(txt, 10);
      if (isNaN(num)) return;
  
      // Descobre a semana ISO do dia que esse número representa
      // O cabeçalho exibe o dia inicial de cada semana — precisamos
      // calcular a semana ISO desse dia para comparar com semAtual
      // Mas não temos o mês direto, então usamos outra abordagem:
      // comparamos a posição relativa do elemento no DOM
      // para encontrar qual semana ele representa via timestamp
  
      el.classList.toggle("semana-atual", num === semAtual);
      if (el.parentElement) el.parentElement.classList.toggle("semana-atual-col", num === semAtual);
  });

  }

  // -----------------------------------------------
  // 4. Observer
  // -----------------------------------------------
  function iniciar() {

    if (window.moment) {
      window.moment.locale('pt-br', { week: { dow: 1, doy: 4 } });
      window.moment.locale('pt-br');
    }

    if (window.moment) {
      window.moment.locale('en', {
          week: { dow: 1, doy: 4 }
      });
  }

  processar();
    const obs = new MutationObserver(processar);
    obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  window.addEventListener("load", iniciar);

})();