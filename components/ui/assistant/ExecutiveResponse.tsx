import type { AssistantChatResponse, ChatMetricFact, ChatUIBlock } from '@/lib/api/types';
import {
  ActionRecommendationCard,
  AlertPanel,
  BenchmarkComparisonCard,
  CompactStatsFooter,
  ConfidenceMeter,
  ExecutiveSummaryCard,
  KPIGrid,
  OperationalInsightCard,
  RiskBanner,
  SourceReferenceChip,
  TechnicalDrawer,
} from './ResponseCards';

type Props = {
  response?: AssistantChatResponse;
  fallbackText: string;
  hideMetaSections?: boolean;
};

type IntentMode = 'SQL_ONLY' | 'HYBRID' | 'RAG_ONLY' | 'UNSUPPORTED' | 'SMALL_TALK' | 'CLARIFICATION_NEEDED';
type CopilotAnswerType =
  | 'SmallTalkAnswer'
  | 'ClarificationNeededAnswer'
  | 'UnsupportedAnswer'
  | 'SqlOnlyAnswer'
  | 'RagOnlyAnswer'
  | 'HybridExecutiveAnswer';

type Generic = Record<string, unknown>;

function getBlock(blocks: ChatUIBlock[] | undefined, type: string): ChatUIBlock | undefined {
  return (blocks || []).find((b) => b.type === type);
}

function getMetric(metrics: ChatMetricFact[] | undefined, key: string): ChatMetricFact | undefined {
  return (metrics || []).find((m) => m.metric === key);
}

function asObject(value: unknown): Generic {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Generic) : {};
}

function asArray(value: unknown): Generic[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === 'object') as Generic[] : [];
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

function intentFromMetrics(metrics: ChatMetricFact[] | undefined): IntentMode {
  const unit = (getMetric(metrics, 'retrieval_plan.intent_type')?.unit || '').toUpperCase();
  if (unit === 'SQL_ONLY' || unit === 'RAG_ONLY' || unit === 'UNSUPPORTED' || unit === 'SMALL_TALK' || unit === 'CLARIFICATION_NEEDED') return unit;
  return 'HYBRID';
}

function answerTypeFromResponse(response?: AssistantChatResponse): CopilotAnswerType {
  const mode = String(response?.mode || '').toLowerCase();
  if (mode === 'small_talk') return 'SmallTalkAnswer';
  if (mode === 'clarification_needed') return 'ClarificationNeededAnswer';
  if (mode === 'unsupported') return 'UnsupportedAnswer';

  const intent = intentFromMetrics(response?.context_metrics);
  if (intent === 'SMALL_TALK') return 'SmallTalkAnswer';
  if (intent === 'CLARIFICATION_NEEDED') return 'ClarificationNeededAnswer';
  if (intent === 'UNSUPPORTED') return 'UnsupportedAnswer';
  if (intent === 'SQL_ONLY') return 'SqlOnlyAnswer';
  if (intent === 'RAG_ONLY') return 'RagOnlyAnswer';
  return 'HybridExecutiveAnswer';
}

function looksCritical(blocks: ChatUIBlock[] | undefined): boolean {
  const risks = getBlock(blocks, 'risk_cards');
  const items = asArray(asObject(risks?.payload).items);
  return items.some((item) => asString(item.niveau).toLowerCase().includes('élev'));
}

function sourceLabel(source: string): string {
  const s = source.toLowerCase();
  if (s.includes('reference') || s.includes('knowledge')) return 'Référence agronomique';
  if (s.includes('ml') || s.includes('prediction')) return 'Analyse ML';
  if (s.includes('batch') || s.includes('process')) return 'Historique lots';
  if (s.includes('stock') || s.includes('ops') || s.includes('dashboard')) return 'Données coopérative';
  return 'Source métier';
}

function safeNonOperationalText(answerType: CopilotAnswerType, fallbackText: string): string {
  if (answerType === 'ClarificationNeededAnswer') {
    return 'Pouvez-vous préciser votre demande ? Je peux vous aider sur les stocks, lots, pertes, risques, recommandations ou références agronomiques.';
  }
  if (answerType === 'UnsupportedAnswer') {
    return 'Cette question sort du périmètre actuel. Je peux répondre aux questions liées aux stocks, lots, pertes, transformation post-récolte, recommandations et indicateurs de la coopérative.';
  }
  return fallbackText;
}

