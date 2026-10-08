import { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { authService } from '../services/authService';
import { intelligenceService } from '../services/intelligenceService';
import type { IntelligenceStatus } from '../services/intelligenceService';

export function IntelligencePage() {
  const [status, setStatus] = useState<IntelligenceStatus | null>(null);
  const [error, setError] = useState('');
  const [training, setTraining] = useState(false);
  const refresh = () => intelligenceService.getStatus().then(setStatus).catch(() => setError('Não foi possível consultar a API de inteligência.'));
  useEffect(() => { void refresh(); }, []);

  const startTraining = async () => {
    setTraining(true);
    setError('');
    try {
      const result = await intelligenceService.train();
      if (result.status === 'awaiting_data') setError(result.message ?? 'Dados reais insuficientes para ativar um modelo.');
      await refresh();
    } catch {
      setError('Treinamento não concluído. Verifique a permissão intelligence:train e o log do backend.');
    } finally {
      setTraining(false);
    }
  };

  const metrics = status ? [
    { label: 'Estado do modelo', value: status.model_status === 'active' ? 'Ativo' : 'Aguardando dados reais' },
    { label: 'Versão do modelo', value: status.model_version ?? '—' },
    { label: 'Compras usadas no treino', value: String(status.training_records) },
    { label: 'Pares validados', value: String(status.eligible_partner_products) },
    { label: 'Parceiros ativos', value: String(status.active_partners) },
    { label: 'Produtos com histórico', value: String(status.products_with_history) },
    { label: 'Previsões armazenadas', value: String(status.stored_predictions) },
    { label: 'Previsões avaliadas', value: String(status.evaluated_predictions) },
  ] : [];

  return <>
    <Header title="Inteligência" breadcrumb="Inteligência / Análises" />
    <div className="page-shell">
      <PageHeader title="Inteligência" description="Previsões aprendidas com compras reais, validadas por parceiro e produto."
        actions={authService.can('train_intelligence')
          ? <button className="btn btn--primary" type="button" disabled={training} onClick={() => void startTraining()}>{training ? 'Treinando…' : 'Treinar modelo'}</button>
          : <span className="page-header__meta">Treinamento restrito</span>} />
      <section className="insights-grid">
        {error ? <ErrorState message={error} /> : null}
        {status ? <>
          {metrics.map((metric) => <article key={metric.label} className="insight-card"><span className="eyebrow">API</span><h4>{metric.label}</h4><p>{metric.value}</p></article>)}
          <article className="insight-card"><span className="eyebrow">MODELO</span><h4>{status.algorithm ?? 'Sem modelo treinado'}</h4><p>{status.message}</p>{status.training_period ? <p>Histórico: {status.training_period.start} a {status.training_period.end}</p> : null}</article>
          <article className="insight-card"><span className="eyebrow">VALIDAÇÃO TEMPORAL</span><h4>Erro no período reservado</h4>
            {status.validation_metrics ? <><p>Intervalo: MAE {status.validation_metrics.interval_days.mae.toFixed(1)} dias · RMSE {status.validation_metrics.interval_days.rmse.toFixed(1)} dias</p><p>Quantidade: MAE {status.validation_metrics.next_quantity.mae.toFixed(2)} · RMSE {status.validation_metrics.next_quantity.rmse.toFixed(2)}</p></> : <p>Sem pares com dados suficientes para validação temporal.</p>}
          </article>
          <article className="insight-card"><span className="eyebrow">RESULTADOS REAIS</span><h4>Previsões avaliadas</h4>
            <p>{status.evaluation_metrics.count ? `Quantidade: MAE ${status.evaluation_metrics.mae?.toFixed(2)} · RMSE ${status.evaluation_metrics.rmse?.toFixed(2)} · MAPE ${status.evaluation_metrics.mape_percent?.toFixed(1) ?? '—'}%` : 'Nenhuma previsão tem resultado real associado ainda.'}</p>
            {status.evaluation_metrics.interval_error_days.count ? <p>Janela: MAE {status.evaluation_metrics.interval_error_days.mae?.toFixed(1)} dias · RMSE {status.evaluation_metrics.interval_error_days.rmse?.toFixed(1)} dias</p> : null}
          </article>
        </> : <LoadingState message="Consultando inteligência…" />}
      </section>
    </div>
  </>;
}
