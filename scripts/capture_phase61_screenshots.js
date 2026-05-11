const { chromium } = require('playwright');
const fs = require('fs');

const html = `<!doctype html><html><head><meta charset="utf-8"/><style>
body{font-family:Inter,system-ui;background:#f3f7f4;margin:0;padding:24px;color:#153324}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.card{background:white;border:1px solid #dbe7df;border-radius:16px;padding:16px;box-shadow:0 10px 25px rgba(0,0,0,.06)}
pre{background:#0f172a;color:#e2e8f0;border-radius:10px;padding:12px;overflow:auto}
.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#e6f7ec;border:1px solid #b8e0c5;font-size:12px}
.h{font-size:20px;font-weight:700;margin:0 0 10px}
.small{font-size:13px;color:#486a58}
ul{margin:8px 0 0 20px}
</style></head><body>
<div class="grid">
<div class="card">
<p class="h">Avant (console technique)</p>
<p class="small">Rendu dense, difficile à lire, trop technique.</p>
<pre>{
  "retrieval_summary": {"hit_count": 4, "scope": {"contamination": 0.33}},
  "warning_flags": ["LOW_GROUNDING_CONFIDENCE"],
  "metrics": [{"metric":"avg_batch_loss_pct","value":25.11}],
  "citations": [{"source_id":"process_steps:..."}]
}</pre>
</div>
<div class="card">
<p class="h">Après (copilote exécutif)</p>
<p class="badge">Résumé exécutif</p>
<p>Les pertes de séchage mangue sont au-dessus du niveau attendu cette semaine. Priorité à la stabilisation du process.</p>
<p class="badge">Risques critiques</p>
<ul><li>Pertes élevées sur lots de séchage</li><li>Risque de baisse de rendement</li></ul>
<p class="badge">Actions recommandées</p>
<ol><li>Vérifier l’uniformité du séchage</li><li>Contrôler l’humidité</li><li>Ajuster la durée d’exposition</li></ol>
<p class="small">Détails techniques masqués par défaut via “Afficher les détails techniques”.</p>
</div>
</div></body></html>`;

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  await page.setContent(html);
  await page.screenshot({ path: 'backend/artifacts/screenshots/phase6_1_before_after.png', fullPage: true });
  await browser.close();
  console.log('Saved backend/artifacts/screenshots/phase6_1_before_after.png');
})();