function confidenceExplanation(warnings: string[]): string {
  if (warnings.length) {
    return 'Confiance moyenne — certaines données opérationnelles sont incomplètes.';
  }
  return 'Confiance élevée — données cohérentes et exploitables pour décision.';
}

function asTableRows(value: unknown): Array<Array<string | number>> {
  if (!Array.isArray(value)) return [];
  return value
    .filter((row) => Array.isArray(row))
    .map((row) => (row as unknown[]).map((cell) => (typeof cell === 'number' || typeof cell === 'string' ? cell : String(cell ?? ''))));
}

function TableBlockSection({ block, index }: { block: ChatUIBlock; index: number }) {
  const payload = asObject(block.payload);
  const columns = Array.isArray(payload.columns) ? (payload.columns as string[]) : [];
  const rows = asTableRows(payload.rows);

  return (
    <section key={`${block.type}-${index}`} className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
      <h3 className="text-sm font-semibold text-[#173324]">{block.title || 'Tableau'}</h3>
      <div className="mt-3 overflow-auto">
        <table className="wf-table min-w-full text-left text-sm">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length ? (
              rows.map((row, rowIndex) => (
                <tr key={`${block.title || 'table'}-${rowIndex}`}>
                  {row.map((cell, cellIndex) => (
                    <td key={`${rowIndex}-${cellIndex}`}>{String(cell)}</td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={Math.max(columns.length, 1)} className="text-[var(--muted)]">
                  Aucune donnée disponible.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function ExecutiveResponse({ response, fallbackText, hideMetaSections = false }: Props) {
  const blocks = response?.ui_blocks || [];
  const metrics = response?.context_metrics || [];
  const answerType = answerTypeFromResponse(response);
  const tableBlocks = blocks.filter((block) => block.type === 'table');

  const summaryBlock = getBlock(blocks, 'executive_summary');
  const kpiBlock = getBlock(blocks, 'kpi_grid');
  const risksBlock = getBlock(blocks, 'risk_cards');
  const analysisBlock = getBlock(blocks, 'analysis_section');
  const benchmarkBlock = getBlock(blocks, 'benchmark_card');
  const recosBlock = getBlock(blocks, 'recommendation_cards');
  const confidenceBlock = getBlock(blocks, 'confidence_block');
  const evidenceBlock = getBlock(blocks, 'evidence_drawer');

  const summaryText = asString(asObject(summaryBlock?.payload).text, fallbackText);
  const kpiItems = asArray(asObject(kpiBlock?.payload).items);
  const riskItems = asArray(asObject(risksBlock?.payload).items);
  const analysisPoints = asArray(asObject(analysisBlock?.payload).points)
    .map((item) => asString(item.text || item.value || Object.values(item)[0] || ''))
    .filter(Boolean);
  const recoItems = asArray(asObject(recosBlock?.payload).items);
  const evidenceItems = asArray(asObject(evidenceBlock?.payload).items);

  const isAlert = looksCritical(blocks);
  const warningMetric = getMetric(metrics, 'orchestration.warning_count');
  const warnings = (warningMetric?.notes || '').split('|').filter((v) => v && v !== 'none');
  const confidenceMetric = getMetric(metrics, 'orchestration.confidence_score');
  const confidencePayload = asObject(confidenceBlock?.payload);
  const confidenceLabel = asString(confidencePayload.label, confidenceMetric?.unit || 'Moyen');
  const confidenceScore = asNumber(confidencePayload.score, (confidenceMetric?.value || 0) * 100);

  if (!response) {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{fallbackText}</p>;
  }

  if (answerType === 'SmallTalkAnswer' || answerType === 'ClarificationNeededAnswer' || answerType === 'UnsupportedAnswer') {
    return <p className="whitespace-pre-wrap text-sm leading-7 text-[#173324]">{safeNonOperationalText(answerType, fallbackText)}</p>;
  }

  if (answerType === 'SqlOnlyAnswer') {
    return (
      <div className="space-y-3">
        <ExecutiveSummaryCard text={summaryText} />
        {kpiItems.length > 0 ? <KPIGrid items={kpiItems.slice(0, 4)} /> : null}
        {tableBlocks.map((block, index) => <TableBlockSection key={`sql-table-${index}`} block={block} index={index} />)}
        <CompactStatsFooter left="Mode SQL direct" right="Réponse concise opérationnelle" />
      </div>
    );
  }

  if (answerType === 'RagOnlyAnswer') {
    return (
      <div className="space-y-3">
        <ExecutiveSummaryCard text={summaryText} />
        {analysisPoints.length > 0 ? (
          <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
            <h3 className="text-sm font-semibold text-[#173324]">Bonnes pratiques et constats</h3>
            <ul className="mt-3 space-y-2">{analysisPoints.map((p) => <OperationalInsightCard key={p} text={p} />)}</ul>
          </section>
        ) : null}
        {benchmarkBlock ? <BenchmarkComparisonCard note={asString(asObject(benchmarkBlock.payload).note)} citationsCount={asNumber(asObject(benchmarkBlock.payload).citations_count)} /> : null}
        <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
          <h3 className="text-sm font-semibold text-[#173324]">Sources utilisées</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {(response.citations || []).slice(0, 6).map((c) => <SourceReferenceChip key={`${c.source_id}-${c.topic}`} label={sourceLabel(c.source_id)} />)}
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {isAlert ? (
        <AlertPanel
          issue={riskItems[0] ? asString(riskItems[0].titre, 'Risque opérationnel prioritaire détecté') : 'Risque opérationnel prioritaire détecté'}
          impact={riskItems[0] ? asString(riskItems[0].impact, 'Impact potentiel sur le rendement et les pertes matière.') : 'Impact potentiel sur le rendement et les pertes matière.'}
          actions={recoItems.slice(0, 3).map((r) => asString(r.action)).filter(Boolean)}
        />
      ) : null}

      <ExecutiveSummaryCard text={summaryText} />
      {kpiItems.length > 0 ? <KPIGrid items={kpiItems} /> : null}

      {riskItems.length > 0 ? (
        <section className="rounded-2xl border border-[#ef4444]/25 bg-[#fff7f7] p-4">
          <h3 className="text-sm font-semibold text-[#9f1239]">Risques détectés</h3>
          <div className="mt-3 space-y-2">
            {riskItems.map((r, i) => <RiskBanner key={i} title={asString(r.titre, 'Risque')} impact={asString(r.impact)} severity={asString(r.niveau, 'Moyen')} />)}
          </div>
        </section>
      ) : null}

      {analysisPoints.length > 0 ? (
        <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
          <h3 className="text-sm font-semibold text-[#173324]">Analyse opérationnelle</h3>
          <ul className="mt-3 space-y-2">{analysisPoints.map((p) => <OperationalInsightCard key={p} text={p} />)}</ul>
        </section>
      ) : null}

      {benchmarkBlock ? <BenchmarkComparisonCard note={asString(asObject(benchmarkBlock.payload).note)} citationsCount={asNumber(asObject(benchmarkBlock.payload).citations_count)} /> : null}

      {tableBlocks.map((block, index) => <TableBlockSection key={`hybrid-table-${index}`} block={block} index={index} />)}

      {recoItems.length > 0 ? (
        <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
          <h3 className="text-sm font-semibold text-[#173324]">Actions recommandées</h3>
          <ol className="mt-3 space-y-2">{recoItems.map((item, i) => <ActionRecommendationCard key={i} item={item} index={i + 1} />)}</ol>
        </section>
      ) : null}

      {!hideMetaSections ? (
        <>
          <ConfidenceMeter
            label={confidenceLabel}
            score={confidenceScore}
            explanation={confidenceExplanation(warnings)}
          />

          <section className="rounded-2xl border border-[var(--line)] bg-white/90 p-4">
            <h3 className="text-sm font-semibold text-[#173324]">Sources utilisées</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {(response.citations || []).slice(0, 8).map((c) => <SourceReferenceChip key={`${c.source_id}-${c.topic}`} label={sourceLabel(c.source_id)} />)}
            </div>
          </section>

          <TechnicalDrawer title="Afficher les détails techniques">
            <div className="space-y-2 text-xs text-[#355f4b]">
              <p>Mode de réponse: {intentFromMetrics(metrics)}</p>
              <p>Sources récupérées: {evidenceItems.length}</p>
              <p>Avertissements internes: {warnings.length ? warnings.join(' | ') : 'Aucun'}</p>
            </div>
          </TechnicalDrawer>
        </>
      ) : null}
    </div>
  );
}
