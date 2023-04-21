#!/usr/bin/env node
/*
 * Vérifie que docs/model.js reproduit les prédictions de scikit-learn.
 * Usage : node scripts/check_js_model.js <cas.json> [tolérance en ₹, défaut 0.01]
 * <cas.json> = { model, spec, cases: [{ input, expected }] } (écrit par flight_prices.parity).
 * Sortie : {"n": …, "maxDiff": …} ; code de retour 1 si l'écart maximal dépasse la tolérance.
 */
'use strict';

const fs = require('fs');
const path = require('path');

require(path.join(__dirname, '..', 'docs', 'model.js'));

const [, , casesFile, tolArg] = process.argv;
const tolerance = Number(tolArg || 0.01);
const { model, spec, cases } = JSON.parse(fs.readFileSync(casesFile, 'utf8'));

let maxDiff = 0;
for (const { input, expected } of cases) {
  const predicted = globalThis.FlightModel.predict(model, spec, input);
  maxDiff = Math.max(maxDiff, Math.abs(predicted - expected));
}

process.stdout.write(JSON.stringify({ n: cases.length, maxDiff }));
process.exit(maxDiff < tolerance ? 0 : 1);
