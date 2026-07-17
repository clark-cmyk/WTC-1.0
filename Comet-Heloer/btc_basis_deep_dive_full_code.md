<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BTC Basis — DIG Layer (Benaiah Captain)</title>
    <link rel="stylesheet" href="css/01_console.css">

    <style>
        body { 
            font-family: system-ui, sans-serif; 
            background: var(--bg-page); 
            color: var(--text-primary); 
            margin: 0; 
            padding: 20px; 
            line-height: 1.6; 
            overflow-y: auto; 
            height: 100vh; 
        }
        .header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center; 
            gap: 16px; 
            margin-bottom: 24px; 
            padding-bottom: 16px; 
            border-bottom: 1px solid var(--border); 
        }
        .back-btn { 
            padding: 10px 20px; 
            background: var(--green); 
            color: white; 
            border: none; 
            border-radius: 6px; 
            cursor: pointer; 
            font-weight: bold; 
        }
        .panel { 
            background: var(--bg-card); 
            border: 1px solid var(--border); 
            padding: 24px; 
            border-radius: 12px; 
            margin-bottom: 24px; 
            overflow: visible; 
        }
        .metric { 
            font-size: 3.5em; 
            font-weight: 700; 
            color: var(--green); 
            line-height: 1; 
        }
        .scan { 
            background: rgba(10,77,46,0.1); 
            padding: 20px; 
            border-radius: 8px; 
            margin: 16px 0; 
            border-left: 4px solid var(--green); 
        }
        .agent-tag { 
            font-size: 0.85em; 
            color: #0A4D2E; 
            font-weight: bold; 
        }
        .a-btn { 
            padding: 8px 16px; 
            background: var(--green); 
            color: white; 
            border: none; 
            border-radius: 4px; 
            cursor: pointer; 
        }
        .chart-placeholder { 
            min-height: 320px; 
            background: #1A1A1A; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-style: italic; 
            color: #aaa; 
            border: 1px dashed #0A4D2E; 
            border-radius: 8px; 
        }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); 
            gap: 12px; 
        }
        .mini-card { 
            background: rgba(255,255,255,0.02); 
            border: 1px solid var(--border); 
            border-radius: 8px; 
            padding: 14px; 
        }
        .mini-card h4 { 
            margin: 0 0 8px 0; 
            font-size: 0.95rem; 
        }
        .mini-card p { 
            margin: 0; 
            font-size: 0.92rem; 
        }
        .pill { 
            display: inline-block; 
            padding: 2px 8px; 
            border-radius: 999px; 
            font-size: 0.78rem; 
            font-weight: 700; 
            text-transform: uppercase; 
            letter-spacing: 0.03em; 
            margin-top: 8px; 
        }
        .pill--healthy, .pill--stable, .pill--inflow { background: rgba(10,77,46,0.18); color: #6fd39a; }
        .pill--crowded { background: rgba(180,120,0,0.18); color: #f0c36a; }
        .pill--stress, .pill--outflow, .pill--compressed { background: rgba(150,30,30,0.18); color: #ff8c8c; }
        .split-two { 
            display: grid; 
            grid-template-columns: 1fr 1fr; 
            gap: 16px; 
        }
        ul { margin: 10px 0 0 18px; }
        li { margin-bottom: 8px; }
        a { color: #86c5ff; }
        h3 { margin-top: 0; }
        h4 { margin-bottom: 8px; }
        .muted { color: var(--text-secondary, #a7a7a7); }
        @media (max-width: 800px) {
            .header { flex-direction: column; align-items: flex-start; }
            .split-two { grid-template-columns: 1fr; }
        }
    </style>
    
</head>
<body>
    <div class="header">
        <button class="back-btn" onclick="window.history.back()">← Back to Risk Curve (Scan)</button>
        <h1>BTC Basis — DIG Layer (Benaiah Captain)</h1>
        <div id="as-of"></div>
    </div>

    <div class="panel" id="summaryPanel">
        <div class="metric" id="score">92</div>
        <div id="status">Strong Q1</div>
        <p id="description">Positive and stable basis environment</p>
        <p id="actionBias" class="muted">Awaiting commentary payload.</p>
    </div>

    <div class="panel" id="chartPanel">
        <h3 id="chartTitle">Chart of the Day</h3>
        <div class="chart-placeholder" id="chartOfDayMount">[Chart mounts here]</div>
        <ul id="chartTakeaways">
            <li>Awaiting drone payload.</li>
        </ul>
    </div>

    <div class="panel" id="inputsPanel">
        <h3>Core Inputs</h3>
        <p id="inputsSummary">Awaiting drone payload.</p>
        <div id="inputsGrid"></div>
    </div>

    <div class="panel" id="scorePanel">
        <h3>How Score is Calculated</h3>
        <p id="scoreMethod">Basis level (40%) + Calendar spreads (30%) + ETF flows (20%) + Roll stability (10%).</p>
        <p id="scoreInterpretation">Awaiting score interpretation payload.</p>
    </div>

    <div class="panel" id="coreTradesPanel">
        <h3>Core Trades & Metrics</h3>
        <div id="coreTradesList"></div>
    </div>

    <div class="panel" id="secondaryTradesPanel">
        <h3>Secondary Trades & Metrics</h3>
        <div id="secondaryTradesList"></div>
    </div>

    <div class="panel" id="crossPanel">
        <h3>Cross-Node Transmission</h3>
        <div id="outboundTransmission"></div>
        <div id="inboundDependencies"></div>
    </div>

    <div class="panel" id="linksPanel">
        <h3>Dig Deeper</h3>
        <div id="researchLinks"></div>
    </div>

    <div class="panel" id="regimePanel">
        <h3>Regime</h3>
        <p id="regimeSummary">Awaiting regime payload.</p>
    </div>

    <div class="panel" id="truthPanel">
        <h3>Truth from Fact</h3>
        <div class="split-two">
            <div id="truthReal"></div>
            <div id="truthFleeting"></div>
        </div>
    </div>

    <button onclick="copyDeepDivePrompt()" class="a-btn">A → LLM (Full Context for Articulate)</button>

         <script src="js/02_core.js"></script>
         <script>
             function safeArray(v) {
                 return Array.isArray(v) ? v : [];
             }
     
             function setHTML(id, html, fallback = '') {
                 const el = document.getElementById(id);
                 if (!el) return;
                 el.innerHTML = html || fallback;
             }
     
             function setText(id, text, fallback = '') {
                 const el = document.getElementById(id);
                 if (!el) return;
                 el.textContent = text || fallback;
             }
     
             function renderList(items, formatter, emptyText = 'Awaiting drone payload.') {
                 if (!Array.isArray(items) || !items.length) return `<p>${emptyText}</p>`;
                 return `<ul>${items.map(formatter).join('')}</ul>`;
             }
     
             function renderSignalCards(inputs) {
                 if (!inputs.length) return '<p>Awaiting drone payload.</p>';
                 return `
                     <div class="grid">
                         ${inputs.map(input => `
                             <div class="mini-card">
                                 <h4>${input.name || 'Signal'}</h4>
                                 <p>${input.interpretation || 'No interpretation yet.'}</p>
                                 <span class="pill">${input.band || input.state || input.trend || ''}</span>
                             </div>
                         `).join('')}
                     </div>
                 `;
             }
     
             function renderTrades(trades) {
                 if (!trades.length) return '<p>Awaiting drone payload.</p>';
                 return `
                     <ul>
                         ${trades.map(trade => `
                             <li>
                                 <strong>${trade.name || 'Trade'}:</strong>
                                 ${trade.expression ? `<span>${trade.expression}. </span>` : ''}
                                 <span>${trade.commentary || 'No commentary yet.'}</span>
                             </li>
                         `).join('')}
                     </ul>
                 `;
             }
     
             function renderLinks(barchartLinks, koyfinLinks) {
                 const links = [];
                 safeArray(barchartLinks).forEach(link => {
                     if (link?.url) links.push(`<li><a href="${link.url}" target="_blank" rel="noopener noreferrer">${link.label || 'Barchart'}</a></li>`);
                 });
                 safeArray(koyfinLinks).forEach(link => {
                     if (link?.url) links.push(`<li><a href="${link.url}" target="_blank" rel="noopener noreferrer">${link.label || 'Koyfin'}</a></li>`);
                 });
                 return links.length ? `<ul>${links.join('')}</ul>` : '<p>Awaiting research links.</p>';
             }
     
             function renderDeepDiveSections(node = {}, data = {}) {
                 setText('score', node.score || 92);
                 setText('status', `${node.status || 'Strong'} ${node.quartile || 'Q1'}`);
                 setText('description', node.description || 'Positive and stable basis environment');
                 setText('as-of', `as of ${data?.as_of || '2026-07-14'}`);
     
                 setText('chartTitle', node.chart_title || 'Chart of the Day');
                 setHTML(
                     'chartTakeaways',
                     safeArray(node.chart_takeaways).length
                         ? safeArray(node.chart_takeaways).map(t => `<li>${t}</li>`).join('')
                         : '<li>Awaiting drone payload.</li>'
                 );
     
                 setText('inputsSummary', node.inputs_summary || 'Awaiting drone payload.');
                 setHTML('inputsGrid', renderSignalCards(safeArray(node.core_inputs)));
     
                 setText('scoreInterpretation', node.score_interpretation || 'Awaiting score interpretation payload.');
     
                 setHTML('coreTradesList', renderTrades(safeArray(node.core_trades)));
                 setHTML('secondaryTradesList', renderTrades(safeArray(node.secondary_trades)));
     
                 setHTML(
                     'outboundTransmission',
                     `
                     <h4>What this node says about other nodes</h4>
                     ${renderList(
                         safeArray(node.outbound_transmission),
                         item => `<li><strong>${item.target_node || 'Node'}:</strong> ${item.message || ''}</li>`
                     )}
                     `
                 );
     
                 setHTML(
                     'inboundDependencies',
                     `
                     <h4>How other nodes impact this node</h4>
                     ${renderList(
                         safeArray(node.inbound_dependencies),
                         item => `<li><strong>${item.source_node || 'Node'}:</strong> ${item.logic || ''}</li>`
                     )}
                     `
                 );
     
                 setHTML('researchLinks', renderLinks(node.barchart_links, node.koyfin_links));
                 setText('regimeSummary', node.regime_summary || 'Awaiting regime payload.');
     
                 setHTML(
                     'truthReal',
                     `
                     <h4>Real</h4>
                     ${renderList(safeArray(node.truth_real), item => `<li>${item}</li>`)}
                     `
                 );
     
                 setHTML(
                     'truthFleeting',
                     `
                     <h4>Fleeting</h4>
                     ${renderList(safeArray(node.truth_fleeting), item => `<li>${item}</li>`)}
                     `
                 );
             }
     
             async function loadDeepDive() {
                 const data = await ARK.get('risk_curve');
                 const node = data?.nodes?.BTCBasis || {};
                 renderDeepDiveSections(node, data);
             }
     
             function copyDeepDivePrompt() {
                 const data = ARK.get('risk_curve') || {};
                 const node = data?.nodes?.BTCBasis || {};
                 const prompt = `BTC Basis Deep Dive
     Score: ${node.score || ''}
     Quadrant: ${node.quartile || ''}
     Description: ${node.description || ''}
     Action Bias: ${node.action_bias || ''}
     Chart Takeaways: ${(node.chart_takeaways || []).join('; ')}
     Inputs Summary: ${node.inputs_summary || ''}
     Score Interpretation: ${node.score_interpretation || ''}
     Regime: ${node.regime_summary || ''}`;
                 navigator.clipboard.writeText(prompt).then(() => alert('Deep Dive Prompt Copied for Articulate!'));
             }
     
             loadDeepDive();
         </script>
     </body>
     </html>
