import { FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { productService } from '../services/productService';
import { supplierService, type SupplierInput } from '../services/supplierService';
import type { Product, Supplier } from '../types';

type SupplierForm = { name: string; email: string; phone: string; location: string; notes: string; minimumOrder: string; deliveryDays: string; productIds: string[] };
const blankSupplier: SupplierForm = { name: '', email: '', phone: '', location: '', notes: '', minimumOrder: '', deliveryDays: '', productIds: [] };
const currency = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function SuppliersPage() {
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [supplierForm, setSupplierForm] = useState<SupplierForm>(blankSupplier);
  const [editingSupplier, setEditingSupplier] = useState<Supplier | null>(null);
  const [showSupplierForm, setShowSupplierForm] = useState(false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [searchError, setSearchError] = useState('');

  const loadData = async () => {
    const [nextSuppliers, nextProducts] = await Promise.all([supplierService.getAll(), productService.getAll()]);
    setSuppliers(nextSuppliers);
    setProducts(nextProducts);
  };

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const nextSuppliers = await supplierService.getAll(search);
        if (active) { setSuppliers(nextSuppliers); setSearchError(''); }
      } catch {
        if (active) setSearchError('Não foi possível consultar fornecedores na API.');
      } finally { if (active) setIsLoading(false); }
    };
    void load();
    return () => { active = false; };
  }, [search]);

  useEffect(() => {
    let active = true;
    void productService.getAll()
      .then((nextProducts) => { if (active) setProducts(nextProducts); })
      .catch(() => { if (active) setSearchError('Não foi possível carregar produtos para associar.'); });
    return () => { active = false; };
  }, []);

  const openCreate = () => { setEditingSupplier(null); setSupplierForm(blankSupplier); setShowSupplierForm(true); setError(''); };
  const openEdit = (supplier: Supplier) => {
    setEditingSupplier(supplier);
    setShowSupplierForm(true);
    setSupplierForm({ name: supplier.name, email: supplier.email ?? '', phone: supplier.phone ?? '', location: supplier.location ?? '', notes: supplier.observations ?? '', minimumOrder: supplier.minimumOrder == null ? '' : String(supplier.minimumOrder), deliveryDays: supplier.deliveryDays == null ? '' : String(supplier.deliveryDays), productIds: supplier.productIds ?? [] });
    setError('');
  };

  const saveSupplier = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (supplierForm.productIds.length !== new Set(supplierForm.productIds).size) { setError('Cada produto pode ser selecionado apenas uma vez.'); return; }
    const input: SupplierInput = {
      name: supplierForm.name.trim(), email: supplierForm.email.trim() || undefined, phone: supplierForm.phone.trim() || undefined,
      location: supplierForm.location.trim(), notes: supplierForm.notes.trim() || undefined,
      minimum_order: supplierForm.minimumOrder ? Number(supplierForm.minimumOrder) : undefined,
      delivery_days: supplierForm.deliveryDays ? Number(supplierForm.deliveryDays) : undefined,
      product_ids: supplierForm.productIds,
    };
    if (input.minimum_order !== undefined && (!Number.isFinite(input.minimum_order) || input.minimum_order < 0)) { setError('Pedido mínimo deve ser maior ou igual a zero.'); return; }
    if (input.delivery_days !== undefined && (!Number.isInteger(input.delivery_days) || input.delivery_days < 0)) { setError('Prazo de entrega deve ser um número inteiro não negativo.'); return; }
    setIsSaving(true);
    setError('');
    try {
      if (editingSupplier) await supplierService.update(editingSupplier.id, input);
      else await supplierService.create(input);
      setShowSupplierForm(false);
      setEditingSupplier(null);
      setFeedback(editingSupplier ? 'Fornecedor atualizado.' : 'Fornecedor cadastrado.');
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível salvar o fornecedor.');
    } finally { setIsSaving(false); }
  };

  const toggleProduct = (productId: string) => setSupplierForm((current) => ({ ...current, productIds: current.productIds.includes(productId) ? current.productIds.filter((id) => id !== productId) : [...current.productIds, productId] }));

  return <>
    <Header title="Fornecedores" breadcrumb="Comercial / Fornecedores" />
    <div className="page-shell">
      <PageHeader title="Fornecedores" description="Gerencie contatos, localização, produtos fornecidos e custos derivados das compras." actions={<button className="btn btn--primary" type="button" onClick={openCreate}>+ Adicionar fornecedor</button>} />
      {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
      {searchError ? <ErrorState message={searchError} /> : null}
      <section className="panel">
        <div className="toolbar"><input aria-label="Buscar fornecedores" placeholder="Buscar por nome, contato ou localização" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        <div className="panel__header"><div><h3>Base de fornecedores</h3><p className="panel__description">Última compra e custo por produto são derivados do histórico registrado.</p></div><span className="page-header__meta">{suppliers.length} fornecedores</span></div>
        {isLoading ? <LoadingState message="Carregando fornecedores…" /> : error && !suppliers.length ? <ErrorState message={error} /> : suppliers.length ? <DataTable label="Fornecedores" columns={<><th>Fornecedor</th><th>Contato</th><th>Localização</th><th>Produtos / último custo</th><th>Última compra</th><th>Ações</th></>} rows={suppliers.map((supplier) => <tr key={supplier.id}><td><strong>{supplier.name}</strong><small>{supplier.observations}</small></td><td>{supplier.contact || '—'}</td><td>{supplier.location || '—'}</td><td>{supplier.productCosts?.length ? <div className="supplier-product-costs">{supplier.productCosts.map((item) => <span key={item.id}><strong>{item.name}</strong><small>{item.lastCost === null ? 'Sem compra registrada' : `${currency.format(item.lastCost)} · ${item.lastPurchase ?? '—'}`}</small></span>)}</div> : 'Nenhum produto associado'}</td><td>{supplier.lastPurchase || 'Nenhuma compra'}</td><td><div className="commercial-row-actions"><button className="btn btn--secondary" type="button" onClick={() => openEdit(supplier)}>Editar</button><Link className="btn btn--primary" to={`/compras/nova?supplierId=${encodeURIComponent(supplier.id)}`}>Registrar compra</Link></div></td></tr>)} /> : <EmptyState title="Nenhum fornecedor cadastrado" description="Cadastre fornecedores e associe os produtos existentes que eles fornecem." />}
      </section>
    </div>
    {showSupplierForm ? <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowSupplierForm(false); }}><form className="admin-modal commercial-modal" role="dialog" aria-modal="true" aria-labelledby="supplier-form-title" onSubmit={(event) => void saveSupplier(event)}>
      <header className="admin-modal__header"><div><span className="eyebrow">COMERCIAL</span><h2 id="supplier-form-title">{editingSupplier ? 'Editar fornecedor' : 'Adicionar fornecedor'}</h2></div><button type="button" aria-label="Fechar" onClick={() => setShowSupplierForm(false)}>×</button></header>
      <div className="commercial-form-grid">
        <label>Nome<input required minLength={2} maxLength={180} value={supplierForm.name} onChange={(event) => setSupplierForm((current) => ({ ...current, name: event.target.value }))} /></label>
        <label>Localização / endereço<input required minLength={2} maxLength={240} value={supplierForm.location} onChange={(event) => setSupplierForm((current) => ({ ...current, location: event.target.value }))} /></label>
        <label>E-mail<input type="email" value={supplierForm.email} onChange={(event) => setSupplierForm((current) => ({ ...current, email: event.target.value }))} /></label>
        <label>Telefone<input type="tel" value={supplierForm.phone} onChange={(event) => setSupplierForm((current) => ({ ...current, phone: event.target.value }))} /></label>
        <label>Pedido mínimo<input type="number" min="0" step="0.01" value={supplierForm.minimumOrder} onChange={(event) => setSupplierForm((current) => ({ ...current, minimumOrder: event.target.value }))} /></label>
        <label>Prazo de entrega (dias)<input type="number" min="0" step="1" value={supplierForm.deliveryDays} onChange={(event) => setSupplierForm((current) => ({ ...current, deliveryDays: event.target.value }))} /></label>
        <label className="commercial-form-grid__wide">Observações<textarea rows={2} value={supplierForm.notes} onChange={(event) => setSupplierForm((current) => ({ ...current, notes: event.target.value }))} /></label>
      </div>
      <fieldset className="supplier-product-picker"><legend>Produtos fornecidos</legend><p className="admin-modal__hint">Selecione produtos já cadastrados; um produto pode ter vários fornecedores.</p>{products.length ? <div>{products.map((product) => <label key={product.id}><input type="checkbox" checked={supplierForm.productIds.includes(product.id)} onChange={() => toggleProduct(product.id)} /><span>{product.name}<small>{product.category} · {currency.format(product.cost)} custo atual</small></span></label>)}</div> : <p>Nenhum produto disponível no catálogo.</p>}</fieldset>
      {error ? <ErrorState message={error} /> : null}
      <footer className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setShowSupplierForm(false)}>Cancelar</button><button type="submit" className="btn btn--primary" disabled={isSaving}>{isSaving ? 'Salvando…' : 'Salvar fornecedor'}</button></footer>
    </form></div> : null}
  </>;
}