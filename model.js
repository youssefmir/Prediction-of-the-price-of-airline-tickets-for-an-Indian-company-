/* ==========================================================================
   Modèle de prix embarqué : variables, encodage et gradient boosting.
   Miroir exact de src/flight_prices/features.py et export.py (vérifié par
   scripts/check_js_model.js). Fonctionne dans le navigateur et sous Node.
   ========================================================================== */
(function (root) {
  'use strict';

  const MINUTES_PER_DAY = 24 * 60;
  const DAY_MS = 24 * 60 * 60 * 1000;

  /**
   * Variables du modèle à partir d'une saisie du simulateur :
   * { airline, cabin, source, destination, route: "DEL → BOM → COK",
   *   date: "2019-03-24", dep: "22:20", duration: 170, info: "No info" }
   */
  function features(input, spec) {
    const [year, month, day] = input.date.split('-').map(Number);
    const time = Date.UTC(year, month - 1, day);
    const [hours, minutes] = input.dep.slice(0, 5).split(':').map(Number);
    const dep = hours * 60 + minutes;
    const end = dep + input.duration;
    const codes = input.route.split('→').map((code) => code.trim());
    const layovers = codes.slice(1, -1);

    const out = {
      airline: input.airline,
      cabin: input.cabin,
      source: input.source,
      destination: input.destination,
      additional_info: spec.infoKept.includes(input.info) ? input.info : 'Other',
      n_stops: codes.length - 2,
      duration_min: input.duration,
      dep_minutes: dep,
      arr_minutes: end % MINUTES_PER_DAY,
      arr_day_offset: Math.floor(end / MINUTES_PER_DAY),
      journey_day: day,
      journey_month: month,
      journey_weekday: (new Date(time).getUTCDay() + 6) % 7, // 0 = lundi, comme pandas
      journey_doy: Math.round((time - Date.UTC(year, 0, 1)) / DAY_MS) + 1,
    };
    for (const hub of spec.hubs) out[`via_${hub}`] = layovers.includes(hub) ? 1 : 0;
    return out;
  }

  /** Vecteur d'entrée du modèle (indicatrices one-hot puis variables numériques). */
  function encode(model, feats) {
    return model.columns.map(([kind, name, value]) =>
      kind === 'cat' ? (String(feats[name]) === value ? 1 : 0) : feats[name]
    );
  }

  /** Somme des arbres (log du prix). */
  function predictLog(model, x) {
    let sum = model.init;
    for (const { f, v, r } of model.trees) {
      let node = 0;
      while (f[node] >= 0) node = x[f[node]] <= v[node] ? node + 1 : r[node];
      sum += v[node];
    }
    return sum;
  }

  /** Prix prédit en roupies. */
  function predict(model, spec, input) {
    return Math.exp(predictLog(model, encode(model, features(input, spec))));
  }

  root.FlightModel = { features, encode, predictLog, predict };
})(typeof window !== 'undefined' ? window : globalThis);
