const { chromium } = require('playwright');

const html = `<!doctype html><html><head><meta charset="utf-8"/><style>
body{font-family:Inter,system-ui;background:#eef5f0;margin:0;padding:24px;color:#173324}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:#fff;border:1px solid #d7e3db;border-radius:14px;padding:16px;box-shadow:0 8px 18px rgba(0,0,0,.06)}
.h{font-size:19px;font-weight:700;margin:0 0 10px}
.kpi{display:flex;gap:8px;flex-wrap:wrap}.chip{font-size:12px;padding:4px 8px;background:#f3f7f4;border:1px solid #d6e4da;border-radius:999px}
.small{font-size:13px;color:#446657}
ul,ol{margin:8px 0 0 20px}
pre{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:12px;overflow:auto;font-size:12px}
</style></head><body>
<div class="grid">
  <div class="card">
    <p class="h">Avant 6.2 (dense)</p>
    <div class="kpi"><span class="chip">KPIs x8</span><span class="chip">analysis</span><span class="chip">confidence</span><span class="chip">evidence+retrieval</span></div>
    <p class="small">Beaucoup de blocs et de répétitions visuelles.</p>
    <pre>{"retrieval_summary": {...}, "context_metrics": [...], "ui_blocks": ["summary","kpi","risk","analysis","benchmark","actions","confidence","evidence", "table"]}</pre>
  </div>
  <div class="card">
    <p class="h">Après 6.2 (exécutif compact)</p>
    <div class="kpi"><span class="chip">Résumé</span><span class="chip">4 KPI max</span><span class="chip">Risques</span><span class="chip">Actions</span></div>
    <p><b>Impact:</b> pertes élevées sur séchage mangue cette semaine.</p>
    <p><b>Risque:</b> baisse du rendement final si réglage inchangé.</p>
    <ol><li>Ajuster humidité/cadence séchage</li><li>Contrôle qualité en fin d’étape</li><li>Prioriser lots à dérive élevée</li></ol>
    <p class="small">Télémétrie interne masquée dans un tiroir technique replié.</p>
  </div>
</div>
</body></html>`;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.setContent(html);
  await page.screenshot({ path: 'backend/artifacts/screenshots/phase6_2_before_after.png', fullPage: true });
  await browser.close();
  console.log('Saved backend/artifacts/screenshots/phase6_2_before_after.png');
})();
