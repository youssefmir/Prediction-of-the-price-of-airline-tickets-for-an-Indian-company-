/* ==========================================================================
   Prix des billets d'avion : logique de la page (vanilla JS, aucune dépendance)
   Données : window.SITE_DATA (data.js, généré par scripts/build_site_data.py)
   Modèle  : window.FlightModel (model.js)
   Règle des animations : le rendu par défaut est l'état final. Un graphique
   n'est remis à zéro que lorsqu'il approche de l'écran, puis animé une fois
   visible ; avec « mouvement réduit », tout reste à l'état final.
   ========================================================================== */
(function () {
  'use strict';

  const D = window.SITE_DATA;
  const F = window.Frame;
  const { fmt, svg, html } = F;
  const NNBSP = ' ';
  const MONTHS = ['JAN', 'FÉV', 'MAR', 'AVR', 'MAI', 'JUN', 'JUL', 'AOÛ', 'SEP', 'OCT', 'NOV', 'DÉC'];
  const MONTHS_LONG = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
  const SPEC = { hubs: D.simulator.hubs, infoKept: D.simulator.infoKept };
  const [LOW, HIGH] = D.simulator.interval;
  const REDUCED = F.reducedMotion;

  /* ---------- Utilitaires ---------- */

  const rupees = (x) => fmt.unit(Math.round(x), '₹');
  const rupees10 = (x) => rupees(Math.round(x / 10) * 10);
  const euros = (x, digits = 0) => fmt.unit(x / D.meta.inrPerEur, '€', digits);
  const get = (obj, path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj);
  const airportName = (code) => (D.map.airports[code] ? D.map.airports[code].name : code);
  const css = (name) => F.cssVar(name);
  const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

  const parseISO = (iso) => {
    const [y, m, d] = iso.split('-').map(Number);
    return { y, m, d };
  };
  const dateLong = (iso) => {
    const { m, d } = parseISO(iso);
    return `${d === 1 ? '1er' : d} ${MONTHS_LONG[m - 1]}`;
  };
  const dateBoard = (iso) => {
    const { m, d } = parseISO(iso);
    return `${String(d).padStart(2, '0')} ${MONTHS[m - 1]}`;
  };
  const toMinutes = (hhmm) => Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
  const durationLabel = (minutes) => {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return m ? `${h}${NNBSP}h${NNBSP}${String(m).padStart(2, '0')}` : `${h}${NNBSP}h`;
  };
  const codesOf = (route) => route.split('→').map((c) => c.trim());
  const shortRoute = (route) => {
    const via = codesOf(route).slice(1, -1);
    return via.length ? `via ${via.join(', ')}` : 'direct';
  };


  function tween(duration, onFrame, onEnd) {
    const start = performance.now();
    function frame(now) {
      const t = Math.min(1, (now - start) / duration);
      onFrame(t);
      if (t < 1) requestAnimationFrame(frame);
      else if (onEnd) onEnd();
    }
    requestAnimationFrame(frame);
  }

  /**
   * Animation à l'entrée dans l'écran, sans jamais montrer un graphique vide : un élément est
   * remis à zéro quand il approche (moins de 200 px sous l'écran, donc encore invisible) et
   * animé quand il devient visible (35 %). Un élément déjà à l'écran au chargement reste final.
   */
  function reveal(el, { reset, play }) {
    if (REDUCED || !('IntersectionObserver' in window)) return;
    let first = true;
    let armed = false;
    let done = false;
    const near = new IntersectionObserver((entries) => {
      for (const e of entries) {
        // Au chargement, seul un élément entièrement sous l'écran peut être remis à zéro
        const hidden = e.boundingClientRect.top >= innerHeight;
        if (e.isIntersecting && !armed && !done && (!first || hidden)) {
          reset();
          armed = true;
        }
      }
      first = false;
    }, { rootMargin: '0px 0px 200px 0px' });
    const visible = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting && armed && !done) {
          done = true;
          play();
          near.disconnect();
          visible.disconnect();
        }
      }
    }, { threshold: 0.35 });
    near.observe(el);
    visible.observe(el);
  }

  function newSvg(container, width, height, label) {
    container.replaceChildren();
    return svg('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': label }, container);
  }

  function setupCanvas(canvas, width, height) {
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    return ctx;
  }

  function withAlpha(color, alpha) {
    const c = color.trim();
    if (c.startsWith('#')) {
      const h = c.slice(1);
      const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
      return `rgba(${r},${g},${b},${alpha})`;
    }
    return c;
  }

  /** Étiquette surlignée en jaune (comme au surligneur sur un horaire imprimé). */
  function signalTag(parent, x, y, text, anchor = 'start') {
    const g = svg('g', { class: 'signal-tag' }, parent);
    const t = svg('text', { x, y, 'text-anchor': anchor, dy: 4, text }, g);
    const w = text.length * 7.6 + 8;
    const x0 = anchor === 'end' ? x - w + 4 : anchor === 'middle' ? x - w / 2 : x - 4;
    g.insertBefore(svg('rect', { x: x0, y: y - 9, width: w, height: 18, rx: 2 }), t);
    return g;
  }

  /* ---------- Chiffres liés au texte (data-k) ---------- */

  const BIND = {
    meta: {
      ...D.meta,
      flights: fmt.num(D.meta.flights),
      train: fmt.num(D.meta.train),
      test: fmt.num(D.meta.test),
      inrPerEur: fmt.num(D.meta.inrPerEur, 2),
      conflicts: fmt.num(D.meta.conflicts),
    },
    kpi: { ...D.kpi, MAE_EUR: euros(D.kpi.MAE, 2) },
    strip: { size: fmt.num(D.strip.rows.length) },
  };

  function bindNumbers() {
    for (const el of document.querySelectorAll('[data-k]')) {
      const value = get(BIND, el.dataset.k);
      if (value === undefined) continue;
      const text = typeof value === 'number' ? fmt.num(value) : String(value);
      el.textContent = el.dataset.unit ? `${text}${NNBSP}${el.dataset.unit}` : text;
    }
  }

  /* ---------- Tableaux des départs (en-tête et simulateur) ---------- */

  const spaced = (x) => fmt.num(Math.round(x)).replace(/\s/g, ' ');
  const BOARD_COLS = {
    dep: { width: 5, value: (r) => r.dep },
    code: { width: 5, value: (r) => r.code },
    from: { width: 3, value: (r) => r.route[0] },
    via: { width: 4, value: (r) => (r.route.length > 2 ? r.route[1] + (r.route.length > 3 ? '+' : '') : '') },
    to: { width: 3, value: (r) => r.route[r.route.length - 1] },
    date: { width: 6, value: (r) => dateBoard(r.date) },
    price: { width: 6, value: (r) => spaced(r.price), right: true },
    pred: { width: 6, value: (r) => spaced(r.pred), right: true, yellow: true },
  };
  const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  const DIGITS = '0123456789';

  /** Ajoute une ligne de cases ; renvoie les cases (texte final et colonne) pour l'animation. */
  function boardRow(tbody, row, keys, { prepend = false } = {}) {
    const tr = html('tr', {});
    if (prepend) tbody.prepend(tr);
    else tbody.append(tr);
    const cells = [];
    keys.forEach((key, column) => {
      const col = BOARD_COLS[key];
      const raw = col.value(row);
      const text = col.right ? raw.padStart(col.width) : raw.padEnd(col.width);
      const td = html('td', { 'data-col': key, class: col.right ? 'is-num' : null, 'aria-label': raw.trim() || '–' }, tr);
      const group = html('span', { class: `flaps${col.yellow ? ' flaps--yellow' : ''}`, 'aria-hidden': 'true' }, td);
      for (const ch of text) {
        const blank = ch === ' ';
        const cell = html('span', { class: `flap${blank ? ' flap--blank' : ''}`, text: blank ? ' ' : ch }, group);
        cells.push({ cell, final: ch, column, key });
      }
    });
    return { tr, cells };
  }

  /** Animation « split-flap » : chaque case défile quelques caractères puis se fige. */
  function flip(cells, { stagger = 2, spread = 5 } = {}) {
    if (REDUCED) {
      for (const c of cells) setFlap(c.cell, c.final);
      return;
    }
    const plan = cells.map((c) => ({ ...c, steps: 3 + c.column * stagger + Math.floor(Math.random() * spread) }));
    let tick = 0;
    const timer = setInterval(() => {
      tick += 1;
      let busy = false;
      for (const p of plan) {
        if (tick < p.steps && /[A-Z0-9]/.test(p.final)) {
          const pool = /\d/.test(p.final) ? DIGITS : LETTERS;
          setFlap(p.cell, pool[Math.floor(Math.random() * pool.length)]);
          busy = true;
        } else {
          setFlap(p.cell, p.final);
        }
      }
      if (!busy) clearInterval(timer);
    }, 45);
  }

  function setFlap(cell, ch) {
    const blank = ch === ' ';
    cell.classList.toggle('flap--blank', blank);
    cell.textContent = blank ? ' ' : ch;
  }

  function renderLeadBoard() {
    const tbody = document.querySelector('#board-table tbody');
    tbody.replaceChildren();
    const keys = ['dep', 'code', 'from', 'via', 'to', 'date', 'price', 'pred'];
    const all = [];
    for (const row of D.board) {
      const { tr, cells } = boardRow(tbody, row, keys);
      const gap = (row.pred - row.price) / row.price;
      html('td', { 'data-col': 'gap', class: 'gap is-num', text: (gap > 0 ? '+' : '') + fmt.pct(gap, 1) }, tr);
      all.push(...cells);
    }
    flip(all);
  }

  /* ---------- Le réseau : texte, horaire et carte ---------- */

  const mapState = { pair: null };
  const pairKey = (p) => `${p.from}-${p.to}`;

  function renderNetworkText() {
    const top = D.map.pairs[0];
    const topAirlines = D.simulator.pairs.find((p) => p.source === top.fromName && p.destination === top.toName).airlines.length;
    const direct = D.strip.groups.stops[0];
    const bom = D.map.hubs.find((h) => h.code === 'BOM');
    const host = document.getElementById('network-text');
    host.replaceChildren();
    html('p', { text: `Les ${fmt.num(D.meta.flights)} vols relient cinq paires de villes. ${top.fromName} → ${top.toName} en rassemble à lui seul ${fmt.num(top.n)}, vendus par ${topAirlines} compagnies sur ${top.routes.length} itinéraires principaux.` }, host);
    html('p', { text: `Seul un vol sur trois est direct (${fmt.pct(direct.n / D.meta.flights)}). Près de la moitié des vols, ${fmt.pct(bom.n / D.meta.flights)}, font escale à Mumbai, la plaque tournante de Jet Airways.` }, host);
  }

  function renderTimetable() {
    const tbody = document.querySelector('#timetable tbody');
    tbody.replaceChildren();
    for (const p of D.map.pairs) {
      const selected = mapState.pair === pairKey(p);
      const tr = html('tr', { 'data-pair': pairKey(p), tabindex: 0, 'aria-selected': String(selected) }, tbody);
      const td = html('td', {}, tr);
      html('span', { class: 'codes', text: `${p.from} → ${p.to}` }, td);
      html('span', { class: 'names', text: `${p.fromName} → ${p.toName}` }, td);
      html('td', { class: 'is-num', text: fmt.num(p.n) }, tr);
      html('td', { class: 'is-num', text: rupees(p.median) }, tr);
      const choose = () => selectPair(pairKey(p));
      tr.addEventListener('click', choose);
      tr.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          choose();
        }
      });
    }
  }

  function selectPair(key) {
    mapState.pair = mapState.pair === key ? null : key;
    renderTimetable();
    renderMap(false);
  }

  function curveGeom(a, b, bend) {
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const cx = mx - (b.y - a.y) * bend;
    const cy = my + (b.x - a.x) * bend;
    const at = (t) => ({
      x: (1 - t) ** 2 * a.x + 2 * (1 - t) * t * cx + t ** 2 * b.x,
      y: (1 - t) ** 2 * a.y + 2 * (1 - t) * t * cy + t ** 2 * b.y,
    });
    return { d: `M${a.x},${a.y}Q${cx},${cy} ${b.x},${b.y}`, at, side: Math.sign(cx - mx) || 1 };
  }

  const PLANE = 'M16 0 C16 -1.4 14.6 -2 13.2 -2 L5 -2 L-3 -11 L-6 -11 L-1.5 -2 L-9 -2 L-12 -5.5 L-14.5 -5.5 L-12.5 0 L-14.5 5.5 L-12 5.5 L-9 2 L-1.5 2 L-6 11 L-3 11 L5 2 L13.2 2 C14.6 2 16 1.4 16 0 Z';

  // Décalage (en pixels à l'écran) des étiquettes de liaison : vers l'extérieur de l'arc
  const OD_LABEL = {
    'DEL-COK': { t: 0.42, dx: -16, dy: 0, anchor: 'end' },
    'CCU-BLR': { t: 0.5, dx: 14, dy: 6, anchor: 'start' },
    'BLR-DEL': { t: 0.55, dx: 14, dy: 0, anchor: 'start' },
    'BOM-HYD': { t: 0.55, dx: 0, dy: 28, anchor: 'middle' },
    'MAA-CCU': { t: 0.5, dx: 14, dy: 8, anchor: 'start' },
  };

  function renderMap(animate) {
    const host = document.getElementById('map');
    const { width, height, outline, airports, hubs, pairs } = D.map;
    const k = width / Math.max(280, host.clientWidth || 600); // unités SVG par pixel affiché
    const px = (v) => v * k;
    const compact = host.clientWidth < 480;
    const root = newSvg(host, width, height, 'Carte des liaisons et des escales des vols intérieurs étudiés');
    const defs = svg('defs', {}, root);
    const marker = svg('marker', { id: 'arrow', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' }, defs);
    svg('path', { class: 'arrow', d: 'M0,1 L9,5 L0,9 Z' }, marker);
    svg('path', { class: 'land', d: outline, style: { strokeWidth: px(1) } }, root);

    // Itinéraires détaillés de la liaison choisie
    const legLayer = svg('g', {}, root);
    const chosen = pairs.find((p) => pairKey(p) === mapState.pair);
    if (chosen) {
      const legs = new Map();
      for (const r of chosen.routes) {
        for (let i = 0; i < r.codes.length - 1; i += 1) {
          const key = `${r.codes[i]}-${r.codes[i + 1]}`;
          legs.set(key, (legs.get(key) || 0) + r.n);
        }
      }
      const maxLeg = Math.max(...legs.values());
      for (const [key, n] of legs) {
        const [a, b] = key.split('-').map((c) => airports[c]);
        if (!a || !b) continue;
        svg('path', { class: 'leg', d: curveGeom(a, b, 0.1).d, style: { strokeWidth: px(1 + 7 * Math.sqrt(n / maxLeg)) } }, legLayer);
      }
    }

    // Escales : cercle proportionnel au nombre de vols qui y font escale
    const maxHub = Math.max(...hubs.map((h) => h.n));
    const hubN = new Map(hubs.map((h) => [h.code, h.n]));
    const hubLayer = svg('g', {}, root);
    for (const h of hubs) {
      const a = airports[h.code];
      if (!a || h.n < 20) continue;
      const c = svg('circle', { class: 'hub mark', cx: a.x, cy: a.y, r: px(2.5 + 15 * Math.sqrt(h.n / maxHub)), style: { strokeWidth: px(1.2) } }, hubLayer);
      F.hover(c, () => ({ title: `${a.name} (${h.code})`, rows: [{ value: `${fmt.num(h.n)} vols`, label: 'y font escale' }] }), { label: `${a.name}, escale de ${fmt.num(h.n)} vols` });
    }

    // Liaisons ville à ville, avec flèche d'arrivée et étiquette
    const odLayer = svg('g', {}, root);
    const labelLayer = svg('g', {}, root);
    const arcs = [];
    for (const p of pairs) {
      const a = airports[p.from];
      const b = airports[p.to];
      const geom = curveGeom(a, b, 0.2);
      const key = pairKey(p);
      const on = mapState.pair === key;
      const dim = mapState.pair && !on;
      const path = svg('path', { class: `od${dim ? ' is-dim' : ''}`, d: geom.d, 'marker-end': 'url(#arrow)', style: { strokeWidth: px(on ? 3.5 : 2.5) } }, odLayer);
      const hit = svg('path', { class: 'od-hit mark', d: geom.d, style: { strokeWidth: px(22) } }, odLayer);
      F.hover(hit, () => ({
        title: `${p.fromName} → ${p.toName}`,
        rows: [
          { value: rupees(p.median), label: 'prix médian' },
          { value: `${rupees(p.q1)} – ${rupees(p.q3)}`, label: 'moitié des billets' },
          { value: `${fmt.num(p.n)} vols`, label: `${p.routes.length} itinéraires principaux` },
        ],
      }), { label: `${p.fromName} vers ${p.toName}, ${fmt.num(p.n)} vols, prix médian ${rupees(p.median)}` });
      hit.addEventListener('click', () => selectPair(key));
      hit.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          selectPair(key);
        }
      });
      const spec = compact ? { t: 0.5, dx: 0, dy: -6, anchor: 'middle' } : OD_LABEL[key] || { t: 0.5, dx: 14, dy: 0, anchor: 'start' };
      const at = geom.at(spec.t);
      const lx = at.x + px(spec.dx);
      const ly = at.y + px(spec.dy);
      const label = svg('g', { opacity: dim ? 0.3 : 1 }, labelLayer);
      svg('text', { class: 'chart-num chart-label--halo', x: lx, y: ly, 'text-anchor': spec.anchor, text: `${p.from} → ${p.to}`, style: { fontSize: `${px(13)}px`, strokeWidth: `${px(4)}px` } }, label);
      if (!compact) svg('text', { class: 'chart-label chart-label--ink chart-label--halo', x: lx, y: ly + px(15), 'text-anchor': spec.anchor, text: `${fmt.num(p.n)} vols · ${rupees(p.median)}`, style: { fontSize: `${px(11.5)}px`, strokeWidth: `${px(4)}px` } }, label);
      arcs.push({ path, label, geom, width: px(on ? 3.5 : 2.5) });
    }

    // Villes desservies et principales escales
    const cityLayer = svg('g', {}, root);
    const cities = new Set(D.map.cities);
    for (const [code, a] of Object.entries(airports)) {
      const isCity = cities.has(code);
      const n = hubN.get(code) || 0;
      if (isCity) svg('circle', { class: 'city', cx: a.x, cy: a.y, r: px(4.5), style: { strokeWidth: px(1.5) } }, cityLayer);
      if (isCity || (n >= 200 && !compact)) {
        const east = ['CCU', 'HYD', 'MAA'].includes(code);
        svg('text', {
          class: `code${isCity ? '' : ' code--hub'}`,
          x: a.x + px(east ? 8 : -8),
          y: a.y + px(4),
          'text-anchor': east ? 'start' : 'end',
          text: code,
          style: { fontSize: `${px(isCity ? 12.5 : 11)}px`, strokeWidth: `${px(3.5)}px` },
        }, cityLayer);
      }
    }

    // Annotation : la plaque tournante, posée en mer d'Arabie (écrans larges)
    const bom = airports.BOM;
    const note = svg('g', { display: compact ? 'none' : null }, root);
    const nx = px(10);
    const ny = bom.y + px(118);
    svg('line', { class: 'baseline', x1: bom.x - px(12), y1: bom.y + px(12), x2: nx + px(40), y2: ny - px(18), style: { strokeWidth: px(1) } }, note);
    [['Mumbai', 'chart-label--strong'], [`${fmt.num(hubN.get('BOM'))} vols`, 'chart-label--ink'], ['y font escale', 'chart-label--ink']].forEach(([text, cls], i) => {
      svg('text', { class: `chart-label ${cls} chart-label--halo`, x: nx, y: ny + px(15 * i), text, style: { fontSize: `${px(11.5)}px`, strokeWidth: `${px(4)}px` } }, note);
    });

    if (animate) {
      reveal(host, {
        reset: () => {
          for (const arc of arcs) {
            const len = arc.path.getTotalLength();
            arc.path.style.strokeDasharray = `${len}`;
            arc.path.style.strokeDashoffset = `${len}`;
            arc.path.setAttribute('marker-end', '');
            arc.label.style.opacity = '0';
          }
        },
        play: () => flyArcs(root, arcs, k),
      });
    }
  }

  /** Les liaisons se tracent derrière un avion qui suit chaque arc. */
  function flyArcs(root, arcs, k) {
    arcs.forEach((arc, i) => {
      const len = arc.path.getTotalLength();
      const plane = svg('path', { class: 'plane', d: PLANE, opacity: 0 }, root);
      setTimeout(() => {
        plane.setAttribute('opacity', 1);
        tween(1500, (t) => {
          const k = ease(t);
          arc.path.style.strokeDashoffset = `${len * (1 - k)}`;
          const p = arc.path.getPointAtLength(len * k);
          const q = arc.path.getPointAtLength(Math.min(len, len * k + 1));
          const angle = (Math.atan2(q.y - p.y, q.x - p.x) * 180) / Math.PI;
          plane.setAttribute('transform', `translate(${p.x},${p.y}) rotate(${angle}) scale(${0.75 * k})`);
        }, () => {
          arc.path.style.strokeDasharray = '';
          arc.path.style.strokeDashoffset = '';
          arc.path.setAttribute('marker-end', 'url(#arrow)');
          plane.remove();
          arc.label.style.transition = 'opacity 400ms ease';
          arc.label.style.opacity = '1';
        });
      }, i * 350);
    });
  }

  /* ---------- Ce qui fait le prix : nuage de points et défilement ---------- */

  const G = D.strip.groups;
  const STEPS = [
    {
      key: null,
      title: `${rupees(D.strip.overall.median)}, le prix médian d'un billet`,
      text: `Soit ${euros(D.strip.overall.median)} au taux de 2019. Les prix vont de ${rupees(D.strip.overall.min)} à ${rupees(D.strip.overall.max)}, un rapport de 1 à ${Math.round(D.strip.overall.max / D.strip.overall.min)}.`,
      emphasis: [],
    },
    {
      key: 'stops',
      title: 'Une escale double le prix',
      text: `Un vol direct coûte ${rupees(G.stops[0].median)} en médiane. Avec une escale, ${rupees(G.stops[1].median)} ; avec deux, ${rupees(G.stops[2].median)}.`,
      emphasis: [0, 1],
    },
    {
      key: 'airline',
      title: 'La compagnie pèse autant que l\'itinéraire',
      text: `${G.airline[0].label} vend ses billets ${rupees(G.airline[0].median)} en médiane, ${G.airline[G.airline.length - 1].label} ${rupees(G.airline[G.airline.length - 1].median)}, près de trois fois plus. Les compagnies à bas coût restent toutes sous ${rupees(Math.ceil(G.airline[3].median / 100) * 100)}.`,
      emphasis: [0, G.airline.length - 1],
    },
    {
      key: 'duration',
      title: 'Plus le trajet est long, plus il coûte',
      text: `Moins de 3${NNBSP}h de trajet : ${rupees(G.duration[0].median)}. Entre 20 et 30${NNBSP}h : ${rupees(G.duration[5].median)}. Un trajet long comporte des escales et passe souvent par une compagnie chère.`,
      emphasis: [0, 5],
    },
    {
      key: 'period',
      title: 'Les vols de début mars coûtent le plus cher',
      text: `Les vols du 1er au 9 mars coûtent ${rupees(G.period[0].median)} en médiane, ${fmt.num(G.period[0].median / G.period[2].median, 1)} fois plus que ceux d'avril (${rupees(G.period[2].median)}). Les prix ont sans doute été relevés début mars, quand ces billets se vendaient à quelques jours du départ.`,
      emphasis: [0, 2],
    },
  ];

  const strip = { step: 0, positions: null, canvas: null, overlay: null, width: 0, height: 0, raf: 0 };

  function jitter(i) {
    const s = Math.sin(i * 12.9898) * 43758.5453;
    return s - Math.floor(s) - 0.5;
  }

  function stripLayout(stepIndex) {
    const step = STEPS[stepIndex];
    const { width, height } = strip;
    const narrow = width < 520;
    const m = { left: narrow ? 100 : 150, right: 18, top: 8, bottom: 30 };
    const x = F.scaleLinear([0, 25000], [m.left, width - m.right]);
    const groups = step.key ? G[step.key] : [{ label: 'Tous les vols', median: D.strip.overall.median }];
    const keyIndex = step.key ? D.strip.keys.indexOf(step.key) + 1 : -1;
    const rowH = (height - m.top - m.bottom) / groups.length;
    const spread = Math.min(rowH * 0.62, 260);
    const positions = D.strip.rows.map((row, i) => {
      const g = keyIndex > 0 ? row[keyIndex] : 0;
      return { x: x(Math.min(row[0], 25000)) + jitter(i * 3 + 1) * 3, y: m.top + rowH * (g + 0.5) + jitter(i) * spread };
    });
    return { m, x, groups, rowH, positions, narrow };
  }

  function drawStrip(positions) {
    const ctx = strip.ctx;
    const { width, height } = strip;
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = withAlpha(css('--mark'), 0.32);
    const r = width < 520 ? 1.7 : 2.2;
    for (const p of positions) {
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function drawStripOverlay(layout, stepIndex) {
    const step = STEPS[stepIndex];
    const { width, height } = strip;
    const root = newSvg(strip.overlayHost, width, height, step.title);
    root.setAttribute('aria-hidden', 'true');
    const { m, x, groups, rowH, narrow } = layout;
    const ticks = narrow ? [0, 10000, 20000] : [0, 5000, 10000, 15000, 20000, 25000];
    const grid = svg('g', { class: 'grid' }, root);
    const axis = svg('g', { class: 'axis' }, root);
    for (const t of ticks) {
      svg('line', { x1: x(t), x2: x(t), y1: m.top, y2: height - m.bottom }, grid);
      svg('text', { x: x(t), y: height - m.bottom + 18, 'text-anchor': 'middle', text: t === 25000 ? '25 000 ₹ et +' : fmt.num(t) }, axis);
    }
    groups.forEach((g, i) => {
      const cy = m.top + rowH * (i + 0.5);
      if (groups.length > 1) {
        svg('line', { class: 'baseline', x1: m.left - 6, x2: width - m.right, y1: m.top + rowH * (i + 1), y2: m.top + rowH * (i + 1), opacity: 0.6 }, root);
      }
      svg('text', { class: 'chart-label chart-label--ink', x: m.left - 12, y: cy + 4, 'text-anchor': 'end', text: g.label }, root);
      const half = Math.min(rowH * 0.4, 120);
      svg('line', { x1: x(g.median), x2: x(g.median), y1: cy - half, y2: cy + half, stroke: css('--ink'), 'stroke-width': 2 }, root);
      const emphasized = step.key === null || step.emphasis.includes(i);
      const label = rupees(g.median);
      if (emphasized) signalTag(root, x(g.median) + 8, cy - half + 10, label);
      else svg('text', { class: 'chart-num chart-label--halo', x: x(g.median) + 8, y: cy - half + 14, text: label }, root);
    });
  }

  function renderStrip(animateFrom) {
    const host = document.getElementById('strip');
    const width = Math.round(host.clientWidth);
    const height = Math.round(host.clientHeight);
    if (!width || !height) return;
    if (!strip.canvas) {
      strip.canvas = html('canvas', {}, host);
      strip.overlayHost = html('div', { style: { position: 'absolute', inset: '0' } }, host);
    }
    strip.width = width;
    strip.height = height;
    strip.ctx = setupCanvas(strip.canvas, width, height);
    const layout = stripLayout(strip.step);
    drawStripOverlay(layout, strip.step);
    cancelAnimationFrame(strip.raf);
    if (!animateFrom || REDUCED) {
      strip.positions = layout.positions;
      drawStrip(layout.positions);
      return;
    }
    const from = animateFrom;
    const to = layout.positions;
    const start = performance.now();
    const duration = 900;
    const frame = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const k = ease(t);
      const current = to.map((p, i) => ({ x: from[i].x + (p.x - from[i].x) * k, y: from[i].y + (p.y - from[i].y) * k }));
      drawStrip(current);
      strip.positions = current;
      if (t < 1) strip.raf = requestAnimationFrame(frame);
    };
    strip.raf = requestAnimationFrame(frame);
  }

  function initSteps() {
    const host = document.getElementById('steps');
    host.replaceChildren();
    STEPS.forEach((s, i) => {
      const step = html('div', { class: `step${i === 0 ? ' is-active' : ''}`, 'data-index': i }, host);
      html('h3', { text: s.title }, step);
      html('p', { text: s.text }, step);
    });
    const steps = [...host.children];
    const observer = new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        const index = Number(e.target.dataset.index);
        if (index === strip.step) continue;
        steps.forEach((el) => el.classList.toggle('is-active', el === e.target));
        const from = strip.positions;
        strip.step = index;
        renderStrip(from);
      }
    }, { rootMargin: '-45% 0px -45% 0px' });
    steps.forEach((el) => observer.observe(el));
  }

  /* ---------- Le modèle : classement, nuage, détails ---------- */

  const METRICS = [
    { key: 'MAE', label: 'MAE', title: 'Erreur absolue moyenne de chaque modèle (validation croisée)', better: 'low' },
    { key: 'RMSE', label: 'RMSE', title: 'RMSE de chaque modèle, qui pénalise les grosses erreurs', better: 'low' },
    { key: 'R2', label: 'R²', title: 'Part de la variance des prix expliquée (R²)', better: 'high' },
  ];
  const CHOSEN = 'Gradient boosting';
  const board = { metric: 0, bars: null };

  function metricValue(metric, v) {
    return metric.key === 'R2' ? fmt.num(v, 3) : rupees(v);
  }

  function leaderboardLayout(metricIndex, width) {
    const metric = METRICS[metricIndex];
    const rows = D.models.cv.slice().sort((a, b) => (metric.better === 'low' ? a[metric.key] - b[metric.key] : b[metric.key] - a[metric.key]));
    const narrow = width < 520;
    const labelW = narrow ? 118 : 170;
    const rowH = 46;
    const top = 6;
    const height = top + rows.length * rowH + 26;
    const lo = metric.key === 'R2' ? Math.min(0, ...rows.map((r) => r.R2)) : 0;
    const hi = metric.key === 'R2' ? 1 : F.niceDomain(0, Math.max(...rows.map((r) => r[metric.key] + (r[`${metric.key}_sd`] || 0))), 4)[1];
    const x = F.scaleLinear([lo, hi], [labelW, width - (narrow ? 72 : 96)]);
    const order = new Map(rows.map((r, i) => [r.model, i]));
    return { metric, rows, labelW, rowH, top, height, x, lo, hi, order, narrow };
  }

  /** Géométrie en pixels d'une barre pour un état (position, valeur, écart-type). */
  function barGeometry(L, r) {
    const v = r[L.metric.key];
    const sd = r[`${L.metric.key}_sd`] || 0;
    return {
      y: L.top + L.order.get(r.model) * L.rowH + L.rowH / 2,
      x0: L.x(Math.min(0, v)),
      x1: L.x(Math.max(0, v)),
      e0: L.x(v - sd),
      e1: L.x(v + sd),
      label: Math.max(L.x(v + sd), L.x(0)) + 8,
      text: metricValue(L.metric, v),
      sd,
    };
  }

  function applyBar(b, g) {
    b.bar.setAttribute('x', g.x0);
    b.bar.setAttribute('y', g.y - 11);
    b.bar.setAttribute('width', Math.max(0, g.x1 - g.x0));
    b.name.setAttribute('y', g.y + 4);
    b.err.setAttribute('x1', g.e0);
    b.err.setAttribute('x2', g.e1);
    b.err.setAttribute('y1', g.y);
    b.err.setAttribute('y2', g.y);
    b.err.setAttribute('opacity', g.sd ? 1 : 0);
    b.value.setAttribute('x', g.label);
    b.value.setAttribute('y', g.y + 4);
    b.value.textContent = g.text;
    b.geometry = g;
  }

  const mix = (a, b, k) => {
    const out = { ...b };
    for (const key of ['y', 'x0', 'x1', 'e0', 'e1', 'label']) out[key] = a[key] + (b[key] - a[key]) * k;
    return out;
  };

  function renderLeaderboard(from) {
    const host = document.getElementById('leaderboard');
    const width = Math.max(300, host.clientWidth);
    const L = leaderboardLayout(board.metric, width);
    document.getElementById('leaderboard-title').textContent = L.metric.title;
    const root = newSvg(host, width, L.height, L.metric.title);
    const grid = svg('g', { class: 'grid' }, root);
    const axis = svg('g', { class: 'axis' }, root);
    for (const t of F.niceTicks(L.lo, L.hi, L.narrow ? 3 : 5)) {
      svg('line', { x1: L.x(t), x2: L.x(t), y1: L.top, y2: L.top + L.rows.length * L.rowH }, grid);
      svg('text', { x: L.x(t), y: L.height - 4, 'text-anchor': 'middle', text: L.metric.key === 'R2' ? fmt.num(t, 1) : fmt.num(t) }, axis);
    }
    svg('line', { class: 'baseline', x1: L.x(0), x2: L.x(0), y1: L.top, y2: L.top + L.rows.length * L.rowH }, root);
    const bars = new Map();
    for (const r of D.models.cv) {
      const chosen = r.model === CHOSEN;
      const g = svg('g', {}, root);
      const name = svg('text', { class: `chart-label ${chosen ? 'chart-label--strong' : 'chart-label--ink'}`, x: L.labelW - 12, 'text-anchor': 'end', text: r.model }, g);
      const bar = svg('rect', { class: `${chosen ? 'm-signal' : 'm-mark-2'} mark`, height: 22, rx: 2 }, g);
      const err = svg('line', { stroke: css('--ink-2'), 'stroke-width': 1 }, g);
      const value = svg('text', { class: 'chart-num' }, g);
      F.hover(bar, () => ({
        title: r.model,
        rows: [
          { value: rupees(r.MAE), label: 'MAE' },
          { value: rupees(r.RMSE), label: 'RMSE' },
          { value: fmt.pct(r.MAPE, 1), label: 'erreur relative (MAPE)' },
          { value: fmt.num(r.R2, 3), label: 'R²' },
        ],
        note: 'Validation croisée à 5 plis',
      }), { label: `${r.model} : ${L.metric.label} ${metricValue(L.metric, r[L.metric.key])}` });
      const b = { r, name, bar, err, value, target: barGeometry(L, r) };
      applyBar(b, b.target);
      bars.set(r.model, b);
    }
    board.bars = bars;
    board.zero = L.x(0);
    if (from && !REDUCED) {
      tween(600, (t) => {
        const k = ease(t);
        for (const b of bars.values()) applyBar(b, mix(from.get(b.r.model), b.target, k));
      });
    }
    renderChoiceText();
  }

  function growLeaderboard() {
    const host = document.getElementById('leaderboard');
    const empty = (g) => ({ ...g, x0: board.zero, x1: board.zero, e0: board.zero, e1: board.zero, label: board.zero + 8 });
    reveal(host, {
      reset: () => {
        for (const b of board.bars.values()) applyBar(b, empty(b.target));
      },
      play: () => {
        const bars = [...board.bars.values()];
        tween(1000, (t) => {
          bars.forEach((b, i) => {
            const k = ease(Math.max(0, Math.min(1, t * 1.6 - i * 0.12)));
            applyBar(b, mix(empty(b.target), b.target, k));
          });
        }, () => bars.forEach((b) => applyBar(b, b.target)));
      },
    });
  }

  function initMetricControls() {
    const seg = document.getElementById('metric-seg');
    METRICS.forEach((m, i) => {
      const b = html('button', { type: 'button', 'aria-pressed': String(i === board.metric), text: m.label }, seg);
      b.addEventListener('click', () => {
        if (i === board.metric) return;
        const from = new Map([...board.bars.values()].map((bar) => [bar.r.model, bar.geometry]));
        board.metric = i;
        for (const other of seg.children) other.setAttribute('aria-pressed', String(other === b));
        renderLeaderboard(from);
      });
    });
  }

  function renderChoiceText() {
    const rf = D.models.test.find((r) => r.model === 'Forêt aléatoire');
    const host = document.getElementById('choice-text');
    host.replaceChildren();
    html('p', { text: `Forêt aléatoire et gradient boosting sont au coude à coude. Le gradient boosting, en jaune, est retenu parce que sa RMSE est la plus basse, donc qu'il fait moins de grosses erreurs, et que ses ${D.meta.trees} arbres (${fmt.num(D.meta.nodes.gb)} nœuds) tiennent dans un navigateur, quand la forêt en compte ${fmt.num(D.meta.nodes.rf)}. Sur le test, la forêt garde une erreur moyenne plus faible (${rupees(rf.MAE)} contre ${rupees(D.kpi.MAE)}) mais commet de plus gros écarts (RMSE de ${rupees(rf.RMSE)} contre ${rupees(D.kpi.RMSE)}).` }, host);
  }

  const cloud = { points: null };

  function cloudLayout(size) {
    const m = { left: 58, right: 14, top: 12, bottom: 40 };
    const lo = Math.log10(1500);
    const hi = Math.log10(56000);
    const plot = size - m.left - m.right;
    const s = F.scaleLinear([lo, hi], [0, plot]);
    return { m, plot, x: (v) => m.left + s(Math.log10(v)), y: (v) => m.top + plot - s(Math.log10(v)), lo: 10 ** lo, hi: 10 ** hi };
  }

  function renderCloud() {
    const host = document.getElementById('cloud');
    const size = Math.round(Math.min(host.parentElement.clientWidth, 560));
    if (!size) return;
    host.replaceChildren();
    host.style.maxWidth = `${size}px`;
    const canvas = html('canvas', {}, host);
    const overlay = html('div', { style: { position: 'absolute', inset: '0' } }, host);
    const ctx = setupCanvas(canvas, size, size);
    const L = cloudLayout(size);
    const { actual, pred, reference } = D.cloud;
    const root = newSvg(overlay, size, size, 'Prix prédit contre prix réel pour les vols du jeu de test');
    const grid = svg('g', { class: 'grid' }, root);
    const axis = svg('g', { class: 'axis' }, root);
    for (const t of [2000, 5000, 10000, 20000, 50000]) {
      svg('line', { x1: L.x(t), x2: L.x(t), y1: L.m.top, y2: L.m.top + L.plot }, grid);
      svg('line', { x1: L.m.left, x2: L.m.left + L.plot, y1: L.y(t), y2: L.y(t) }, grid);
      svg('text', { x: L.x(t), y: L.m.top + L.plot + 18, 'text-anchor': 'middle', text: fmt.compact(t) }, axis);
      svg('text', { x: L.m.left - 8, y: L.y(t) + 4, 'text-anchor': 'end', text: fmt.compact(t) }, axis);
    }
    svg('text', { class: 'chart-label', x: L.m.left + L.plot, y: size - 4, 'text-anchor': 'end', text: 'prix réel (₹)' }, root);
    svg('text', { class: 'chart-label', x: L.m.left + 8, y: L.y(36000), text: 'prix prédit (₹)' }, root);
    svg('line', { x1: L.x(L.lo), y1: L.y(L.lo), x2: L.x(L.hi), y2: L.y(L.hi), stroke: css('--ink-2'), 'stroke-width': 1 }, root);
    svg('text', { class: 'chart-label chart-label--ink', x: L.x(30000), y: L.y(30000) - 10, 'text-anchor': 'end', text: 'prédiction parfaite' }, root);
    svg('line', { x1: L.x(L.lo), y1: L.y(reference), x2: L.x(L.hi), y2: L.y(reference), stroke: css('--mark-2'), 'stroke-width': 1.5, 'stroke-dasharray': '4 4' }, root);
    svg('text', { class: 'chart-label chart-label--ink', x: L.x(L.hi) - 2, y: L.y(reference) + 16, 'text-anchor': 'end', text: `référence : ${rupees(reference)} pour tous` }, root);

    const final = actual.map((a, i) => ({ x: L.x(a), y: L.y(pred[i]) }));
    const start = actual.map((a) => ({ x: L.x(a), y: L.y(reference) }));
    const yellow = withAlpha(css('--signal'), 0.6);
    const draw = (points) => {
      ctx.clearRect(0, 0, size, size);
      ctx.fillStyle = yellow;
      for (const p of points) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 2.3, 0, Math.PI * 2);
        ctx.fill();
      }
    };
    draw(final);
    cloud.points = final;

    // Survol : le point le plus proche
    const hit = svg('rect', { class: 'hit', x: L.m.left, y: L.m.top, width: L.plot, height: L.plot }, root);
    hit.addEventListener('pointermove', (e) => {
      const box = root.getBoundingClientRect();
      const px = ((e.clientX - box.left) / box.width) * size;
      const py = ((e.clientY - box.top) / box.height) * size;
      let best = -1;
      let dist = 144;
      final.forEach((p, i) => {
        const d = (p.x - px) ** 2 + (p.y - py) ** 2;
        if (d < dist) {
          dist = d;
          best = i;
        }
      });
      if (best < 0) return F.tip.hide();
      const gap = (pred[best] - actual[best]) / actual[best];
      F.tip.show(e, {
        rows: [
          { value: rupees(actual[best]), label: 'prix réel' },
          { value: rupees(pred[best]), label: 'prix prédit', color: css('--signal'), kind: 'dot' },
          { value: (gap > 0 ? '+' : '') + fmt.pct(gap, 1), label: 'écart' },
        ],
      });
    });
    hit.addEventListener('pointerleave', () => F.tip.hide());

    const ref = D.models.test.find((r) => r.model === 'Référence (médiane)');
    const text = document.getElementById('cloud-text');
    text.replaceChildren();
    html('p', { text: `Le modèle de référence prédit ${rupees(reference)} pour chaque vol (ligne pointillée) et se trompe de ${rupees(ref.MAE)} en moyenne. Le gradient boosting ramène les points près de la diagonale. Pour 80 % des vols, le prix réel se situe entre ${fmt.pct(LOW - 1)} et +${fmt.pct(HIGH - 1)} du prix prédit, et le R² atteint ${fmt.num(D.kpi.R2, 2)}.` }, text);

    reveal(host, {
      reset: () => draw(start),
      play: () => tween(1600, (t) => {
        draw(final.map((p, i) => {
          const k = ease(Math.max(0, Math.min(1, t * 1.5 - (p.x / size) * 0.5)));
          return { x: p.x, y: start[i].y + (p.y - start[i].y) * k };
        }));
      }, () => draw(final)),
    });
  }

  function renderDetails() {
    const host = document.getElementById('importance');
    const rows = D.models.importance;
    const width = Math.max(300, host.clientWidth);
    const labelW = width < 420 ? 128 : 170;
    const rowH = 30;
    const height = rows.length * rowH + 28;
    const root = newSvg(host, width, height, 'Importance des variables par permutation');
    const max = F.niceDomain(0, Math.max(...rows.map((r) => r.value + r.sd)), 4)[1];
    const x = F.scaleLinear([0, max], [labelW, width - 70]);
    const grid = svg('g', { class: 'grid' }, root);
    const axis = svg('g', { class: 'axis' }, root);
    for (const t of F.niceTicks(0, max, width < 420 ? 2 : 4)) {
      svg('line', { x1: x(t), x2: x(t), y1: 0, y2: rows.length * rowH }, grid);
      svg('text', { x: x(t), y: height - 4, 'text-anchor': 'middle', text: fmt.num(t) }, axis);
    }
    rows.forEach((r, i) => {
      const cy = i * rowH + rowH / 2;
      svg('text', { class: 'chart-label chart-label--ink', x: labelW - 10, y: cy + 4, 'text-anchor': 'end', text: r.feature }, root);
      svg('rect', { class: 'm-mark-2', x: x(0), y: cy - 8, width: x(r.value) - x(0), height: 16, rx: 2 }, root);
      svg('text', { class: 'chart-num', x: x(r.value) + 8, y: cy + 4, text: `+${rupees(r.value)}` }, root);
    });
    const tables = [
      ['leaderboard-table', 'Scores en validation croisée', D.models.cv],
      ['test-table', 'Scores sur le jeu de test', D.models.test],
    ];
    for (const [id, summary, data] of tables) {
      const el = document.getElementById(id);
      el.replaceChildren();
      F.dataTable(el, {
        summary,
        caption: summary,
        columns: [
          { key: 'model', label: 'Modèle' },
          { key: 'MAE', label: 'MAE', num: true, format: rupees },
          { key: 'RMSE', label: 'RMSE', num: true, format: rupees },
          { key: 'MAPE', label: 'MAPE', num: true, format: (v) => fmt.pct(v, 1) },
          { key: 'R2', label: 'R²', num: true, format: (v) => fmt.num(v, 3) },
        ],
        rows: data,
      });
    }
    const imp = document.getElementById('importance-table');
    imp.replaceChildren();
    F.dataTable(imp, {
      summary: 'Importance des variables',
      caption: 'Importance des variables',
      columns: [
        { key: 'feature', label: 'Variable' },
        { key: 'value', label: 'Hausse de la MAE', num: true, format: rupees },
        { key: 'sd', label: '± é.-t.', num: true, format: (v) => fmt.num(v) },
      ],
      rows,
    });
  }

  /* ---------- Simulateur ---------- */

  const sim = { pairs: D.simulator.pairs.slice().sort((a, b) => volume(b) - volume(a)), info: 'No info', cabin: 'Economy', current: null };

  function volume(pair) {
    return pair.airlines.reduce((s, a) => s + a.routes.reduce((t, r) => t + r.n, 0), 0);
  }

  function fillSelect(select, items, label) {
    select.replaceChildren();
    items.forEach((it, i) => html('option', { value: String(i), text: label(it) }, select));
  }

  function setSeg(host, options, current, onPick) {
    host.replaceChildren();
    for (const opt of options) {
      const b = html('button', { type: 'button', 'aria-pressed': String(opt.value === current), text: opt.label }, host);
      b.addEventListener('click', () => onPick(opt.value));
    }
  }

  function initSimulator() {
    const pairSel = document.getElementById('sim-pair');
    fillSelect(pairSel, sim.pairs, (p) => `${p.source} → ${p.destination}`);
    pairSel.addEventListener('change', () => choosePair(Number(pairSel.value)));
    document.getElementById('sim-airline').addEventListener('change', (e) => chooseAirline(Number(e.target.value)));
    document.getElementById('sim-route').addEventListener('change', (e) => chooseRoute(Number(e.target.value)));
    document.getElementById('sim-date').addEventListener('input', () => updatePrediction());
    document.getElementById('sim-dep').addEventListener('input', () => updatePrediction());
    const duration = document.getElementById('sim-duration');
    duration.addEventListener('input', () => {
      document.getElementById('sim-duration-out').textContent = durationLabel(Number(duration.value));
      updatePrediction();
    });
    document.getElementById('sim-form').addEventListener('submit', (e) => e.preventDefault());
    document.getElementById('sim-date').value = '2019-05-24';
    choosePair(0);
  }

  function choosePair(index) {
    sim.pair = sim.pairs[index];
    document.getElementById('sim-pair').value = String(index);
    sim.airlines = sim.pair.airlines.slice().sort((a, b) => b.routes.reduce((s, r) => s + r.n, 0) - a.routes.reduce((s, r) => s + r.n, 0));
    fillSelect(document.getElementById('sim-airline'), sim.airlines, (a) => `${a.airline} (${D.simulator.codes[a.airline]})`);
    chooseAirline(0);
  }

  function chooseAirline(index) {
    sim.airline = sim.airlines[index];
    document.getElementById('sim-airline').value = String(index);
    fillSelect(document.getElementById('sim-route'), sim.airline.routes, (r) => `${shortRoute(r.route)} · ${fmt.num(r.n)} vols`);
    if (!sim.airline.infos.includes(sim.info)) sim.info = 'No info';
    if (!sim.airline.cabins.includes(sim.cabin)) sim.cabin = 'Economy';
    renderTicketOptions();
    chooseRoute(0);
  }

  function renderTicketOptions() {
    const infos = ['No info', ...sim.airline.infos.filter((i) => i !== 'No info')];
    setSeg(document.getElementById('sim-info'), infos.map((v) => ({ value: v, label: D.simulator.infoLabels[v] })), sim.info, (v) => {
      sim.info = v;
      renderTicketOptions();
      updatePrediction();
    });
    document.getElementById('sim-cabin-field').hidden = sim.airline.cabins.length < 2;
    setSeg(document.getElementById('sim-cabin'), sim.airline.cabins.map((v) => ({ value: v, label: v === 'Economy' ? 'Économique' : 'Premium' })), sim.cabin, (v) => {
      sim.cabin = v;
      renderTicketOptions();
      updatePrediction();
    });
  }

  function chooseRoute(index) {
    sim.route = sim.airline.routes[index];
    document.getElementById('sim-route').value = String(index);
    const duration = document.getElementById('sim-duration');
    duration.value = String(sim.route.duration);
    document.getElementById('sim-duration-out').textContent = durationLabel(sim.route.duration);
    const dep = document.getElementById('sim-dep');
    dep.value = sim.route.deps[0];
    const chips = document.getElementById('sim-deps');
    chips.replaceChildren();
    for (const t of sim.route.deps) {
      const b = html('button', { type: 'button', 'aria-pressed': String(t === dep.value), text: t }, chips);
      b.addEventListener('click', () => {
        dep.value = t;
        updatePrediction();
      });
    }
    const codes = codesOf(sim.route.route);
    document.getElementById('pass-from').textContent = codes[0];
    document.getElementById('pass-to').textContent = codes[codes.length - 1];
    updatePrediction({ newRow: true });
  }

  function currentInput(date) {
    return {
      airline: sim.airline.airline,
      cabin: sim.cabin,
      source: sim.pair.source,
      destination: sim.pair.destination,
      route: sim.route.route,
      date: date || document.getElementById('sim-date').value,
      dep: document.getElementById('sim-dep').value || sim.route.deps[0],
      duration: Number(document.getElementById('sim-duration').value),
      info: sim.info,
    };
  }

  function validDate(iso) {
    return /^2019-0[3-6]-\d{2}$/.test(iso) && iso >= '2019-03-01' && iso <= '2019-06-30';
  }

  /** Écrit l'estimation dans le tableau : nouvelle ligne pour un nouveau vol, sinon les cases changent. */
  function writeEstimate(row, newRow) {
    const tbody = document.querySelector('#estimate-table tbody');
    const keys = ['dep', 'code', 'from', 'via', 'to', 'date', 'pred'];
    if (newRow || !sim.current) {
      const blank = { ...row, dep: '', code: '', date: '2019-01-01', route: ['', ''], pred: 0 };
      const created = boardRow(tbody, blank, keys, { prepend: true });
      created.cells.forEach((c) => setFlap(c.cell, ' '));
      sim.current = created;
      while (tbody.children.length > 4) tbody.lastElementChild.remove();
    }
    // Cibles : texte final de chaque case de la ligne courante
    const targets = [];
    let i = 0;
    keys.forEach((key, column) => {
      const col = BOARD_COLS[key];
      const raw = col.value(row);
      const text = col.right ? raw.padStart(col.width) : raw.padEnd(col.width);
      for (const ch of text) {
        const cell = sim.current.cells[i];
        if (cell && cell.cell.textContent !== (ch === ' ' ? ' ' : ch)) targets.push({ cell: cell.cell, final: ch, column });
        if (cell) cell.final = ch;
        i += 1;
      }
      sim.current.tr.children[column].setAttribute('aria-label', raw.trim() || '–');
    });
    flip(targets, { stagger: 1, spread: 3 });
    document.getElementById('estimate-count').textContent = `${tbody.children.length} estimation${tbody.children.length > 1 ? 's' : ''}`;
  }

  function updatePrediction({ newRow = false } = {}) {
    const dateInput = document.getElementById('sim-date');
    if (!validDate(dateInput.value)) dateInput.value = '2019-05-24';
    const input = currentInput();
    for (const chip of document.getElementById('sim-deps').children) chip.setAttribute('aria-pressed', String(chip.textContent === input.dep));
    const price = window.FlightModel.predict(D.model, SPEC, input);
    const codes = codesOf(input.route);
    writeEstimate({ dep: input.dep, code: D.simulator.codes[input.airline], route: codes, date: input.date, pred: Math.round(price / 10) * 10 }, newRow);
    const band = document.getElementById('sim-band');
    band.replaceChildren();
    const via = codes.slice(1, -1).map((c) => airportName(c));
    band.append(`${input.airline}, ${via.length ? `escale à ${via.join(' et ')}` : 'vol direct'}, ${dateLong(input.date)} 2019 : `);
    html('b', { text: rupees10(price) }, band);
    band.append(` (≈ ${euros(price)}). Fourchette à 80 % : ${rupees10(price * LOW)} à ${rupees10(price * HIGH)}. Prix médian observé pour ce vol : ${rupees(sim.route.median)}, sur ${fmt.num(sim.route.n)} vols.`);
    renderCurve(input);
  }

  function renderCurve(input, { draw = false } = {}) {
    const host = document.getElementById('sim-curve');
    const width = Math.max(300, host.clientWidth);
    const height = width < 560 ? 220 : 250;
    const m = { top: 18, right: 16, bottom: 30, left: 58 };
    const days = [];
    for (let t = Date.UTC(2019, 2, 1); t <= Date.UTC(2019, 5, 30); t += 86400000) {
      const iso = new Date(t).toISOString().slice(0, 10);
      days.push({ t, iso, price: window.FlightModel.predict(D.model, SPEC, { ...input, date: iso }) });
    }
    const root = newSvg(host, width, height, 'Prix prédit pour le même vol selon la date');
    const x = F.scaleLinear([days[0].t, days[days.length - 1].t], [m.left, width - m.right]);
    const yMax = F.niceDomain(0, Math.max(...days.map((d) => d.price * HIGH)), 4)[1];
    const y = F.scaleLinear([0, yMax], [height - m.bottom, m.top]);
    const grid = svg('g', { class: 'grid' }, root);
    const axis = svg('g', { class: 'axis' }, root);
    for (const t of F.niceTicks(0, yMax, 4)) {
      svg('line', { x1: m.left, x2: width - m.right, y1: y(t), y2: y(t) }, grid);
      svg('text', { x: m.left - 8, y: y(t) + 4, 'text-anchor': 'end', text: fmt.num(t) }, axis);
    }
    for (const [mo, label] of [[2, 'mars'], [3, 'avril'], [4, 'mai'], [5, 'juin']]) {
      const t = Date.UTC(2019, mo, 1);
      svg('line', { class: 'baseline', x1: x(t), x2: x(t), y1: height - m.bottom, y2: height - m.bottom + 6 }, root);
      svg('text', { x: x(t) + 4, y: height - m.bottom + 18, text: label }, axis);
    }
    svg('line', { class: 'baseline', x1: m.left, x2: width - m.right, y1: y(0), y2: y(0) }, root);
    const band = days.map((d) => `${x(d.t)},${y(d.price * HIGH)}`).join('L') + 'L' + days.slice().reverse().map((d) => `${x(d.t)},${y(d.price * LOW)}`).join('L');
    svg('path', { class: 'm-soft', d: `M${band}Z` }, root);
    const line = svg('path', { class: 'm-line', d: `M${days.map((d) => `${x(d.t)},${y(d.price)}`).join('L')}` }, root);
    const chosen = days.find((d) => d.iso === input.date) || days[0];
    const cheapest = days.reduce((a, b) => (b.price < a.price ? b : a));
    const priciest = days.reduce((a, b) => (b.price > a.price ? b : a));
    for (const d of [cheapest, priciest]) {
      if (d === chosen) continue;
      svg('circle', { class: 'm-mark m-ring', cx: x(d.t), cy: y(d.price), r: 3.5 }, root);
      const right = x(d.t) < width / 2;
      const below = d === cheapest;
      svg('text', { class: 'chart-label chart-label--ink chart-label--halo', x: x(d.t) + (right ? 8 : -8), y: y(d.price) + (below ? 20 : -10), 'text-anchor': right ? 'start' : 'end', text: `${dateLong(d.iso)} : ${rupees10(d.price)}` }, root);
    }
    svg('circle', { class: 'm-signal', cx: x(chosen.t), cy: y(chosen.price), r: 6.5, stroke: css('--ink'), 'stroke-width': 1.5 }, root);
    document.getElementById('sim-curve-note').textContent = `Bande grise : fourchette à 80 %. Les données contiennent des vols un jour sur trois environ ; entre ces dates, le modèle interpole. Cliquez sur la courbe pour choisir une date. Graphique : Youssef Mir.`;

    const cross = svg('line', { class: 'crosshair', y1: m.top, y2: height - m.bottom, visibility: 'hidden' }, root);
    const hit = svg('rect', { class: 'hit', x: m.left, y: m.top, width: width - m.left - m.right, height: height - m.top - m.bottom }, root);
    hit.addEventListener('pointermove', (e) => {
      const box = root.getBoundingClientRect();
      const t = x.invert(((e.clientX - box.left) / box.width) * width);
      const d = days.reduce((a, b) => (Math.abs(b.t - t) < Math.abs(a.t - t) ? b : a));
      cross.setAttribute('x1', x(d.t));
      cross.setAttribute('x2', x(d.t));
      cross.setAttribute('visibility', 'visible');
      F.tip.show(e, { title: `${dateLong(d.iso)} 2019`, rows: [{ value: rupees10(d.price), label: 'prix prédit' }], note: 'Cliquer pour choisir cette date' });
      hit.dataset.iso = d.iso;
    });
    hit.addEventListener('pointerleave', () => {
      cross.setAttribute('visibility', 'hidden');
      F.tip.hide();
    });
    hit.addEventListener('click', () => {
      if (!hit.dataset.iso) return;
      document.getElementById('sim-date').value = hit.dataset.iso;
      F.tip.hide();
      updatePrediction();
    });
    if (draw) {
      reveal(host, {
        reset: () => {
          const len = line.getTotalLength();
          line.style.strokeDasharray = `${len}`;
          line.style.strokeDashoffset = `${len}`;
        },
        play: () => {
          const current = host.querySelector('.m-line');
          const len = current.getTotalLength();
          current.style.strokeDasharray = `${len}`;
          tween(1100, (t) => {
            current.style.strokeDashoffset = `${len * (1 - ease(t))}`;
          }, () => {
            current.style.strokeDasharray = '';
            current.style.strokeDashoffset = '';
          });
        },
      });
    }
  }

  /* ---------- Navigation : section active ---------- */

  function initScrollSpy() {
    const links = [...document.querySelectorAll('.sitenav a')];
    const sections = links.map((a) => document.querySelector(a.getAttribute('href')));
    const update = () => {
      const line = innerHeight * 0.35;
      let active = -1;
      sections.forEach((s, i) => {
        if (s && s.getBoundingClientRect().top <= line) active = i;
      });
      links.forEach((a, i) => (i === active ? a.setAttribute('aria-current', 'true') : a.removeAttribute('aria-current')));
    };
    addEventListener('scroll', update, { passive: true });
    update();
  }

  /* ---------- Démarrage ---------- */

  bindNumbers();
  renderLeadBoard();
  renderNetworkText();
  renderTimetable();
  renderMap(true);
  initSteps();
  renderStrip();
  initMetricControls();
  renderLeaderboard();
  growLeaderboard();
  renderCloud();
  renderDetails();
  initSimulator();
  renderCurve(currentInput(), { draw: true });
  initScrollSpy();

  const onWidth = {
    map: () => renderMap(false),
    strip: () => renderStrip(),
    leaderboard: () => renderLeaderboard(),
    importance: () => renderDetails(),
    'sim-curve': () => renderCurve(currentInput()),
  };
  let firstCloud = true;
  F.onResize(document.getElementById('cloud').parentElement, () => {
    if (firstCloud) {
      firstCloud = false;
      return;
    }
    renderCloud();
  });
  for (const [id, render] of Object.entries(onWidth)) {
    let first = true;
    F.onResize(document.getElementById(id), () => {
      if (first) {
        first = false;
        return;
      }
      render();
    });
  }
  F.onTheme(() => {
    renderMap(false);
    renderStrip();
    renderLeaderboard();
    renderCloud();
    renderDetails();
    renderCurve(currentInput());
  });
})();
