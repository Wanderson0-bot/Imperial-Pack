import { useEffect, useState } from 'react';
import { PageHeader } from '../components/PageHeader';
import { consumptionService, type ProductConsumption } from '../services/consumptionService';
import { partnerMonitoringService, type PartnerMonitoring as PartnerMonitoringData } from '../services/partnerMonitoringService';
import { partnerService } from '../services/partnerService';
import type { Customer, PartnerProfile } from '../types';

const cycles: Record<string, string> = { weekly: 'Semanal', fortnightly: 'Quinzenal', monthly: 'Mensal', bimonthly: 'Bimestral', custom: 'Personalizado' };
const dateLabel = (date?: string) => date ? new Intl.DateTimeFormat('pt-BR').format(new Date(`${date.slice(0, 10)}T12:00:00`)) : '—';
const quantity = (value?: number) => value === undefined ? '—' : value.toLocaleString('pt-BR', { maximumFractionDigits: 2 });

export function PartnerMonitoringPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [partners, setPartners] = useState<PartnerMonitoringData[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState('');
  const [openedId, setOpenedId] = useState('');
  const [history, setHistory] = useState<Record<string, ProductConsumption[]>>({});
  const [customDaysDraft, setCustomDaysDraft] = useState<Record<string, string>>({});
  const [feedback, setFeedback] = useState('');
  const refresh = async () => {
    const [nextCustomers, overview] = await Promise.all([partnerService.getCandidates(), partnerMonitoringService.getOverview()]);
    setCustomers(nextCustomers);
    setPartners(overview.partners);
  };
  useEffect(() => { void refresh(); }, []);
  const activeIds = new Set(partners.map((item) => item.profile.customerId));
  const opened = partners.find((item) => item.profile.customerId === openedId);
  const alertCount = partners.reduce((count, partner) => count + partner.alerts.length, 0);
  const trackedCount = partners.reduce((count, partner) => count + partner.products.length, 0);
  const upcomingCount = partners.reduce((count, partner) => count + partner.products.filter((item) => {
    const date = item.prediction?.replenishmentWindow?.start;
    const days = date ? (Date.parse(`${date}T12:00:00`) - Date.now()) / 86_400_000 : Infinity;
    return days >= 0 && days <= 7;
  }).length, 0);
  const openPartner = async (partner: PartnerMonitoringData) => {
    setOpenedId(partner.profile.customerId);
    const items = await consumptionService.getForPartner(partner.profile.customerId);
    setHistory((current) => ({ ...current, [partner.profile.customerId]: items }));
  };
  const activate = async () => {
    if (!selectedCustomer) return;
    try { await partnerService.activate(selectedCustomer); setSelectedCustomer(''); setFeedback('Cliente associado ao Imperial Partner.'); await refresh(); }
    catch (error) { setFeedback(error instanceof Error ? error.message : 'Não foi possível atualizar o parceiro.'); }
  };
  const setCycle = async (partner: PartnerMonitoringData, cycle: string) => {
    await partnerService.setCycle(partner.profile.customerId, (cycle || undefined) as PartnerProfile['cycle']);
    await refresh();
  };
  const setCustomDays = async (partner: PartnerMonitoringData, days: number) => {
    if (Number.isFinite(days) && days > 0) { await partnerService.setCycle(partner.profile.customerId, 'custom', days); await refresh(); }
  };

  return <div className="page-shell">
    <PageHeader title="Imperial Partner" description="Acompanhamento de abastecimento, relacionamento e oportunidades da carteira parceira." actions={<span className="page-header__meta">Cliente continua sendo o cadastro principal</span>} />
    <section className="command-summary" aria-label="Resumo Imperial Partner"><div className="command-summary__ops">
      <div><span className="command-kicker">PARCEIROS ATIVOS</span><strong>{partners.length}</strong></div>
      <div><span className="command-kicker">PRODUTOS ACOMPANHADOS</span><strong>{trackedCount}</strong></div>
      <div><span className="command-kicker">REPOSIÇÕES PRÓXIMAS</span><strong>{upcomingCount}</strong></div>
      <div><span className="command-kicker">ALERTAS</span><strong>{alertCount}</strong></div>
    </div></section>
    <section className="panel">
      <div className="panel__header"><div><h3>Avaliar cliente</h3><p className="panel__description">Associe um cadastro existente; clientes não são duplicados.</p></div></div>
      <div className="toolbar"><select aria-label="Selecionar cliente" value={selectedCustomer} onChange={(event) => setSelectedCustomer(event.target.value)}><option value="">Selecione um cliente</option>{customers.filter((customer) => !activeIds.has(customer.id)).map((customer) => <option key={customer.id} value={customer.id}>{customer.company} · {customer.name}</option>)}</select><button className="btn btn--primary" type="button" disabled={!selectedCustomer} onClick={() => void activate()}>Ativar Imperial Partner</button></div>
      {feedback ? <p role="status">{feedback}</p> : null}
    </section>
    <section className="panel"><div className="panel__header"><div><h3>Carteira parceira</h3><p className="panel__description">O ciclo é planejamento e não cria compra automática.</p></div></div>
      {!partners.length ? <p className="table-state">Nenhum Imperial Partner ativo.</p> : <div className="table-scroll"><table className="table"><thead><tr><th>Cliente</th><th>Ciclo</th><th>Produtos</th><th>Alertas</th><th></th></tr></thead><tbody>{partners.map((partner) => <tr key={partner.profile.customerId}>
        <td><strong>{partner.customer?.company ?? partner.customer?.name ?? partner.profile.customerId}</strong><small>{partner.customer?.name}</small></td>
        <td><select aria-label="Ciclo planejado" value={partner.profile.cycle ?? ''} onChange={(event) => void setCycle(partner, event.target.value)}><option value="">Não definido</option><option value="weekly">Semanal</option><option value="fortnightly">Quinzenal</option><option value="monthly">Mensal</option><option value="bimonthly">Bimestral</option><option value="custom">Personalizado</option></select>{partner.profile.cycle === 'custom' ? <input aria-label="Ciclo em dias" type="number" min="1" placeholder="Dias" value={customDaysDraft[partner.profile.customerId] ?? String(partner.profile.customCycleDays ?? '')} onChange={(event) => setCustomDaysDraft((current) => ({ ...current, [partner.profile.customerId]: event.target.value }))} onBlur={(event) => void setCustomDays(partner, Number(event.target.value))} /> : <small>{partner.profile.cycle ? cycles[partner.profile.cycle] : 'Planejamento não definido'}</small>}</td>
        <td>{partner.products.length}</td><td>{partner.alerts.length}</td><td><button className="btn btn--secondary" type="button" onClick={() => void openPartner(partner)}>{openedId === partner.profile.customerId ? 'Atualizar' : 'Abrir parceiro'}</button></td>
      </tr>)}</tbody></table></div>}
    </section>
    {opened ? <>
      <section className="panel"><div className="panel__header"><div><h3>{opened.customer?.company ?? opened.customer?.name ?? opened.profile.customerId}</h3><p className="panel__description">{opened.customer?.name} · {opened.customer?.phone}</p></div><button className="btn btn--secondary" type="button" onClick={() => setOpenedId('')}>Fechar</button></div>
        <h4>Condições comerciais</h4>{opened.profile.conditions ? <dl className="report-facts"><div><dt>Desconto</dt><dd>{opened.profile.conditions.discountPercent === undefined ? 'Não definido' : `${opened.profile.conditions.discountPercent}%`}</dd></div><div><dt>Prazo autorizado</dt><dd>{opened.profile.conditions.paymentTermDays === undefined ? 'Não definido' : `${opened.profile.conditions.paymentTermDays} dias`}</dd></div><div><dt>Forma de pagamento</dt><dd>{opened.profile.conditions.paymentMethod ?? 'Não definida'}</dd></div><div><dt>Limite</dt><dd>{opened.profile.conditions.creditLimit === undefined ? 'Não definido' : `R$ ${opened.profile.conditions.creditLimit.toFixed(2)}`}</dd></div><div><dt>Prioridade</dt><dd>{opened.profile.conditions.servicePriority ?? 'Não definida'}</dd></div></dl> : <p className="table-state">Condições comerciais não configuradas.</p>}
        <p>Ciclo: <strong>{opened.profile.cycle ? cycles[opened.profile.cycle] : 'Não definido'}{opened.profile.cycle === 'custom' && opened.profile.customCycleDays ? ` · ${opened.profile.customCycleDays} dias` : ''}</strong>. Sem obrigação de compra.</p>
      </section>
      <section className="panel"><div className="panel__header"><div><h3>Produtos acompanhados</h3><p className="panel__description">Consumo calculado apenas a partir das compras detalhadas registradas.</p></div></div>
        {!opened.products.length ? <p className="table-state">Dados insuficientes para previsão confiável. Este parceiro ainda não tem linhas de pedido detalhadas.</p> : <div className="table-scroll"><table className="table"><thead><tr><th>Produto</th><th>Qtd. última compra</th><th>Última compra</th><th>Frequência</th><th>Consumo estimado</th><th>Previsão / status</th></tr></thead><tbody>{opened.products.map((item) => <tr key={item.consumption.productId}>
          <td><strong>{item.product?.name ?? item.consumption.productId}</strong></td><td>{quantity(item.consumption.lastQuantity)}</td><td>{dateLabel(item.consumption.lastPurchase)}</td><td>{item.consumption.averageIntervalDays === undefined ? 'Uma compra registrada' : `A cada ${quantity(item.consumption.averageIntervalDays)} dias`}</td>
          <td>{item.consumption.estimatedDailyConsumption === undefined ? 'Dados insuficientes' : `${quantity(item.consumption.estimatedDailyConsumption)} un./dia · média ${quantity(item.consumption.averageQuantityPerPurchase)} por compra · tendência ${item.consumption.trend}`}</td>
          <td>{item.prediction?.replenishmentWindow ? `Reposição prevista ${dateLabel(item.prediction.replenishmentWindow.start)}–${dateLabel(item.prediction.replenishmentWindow.end)} · quantidade estimada ${quantity(item.prediction.recommendedQuantity)} · confiabilidade ${item.prediction.confidence}` : item.prediction?.depletionWindow ? `Esgotamento ${dateLabel(item.prediction.depletionWindow.start)}–${dateLabel(item.prediction.depletionWindow.end)} · confiança ${item.prediction.confidence}` : item.status}</td>
        </tr>)}</tbody></table></div>}
      </section>
      <section className="panel"><div className="panel__header"><div><h3>Histórico de compras</h3><p className="panel__description">Produto, quantidade, data, origem, preço e intervalo observado.</p></div></div>
        {!opened.products.some((item) => item.consumption.purchases.length) ? <p className="table-state">Nenhuma linha detalhada de compra registrada.</p> : <div className="table-scroll"><table className="table"><thead><tr><th>Produto</th><th>Qtd.</th><th>Data</th><th>Pedido / origem</th><th>Preço unitário</th><th>Intervalo</th></tr></thead><tbody>{opened.products.flatMap((item) => item.consumption.purchases.map((record) => <tr key={`${record.orderId}-${record.productId}`}><td>{item.product?.name ?? record.productId}</td><td>{record.quantity}</td><td>{dateLabel(record.purchasedAt)}</td><td>{record.orderId} · {record.source}</td><td>R$ {record.unitPrice.toFixed(2)}</td><td>{record.intervalSincePreviousDays === undefined ? 'Primeira compra registrada' : `${record.intervalSincePreviousDays} dias`}</td></tr>))}</tbody></table></div>}
      </section>
      <section className="panel"><div className="panel__header"><div><h3>Alertas e oportunidades</h3><p className="panel__description">Toda recomendação exige confirmação do parceiro antes de qualquer pedido.</p></div></div>
        {opened.alerts.map((alert) => <p key={alert} role="status">{alert}</p>)}
        {opened.products.some((item) => item.prediction?.replenishmentWindow) ? <p>Reposição recomendada. Confirme com o parceiro antes de gerar pedido; nenhuma ação automática será executada.</p> : null}
        <h4>Produtos sem compra registrada neste histórico</h4>{opened.opportunities.length ? <ul>{opened.opportunities.map((product) => <li key={product.id}>{product.name}</li>)}</ul> : <p className="table-state">Sem histórico detalhado para identificar oportunidades.</p>}
        <p>{opened.predictionStatus === 'insufficient-data' ? 'Dados insuficientes para previsão confiável' : opened.predictionStatus === 'model-unavailable' ? 'Nenhuma previsão ML validada disponível para este parceiro/produto' : 'Previsão ML disponível; quantidade e janela são estimadas, sem observação de estoque físico'}.</p>
      </section>
    </> : null}
  </div>;
}
