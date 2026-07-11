"""Generate desk_china_ladder_models.js from authoritative china_ladder.py.

Regenerate after editing china_policy_track/china_ladder.py:

    python3 -m whinfell_pipeline.desk_china_ladder_models
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from china_policy_track.china_ladder import china_ladder_js_spec

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_JS = REPO_ROOT / "08_Deliverables/desk_china_ladder_models.js"

RUNTIME_HELPERS = r"""
/** Derived from china_ladder.py — keep in sync via desk_china_ladder_models generator. */
function compositeChinaStageScore(stageId, horizons) {
  var model = CHINA_STAGE_MODELS[stageId];
  var hz = horizons && horizons[stageId] ? horizons[stageId] : {};
  if (!model) return 50;
  var total = 0;
  model.components.forEach(function (c) {
    var mark = (hz[c.hz] || 'flat').toLowerCase();
    total += c.w * (CHINA_MARK_SCORE[mark] != null ? CHINA_MARK_SCORE[mark] : 50);
  });
  return Math.round(total / 100);
}

function chinaHorizonNet(hz) {
  var keys = ['d1', 'd5', 'd20', 'd60'];
  var map = { up: 1, flat: 0, down: -1, '': 0 };
  return keys.reduce(function (s, k) { return s + (map[(hz && hz[k]) || ''] || 0); }, 0);
}

function stageHealthBand(score) {
  var s = Math.max(0, Math.min(100, Math.round(score)));
  for (var i = 0; i < STAGE_HEALTH_BANDS.length; i++) {
    if (s >= STAGE_HEALTH_BANDS[i].min) return STAGE_HEALTH_BANDS[i];
  }
  return STAGE_HEALTH_BANDS[STAGE_HEALTH_BANDS.length - 1];
}

function chinaSq3Multiplier(sq3Score) {
  var s = Math.round(sq3Score);
  if (s >= 80) return 1.00;
  if (s >= 65) return 0.95;
  if (s >= 50) return 0.80;
  return 0.60;
}

function chinaLadderFinalBand(finalScore) {
  var score = Math.max(0, Math.min(100, Math.round(finalScore)));
  for (var i = 0; i < CHINA_LADDER_FINAL_BANDS.length; i++) {
    var row = CHINA_LADDER_FINAL_BANDS[i];
    if (score >= row.min && score <= row.max) return row;
  }
  return CHINA_LADDER_FINAL_BANDS[CHINA_LADDER_FINAL_BANDS.length - 1];
}

/**
 * weakestStage — composite = lowest stage score (TC + Deep Dive China).
 * net = lowest horizon net (tracer-style; optional).
 */
function weakestStage(stageList, mode) {
  mode = mode || 'composite';
  var key = mode === 'net' ? 'net' : 'score';
  if (!stageList || !stageList.length) {
    return { stage_id: '', name: '—', value: 0, mode: mode };
  }
  var weakest = stageList[0];
  stageList.forEach(function (row) {
    var v = row[key] != null ? row[key] : 0;
    var wv = weakest[key] != null ? weakest[key] : 0;
    var tie = (STAGE_TIE_RANK[row.id] != null ? STAGE_TIE_RANK[row.id] : 99);
    var wtie = (STAGE_TIE_RANK[weakest.id] != null ? STAGE_TIE_RANK[weakest.id] : 99);
    if (v < wv || (v === wv && tie < wtie)) weakest = row;
  });
  return {
    stage_id: weakest.id,
    name: weakest.name,
    value: weakest[key] != null ? weakest[key] : 0,
    mode: mode,
  };
}

function formatChinaHandicapLine(raw, sq3, multiplier, finalScore, finalBand, deskMeaning, sq3PolicyBand) {
  var mult = typeof multiplier === 'number' ? multiplier.toFixed(2) : String(multiplier);
  var line = 'Ladder ' + raw + ' × SQ3 ' + mult + ' → Final ' + finalScore + ' · ' + finalBand;
  if (deskMeaning) line += ' · ' + deskMeaning;
  if (sq3PolicyBand) line += ' (SQ3 policy band: ' + sq3PolicyBand + ')';
  return line;
}

function chinaStageFacts(stageId, stageName, score, band, net, weakestName, sq3Score) {
  var tpl = CHINA_STAGE_UI_COPY[stageId] || CHINA_STAGE_UI_COPY.liquidity;
  var netStr = (net >= 0 ? '+' : '') + net;
  var vars = {
    score: score,
    band: band,
    net: netStr,
    posture: net >= 0 ? 'available' : 'tightening',
    durability: score >= 65 ? 'durable' : 'tactical',
    participation: net >= 0 ? 'broadening' : 'narrow',
    transmitting: net < 0 ? 'not transmitting' : 'transmitting',
    carry: band === 'Fragile' ? 'selective' : 'warehouse-friendly',
    sq3: sq3Score != null ? sq3Score : '—',
  };
  function fill(s) {
    return String(s).replace(/\{(\w+)\}/g, function (_, k) {
      return vars[k] != null ? String(vars[k]) : '';
    });
  }
  var facts = {
    state: fill(tpl.state),
    evidence: fill(tpl.evidence),
    trigger: fill(tpl.trigger),
  };
  if (stageName === weakestName) facts.evidence += ' Weakest link — size China-linked books first.';
  return facts;
}
"""


def build_js(spec: dict) -> str:
    today = date.today().isoformat()
    payload = json.dumps(spec, indent=2, ensure_ascii=False)
    return f"""/* AUTO-GENERATED — do not edit manually.
 * Source: {spec['source']}
 * Version: {spec['version']}
 * Generated: {today}
 * Regenerate: python3 -m whinfell_pipeline.desk_china_ladder_models
 */
'use strict';

const CHINA_LADDER_SPEC = {payload};

const CHINA_LADDER_SPEC_VERSION = CHINA_LADDER_SPEC.version;
const CHINA_LADDER_STAGES = CHINA_LADDER_SPEC.stages;
const CHINA_MARK_SCORE = CHINA_LADDER_SPEC.mark_score;
const CHINA_STAGE_MODELS = CHINA_LADDER_SPEC.stage_models;
const CHINA_LADDER_FINAL_BANDS = CHINA_LADDER_SPEC.final_bands;
const STAGE_HEALTH_BANDS = CHINA_LADDER_SPEC.stage_health_bands;
const STAGE_TIE_RANK = CHINA_LADDER_SPEC.stage_tie_rank;
const CHINA_STAGE_UI_COPY = CHINA_LADDER_SPEC.ui_copy;
{RUNTIME_HELPERS}
"""


def write_desk_china_ladder_models(path: Path | None = None) -> Path:
    out = path or OUT_JS
    spec = china_ladder_js_spec()
    out.write_text(build_js(spec), encoding="utf-8")
    return out


def main() -> None:
    path = write_desk_china_ladder_models()
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()