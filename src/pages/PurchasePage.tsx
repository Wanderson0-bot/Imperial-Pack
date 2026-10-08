import { FormEvent, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { productService } from '../services/productService';
import { calculatePurchaseSummary, toCents } from '../services/purchaseCalculations';
import { purchaseService } from '../services/purchaseService';
import { supplierService } from '../services/supplierService';
import type { Product, PurchaseDraft, PurchaseDraftItem } from '../types';

type PurchaseRow = PurchaseDraftItem & { clientId: string };
type ItemForm = { productId: string; quantity: string; unitCost: string; discount: string; description: string };
type PurchaseForm = { supplierId: string; date: string; documentNumber: string; freight: string; observations: string };

const today = () => new Date().toISOString().slice(0, 10);
const initialPurchase = (supplierId = ''): PurchaseForm => ({ supplierId, date: today(), documentNumber: '', freight: '0.00', observations: '' });
const initialItem = (productId = ''): ItemForm => ({ productId, quantity: '1', unitCost: '', discount: '0.00', description: '' });
const parseAmount = (value: string) => value.trim() === '' ? 0 : Number(value);
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const formatCents = (value: number) => currency.format(value / 100);

const createClientId = () => {
  if (
    typeof crypto !== 'undefined' &&
    typeof crypto.randomUUID === 'function'
  ) {
    return crypto.randomUUID();
  }

  return `purchase-item-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
};

export function PurchasePage() {
  const [searchParams] = useSearchParams();
  const [products, setProducts] = useState<Product[]>([]);
  const [suppliers, setSuppliers] = useState<Array<{ id: string; name: string }>>([]);
  const [purchase, setPurchase] = useState<PurchaseForm>(initialPurchase());
  const [itemForm, setItemForm] = useState<ItemForm>(initialItem());
  const [items, setItems] = useState<PurchaseRow[]>([]);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState('');
  const [formError, setFormError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void Promise.all([productService.getAll(), supplierService.getActiveOptions()])
      .then(([nextProducts, nextSuppliers]) => {
        if (!active) return;
        setProducts(nextProducts);
        setSuppliers(nextSuppliers);
        const requestedSupplier = searchParams.get('supplierId');
        setPurchase((current) => ({ ...current, supplierId: nextSuppliers.some((supplier) => supplier.id === requestedSupplier) ? requestedSupplier ?? '' : current.supplierId || nextSuppliers[0]?.id || '' }));
        setItemForm((current) => ({ ...current, productId: current.productId || nextProducts[0]?.id || '' }));
      })
      .catch(() => { if (active) setLoadError('Não foi possível carregar fornecedores e produtos da API.'); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, []);

  const summary = useMemo(
    () => calculatePurchaseSummary(items, parseAmount(purchase.freight)),
    [items, purchase.freight],
  );

  const selectedProduct = products.find((product) => product.id === itemForm.productId);

  const resetItemForm = () => {
    setItemForm(initialItem(products[0]?.id ?? ''));
    setEditingItemId(null);
    setFormError('');
  };

  const saveItem = () => {
    setFormError('');
    const quantity = Number(itemForm.quantity);
    const unitCost = parseAmount(itemForm.unitCost);
    const discount = parseAmount(itemForm.discount);
    if (!itemForm.productId || !products.some((product) => product.id === itemForm.productId)) {
      setFormError('Selecione um produto cadastrado.');
      return;
    }
    if (!Number.isFinite(quantity) || quantity <= 0) {
      setFormError('A quantidade deve ser maior que zero.');
      return;
    }
    if (!Number.isFinite(unitCost) || unitCost < 0) {
      setFormError('O valor unitário não pode ser negativo.');
      return;
    }
    if (!Number.isFinite(discount) || discount < 0) {
      setFormError('O desconto não pode ser negativo.');
      return;
    }
    const candidate: PurchaseDraftItem = { productId: itemForm.productId, quantity, unitCost, discount, description: itemForm.description.trim() || undefined };
    const line = calculatePurchaseSummary([candidate], 0).lines[0];
    if (line.discountCents > line.grossCents) {
      setFormError('O desconto não pode ser maior que o valor bruto do item.');
      return;
    }
    const clientId = editingItemId ?? createClientId();
    setItems((current) => editingItemId
      ? current.map((item) => item.clientId === editingItemId ? { ...candidate, clientId } : item)
      : [...current, { ...candidate, clientId }]);
    setFeedback('');
    resetItemForm();
  };

  const editItem = (item: PurchaseRow) => {
    setEditingItemId(item.clientId);
    setItemForm({ productId: item.productId, quantity: String(item.quantity), unitCost: item.unitCost.toFixed(2), discount: item.discount.toFixed(2), description: item.description ?? '' });
    setFormError('');
    document.getElementById('purchase-item-product')?.focus();
  };

  const removeItem = (clientId: string) => {
    setItems((current) => current.filter((item) => item.clientId !== clientId));
    if (editingItemId === clientId) resetItemForm();
    setFeedback('');
  };

  const submitPurchase = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFeedback('');
    setFormError('');
    const freight = parseAmount(purchase.freight);
    if (!purchase.supplierId || !suppliers.some((supplier) => supplier.id === purchase.supplierId)) {
      setFormError('Selecione um fornecedor cadastrado.');
      return;
    }
    if (!purchase.date) {
      setFormError('Informe a data da compra.');
      return;
    }
    if (!Number.isFinite(freight) || freight < 0) {
      setFormError('O frete não pode ser negativo.');
      return;
    }
    if (!items.length) {
      setFormError('Adicione pelo menos um produto à compra.');
      return;
    }

    const draft: PurchaseDraft = {
      supplierId: purchase.supplierId,
      date: purchase.date,
      documentNumber: purchase.documentNumber.trim() || undefined,
      freight: toCents(freight) / 100,
      otherCosts: 0,
      observations: purchase.observations.trim() || undefined,
      items: items.map(({ clientId: _clientId, ...item }) => ({
        ...item,
        quantity: Math.round(item.quantity * 1000) / 1000,
        unitCost: toCents(item.unitCost) / 100,
        discount: toCents(item.discount) / 100,
      })),
    };

    setIsSaving(true);
    try {
      const result = await purchaseService.confirmPurchase(draft);
      setFeedback(`Compra ${result.purchase.id} registrada; estoque e custos históricos atualizados.`);
      setItems([]);
      setPurchase(initialPurchase(purchase.supplierId));
      resetItemForm();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Não foi possível registrar a compra.');
    } finally {
      setIsSaving(false);
    }
  };

  return <>
    <Header title="Nova compra" breadcrumb="Compras / Nova compra" />
    <div className="page-shell purchase-page">
      <PageHeader title="Nova compra" description="Registre o fornecedor, os produtos e os custos desta entrada." />
      {loadError ? <ErrorState message={loadError} /> : null}
      {isLoading ? <LoadingState message="Carregando fornecedores e produtos…" /> : null}
      {!isLoading && !loadError ? <form onSubmit={(event) => void submitPurchase(event)}>
        <section className="panel purchase-panel">
          <div className="panel__header"><div><h3>Dados gerais</h3><p className="panel__description">Identificação da nota e custos da compra.</p></div></div>
          <div className="purchase-general-grid">
            <div className="field"><label htmlFor="purchase-supplier">Fornecedor</label><select id="purchase-supplier" value={purchase.supplierId} onChange={(event) => setPurchase((current) => ({ ...current, supplierId: event.target.value }))} required><option value="" disabled>Selecione um fornecedor</option>{suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}</select></div>
            <div className="field"><label htmlFor="purchase-date">Data da compra</label><input id="purchase-date" type="date" value={purchase.date} onChange={(event) => setPurchase((current) => ({ ...current, date: event.target.value }))} required /></div>
            <div className="field"><label htmlFor="purchase-document">Número/documento <span className="purchase-optional">Opcional</span></label><input id="purchase-document" value={purchase.documentNumber} onChange={(event) => setPurchase((current) => ({ ...current, documentNumber: event.target.value }))} maxLength={100} /></div>
            <div className="field"><label htmlFor="purchase-freight">Frete</label><input id="purchase-freight" type="number" min="0" step="0.01" inputMode="decimal" value={purchase.freight} onChange={(event) => setPurchase((current) => ({ ...current, freight: event.target.value }))} required /></div>
            <div className="field purchase-observations"><label htmlFor="purchase-observations">Observações <span className="purchase-optional">Opcional</span></label><textarea id="purchase-observations" rows={2} value={purchase.observations} onChange={(event) => setPurchase((current) => ({ ...current, observations: event.target.value }))} maxLength={2000} /></div>
          </div>
        </section>

        <section className="panel purchase-panel">
          <div className="panel__header"><div><h3>Produtos da compra</h3><p className="panel__description">Inclua cada produto uma vez ou em linhas separadas, conforme a nota.</p></div></div>
          {!products.length ? <EmptyState title="Nenhum produto disponível" description="Cadastre ou ative produtos antes de registrar uma compra." /> : <>
            <div className="purchase-item-form">
              <div className="field purchase-item-form__product"><label htmlFor="purchase-item-product">Produto</label><select id="purchase-item-product" value={itemForm.productId} onChange={(event) => setItemForm((current) => ({ ...current, productId: event.target.value }))} required><option value="" disabled>Selecione um produto</option>{products.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></div>
              <div className="field"><label htmlFor="purchase-item-quantity">Quantidade</label><input id="purchase-item-quantity" type="number" min="0.001" step="0.001" inputMode="decimal" value={itemForm.quantity} onChange={(event) => setItemForm((current) => ({ ...current, quantity: event.target.value }))} required /></div>
              <div className="field"><label htmlFor="purchase-item-unit-cost">Valor unitário</label><input id="purchase-item-unit-cost" type="number" min="0" step="0.01" inputMode="decimal" value={itemForm.unitCost} onChange={(event) => setItemForm((current) => ({ ...current, unitCost: event.target.value }))} required /></div>
              <div className="field"><label htmlFor="purchase-item-discount">Desconto</label><input id="purchase-item-discount" type="number" min="0" step="0.01" inputMode="decimal" value={itemForm.discount} onChange={(event) => setItemForm((current) => ({ ...current, discount: event.target.value }))} /></div>
              <div className="field purchase-item-form__description"><label htmlFor="purchase-item-description">Descrição <span className="purchase-optional">Opcional</span></label><input id="purchase-item-description" value={itemForm.description} onChange={(event) => setItemForm((current) => ({ ...current, description: event.target.value }))} maxLength={1000} /></div>
              <div className="purchase-item-form__actions"><button type="button" className="btn btn--primary" onClick={saveItem}>{editingItemId ? 'Salvar produto' : '+ Adicionar produto'}</button>{editingItemId ? <button type="button" className="btn btn--secondary" onClick={resetItemForm}>Cancelar edição</button> : null}</div>
            </div>
            {selectedProduct ? <p className="purchase-current-product">Unidade cadastrada: {selectedProduct.unit}</p> : null}
            {items.length ? <DataTable label="Produtos da compra" columns={<><th>Produto</th><th>Quantidade</th><th>Valor unitário</th><th>Desconto</th><th>Subtotal</th><th>Ações</th></>} rows={items.map((item, index) => {
              const product = products.find((entry) => entry.id === item.productId);
              const amounts = summary.lines[index];
              return <tr key={item.clientId}><td><strong>{product?.name ?? 'Produto indisponível'}</strong>{item.description ? <small className="purchase-item-description">{item.description}</small> : null}</td><td>{item.quantity.toLocaleString('pt-BR', { maximumFractionDigits: 3 })}</td><td>{currency.format(item.unitCost)}</td><td>{formatCents(amounts.discountCents)}</td><td><strong>{formatCents(amounts.subtotalCents)}</strong></td><td><div className="purchase-row-actions"><button type="button" className="btn btn--secondary" onClick={() => editItem(item)}>Editar</button><button type="button" className="btn btn--secondary" onClick={() => removeItem(item.clientId)}>Remover</button></div></td></tr>;
            })} /> : <EmptyState title="Nenhum produto adicionado" description="Selecione um produto, informe quantidade e valores e adicione à compra." />}
          </>}
        </section>

        <section className="panel purchase-summary-panel" aria-labelledby="purchase-summary-title">
          <div className="panel__header"><div><h3 id="purchase-summary-title">Resumo financeiro</h3><p className="panel__description">Totais calculados a partir dos itens e do frete informado.</p></div></div>
          <dl className="purchase-summary">
            <div><dt>Subtotal dos produtos</dt><dd>{formatCents(summary.productsSubtotalCents)}</dd></div>
            <div><dt>Descontos</dt><dd>− {formatCents(summary.discountsCents)}</dd></div>
            <div><dt>Frete</dt><dd>{formatCents(summary.freightCents)}</dd></div>
            <div className="purchase-summary__total"><dt>Total da compra</dt><dd>{formatCents(summary.totalCents)}</dd></div>
          </dl>
          {formError ? <ErrorState message={formError} /> : null}
          {feedback ? <p className="purchase-feedback" role="status">{feedback}</p> : null}
          <div className="purchase-submit"><button type="submit" className="btn btn--primary" disabled={isSaving || isLoading || !suppliers.length || !items.length}>{isSaving ? 'Salvando compra…' : 'Salvar compra'}</button></div>
        </section>
      </form> : null}
    </div>
  </>;
}