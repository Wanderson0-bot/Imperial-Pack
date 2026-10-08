import { useEffect, useState } from 'react';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { operationalSignalsService, type OperationalAlert, type OperationalOpportunity } from '../services/operationalSignalsService';

type View = 'alerts' | 'opportunities';
const dateTime = (value: string) => new Intl.DateTimeFormat('pt-BR', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
const priorityName: Record<OperationalAlert['priority'], string> = { high: 'Alta', medium: 'Média', low: 'Baixa' };
const alertAction = (item: OperationalAlert) => item.entity_type === 'payable' || item.entity_type === 'receivable'
  ? 'Conferir o título e atualizar a situação financeira.'
  : item.entity_type === 'inventory_product'
    ? 'Conferir o saldo físico e avaliar a reposição.'
    : 'Revisar o histórico e confirmar a necessidade com o cliente.';

export function OperationalSignalsPage() {
  const [view, setView] = useState<View>('alerts');
  const [alerts, setAlerts] = useState<OperationalAlert[]>([]);
  const [opportunities, setOpportunities] = useState<OperationalOpportunity[]>([]);
  const [opportunityStatus, setOpportunityStatus] = useState<'ready' | 'insufficient_data'>('ready');
  const [loading, setLoading] = useState(true);
  const [updatingId, setUpdatingId] = useState('');
  const [error, setError] = useState('');

  const refresh = async () => {
    setError('');
    try {
      const [nextAlerts, nextOpportunities] = await Promise.all([
        operationalSignalsService.getAlerts(),
        operationalSignalsService.getOpportunities(),
      ]);
      setAlerts(nextAlerts);
      setOpportunities(nextOpportunities.items);
      setOpportunityStatus(nextOpportunities.status);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível carregar os registros operacionais.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void refresh(); }, []);

  const updateAlert = async (item: OperationalAlert, status: 'RESOLVED' | 'IGNORED') => {
    setUpdatingId(item.id);
    setError('');
    try {
      await operationalSignalsService.updateAlert(item.id, status);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível atualizar o alerta.');
    } finally {
      setUpdatingId('');
    }
  };

  const updateOpportunity = async (item: OperationalOpportunity, status: 'ACTIONED' | 'DISMISSED') => {
    setUpdatingId(item.id);
    setError('');
    try {
      await operationalSignalsService.updateOpportunity(item.id, status);
      await refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Não foi possível atualizar a oportunidade.');
    } finally {
      setUpdatingId('');
    }
  };

  return <div className="page-shell operational-signals">
    <PageHeader title="Alertas e oportunidades" description="Ocorrências e possibilidades operacionais identificadas a partir dos registros do sistema." actions={<span className="page-header__meta">Dados registrados · regras explícitas</span>} />
    <div className="signal-toolbar" role="tablist" aria-label="Registros operacionais">
      <button type="button" role="tab" aria-selected={view === 'alerts'} className={view === 'alerts' ? 'signal-tab signal-tab--active' : 'signal-tab'} onClick={() => setView('alerts')}>Alertas <span>{alerts.length}</span></button>
      <button type="button" role="tab" aria-selected={view === 'opportunities'} className={view === 'opportunities' ? 'signal-tab signal-tab--active' : 'signal-tab'} onClick={() => setView('opportunities')}>Oportunidades <span>{opportunities.length}</span></button>
      <button type="button" className="btn btn--secondary signal-refresh" onClick={() => void refresh()} disabled={loading}>Atualizar</button>
    </div>
    {error ? <ErrorState message={error} /> : null}
    {loading ? <LoadingState message="Lendo registros operacionais..." /> : view === 'alerts' ? <section className="signal-list" aria-label="Alertas ativos">
      {!alerts.length ? <p className="table-state">Nenhum alerta ativo nos contextos disponíveis.</p> : alerts.map((item) => <article className="signal-row" key={item.id}>
        <div className={`signal-priority signal-priority--${item.priority}`}><span>{priorityName[item.priority]}</span></div>
        <div className="signal-content"><div className="signal-heading"><h2>{item.title}</h2><time dateTime={item.detected_at}>{dateTime(item.detected_at)}</time></div>
          <p>{item.description}</p><dl className="signal-facts"><div><dt>Entidade</dt><dd>{item.entity_label || item.entity_id || '—'}</dd></div><div><dt>Motivo</dt><dd>{item.reason}</dd></div><div><dt>Ação possível</dt><dd>{alertAction(item)}</dd></div></dl>
        </div>
        <div className="signal-actions"><button type="button" className="btn btn--secondary" disabled={updatingId === item.id} onClick={() => void updateAlert(item, 'RESOLVED')}>Resolver</button><button type="button" className="btn btn--quiet" disabled={updatingId === item.id} onClick={() => void updateAlert(item, 'IGNORED')}>Ignorar</button></div>
      </article>)}
    </section> : <section className="signal-list" aria-label="Oportunidades abertas">
      {!opportunities.length ? <p className="table-state">{opportunityStatus === 'insufficient_data' ? 'insufficient_data · histórico ainda insuficiente para identificar oportunidades de reposição.' : 'Nenhuma oportunidade operacional aberta.'}</p> : opportunities.map((item) => <article className="signal-row signal-row--opportunity" key={item.id}>
        <div className="signal-priority signal-priority--opportunity"><span>Oportunidade</span></div>
        <div className="signal-content"><div className="signal-heading"><h2>{item.title}</h2><time dateTime={item.created_at}>{dateTime(item.created_at)}</time></div>
          <p>{item.description}</p><dl className="signal-facts"><div><dt>Entidade</dt><dd>{item.entity_label || item.entity_id || '—'}</dd></div><div><dt>Ação considerada</dt><dd>{item.action}</dd></div></dl>
          <div className="signal-evidence"><strong>Origem dos dados</strong>{Object.entries(item.evidence).map(([key, value]) => <span key={key}>{key.replace(/_/g, ' ')}: {String(value)}</span>)}</div>
        </div>
        <div className="signal-actions"><button type="button" className="btn btn--secondary" disabled={updatingId === item.id} onClick={() => void updateOpportunity(item, 'ACTIONED')}>Registrar ação</button><button type="button" className="btn btn--quiet" disabled={updatingId === item.id} onClick={() => void updateOpportunity(item, 'DISMISSED')}>Dispensar</button></div>
      </article>)}
    </section>}
  </div>;
}