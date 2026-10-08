import { FormEvent, useEffect, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { Section } from '../components/Section';
import { StatusBadge } from '../components/StatusBadge';
import { inventoryService } from '../services/inventoryService';
import type { InventoryMovement } from '../types';

type InventoryBalance = { productId: string; name: string; current: number; minimum: number };
type StockStatus = 'Normal' | 'Baixo' | 'Crítico' | 'Sem estoque';

const statusFor = (balance: InventoryBalance): StockStatus => balance.current <= 0
  ? 'Sem estoque'
  : balance.current <= balance.minimum * 0.5
    ? 'Crítico'
    : balance.current <= balance.minimum
      ? 'Baixo'
      : 'Normal';

const statusTones: Record<StockStatus, 'success' | 'warning' | 'danger'> = {
  Normal: 'success',
  Baixo: 'warning',
  Crítico: 'danger',
  'Sem estoque': 'danger',
};

const movementLabel = (movement: InventoryMovement) => `${movement.type} de ${movement.quantity}`;

export function InventoryPage() {
  const [balances, setBalances] = useState<InventoryBalance[]>([]);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [quantityDelta, setQuantityDelta] = useState('');
  const [reason, setReason] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [feedback, setFeedback] = useState('');

  const loadData = async () => {
    setErrorMessage('');
    try {
      const [nextBalances, nextMovements] = await Promise.all([
        inventoryService.getBalances(),
        inventoryService.getMovements(),
      ]);
      setBalances(nextBalances);
      setMovements(nextMovements);
      setSelectedProductId((current) => current || nextBalances[0]?.productId || '');
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Não foi possível carregar o estoque.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { void loadData(); }, []);

  const submitAdjustment = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const delta = Number(quantityDelta);
    if (!selectedProductId || !Number.isFinite(delta) || delta === 0 || reason.trim().length < 3) {
      setErrorMessage('Selecione um produto, informe um ajuste diferente de zero e descreva o motivo.');
      return;
    }

    setIsSaving(true);
    setErrorMessage('');
    setFeedback('');
    try {
      await inventoryService.adjust(selectedProductId, delta, reason.trim());
      setQuantityDelta('');
      setReason('');
      setFeedback('Ajuste de estoque salvo.');
      await loadData();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Não foi possível salvar o ajuste de estoque.');
    } finally {
      setIsSaving(false);
    }
  };

  return <>
    <Header title="Estoque" breadcrumb="Estoque / Controle" />
    <div className="page-shell">
      <PageHeader title="Estoque" description="Monitoramento de entradas, saídas e situação crítica por produto." />
      {errorMessage ? <ErrorState message={errorMessage} /> : null}
      {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
      {isLoading ? <LoadingState message="Carregando saldos e movimentações..." /> : <>
        <Section title="Posição por produto" description={`${balances.length} produtos · saldos e limites consultados na API.`}>
          <DataTable columns={<><th>Produto</th><th>Estoque atual</th><th>Estoque mínimo</th><th>Situação</th></>} rows={balances.map((balance) => {
            const status = statusFor(balance);
            return <tr key={balance.productId}>
              <td><strong>{balance.name}</strong></td>
              <td>{balance.current}</td>
              <td>{balance.minimum}</td>
              <td><StatusBadge tone={statusTones[status]}>{status}</StatusBadge></td>
            </tr>;
          })} />
        </Section>
        <Section title="Ajuste manual" description="Registre uma variação com justificativa; o saldo não pode ficar negativo.">
          <form className="toolbar" onSubmit={(event) => void submitAdjustment(event)}>
            <select aria-label="Produto para ajuste" value={selectedProductId} onChange={(event) => setSelectedProductId(event.target.value)} required disabled={!balances.length}>
              <option value="">Selecione um produto</option>
              {balances.map((balance) => <option key={balance.productId} value={balance.productId}>{balance.name}</option>)}
            </select>
            <input aria-label="Variação de estoque" type="number" step="0.001" value={quantityDelta} onChange={(event) => setQuantityDelta(event.target.value)} placeholder="Variação (+/-)" required />
            <input aria-label="Motivo do ajuste" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Motivo do ajuste" minLength={3} required />
            <button className="btn btn--primary" type="submit" disabled={isSaving || !balances.length}>{isSaving ? 'Salvando...' : 'Salvar ajuste'}</button>
          </form>
        </Section>
        <Section title="Movimentações recentes" description="Histórico retornado pelo sistema de estoque.">
          <DataTable columns={<><th>Data</th><th>Produto</th><th>Movimento</th><th>Motivo</th></>} rows={movements.map((movement) => <tr key={movement.id}>
            <td>{movement.date}</td>
            <td>{balances.find((balance) => balance.productId === movement.productId)?.name ?? movement.productId}</td>
            <td>{movementLabel(movement)}</td>
            <td>{movement.reason}</td>
          </tr>)} />
        </Section>
      </>}
    </div>
  </>;
}
