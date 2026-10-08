import { FormEvent, useEffect, useMemo, useState } from 'react';
import { DataTable } from '../components/DataTable';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { Header } from '../components/Header';
import { LoadingState } from '../components/LoadingState';
import { PageHeader } from '../components/PageHeader';
import { customerService, type CustomerInput } from '../services/customerService';
import { orderService } from '../services/orderService';
import { productService } from '../services/productService';
import type { Customer, Product } from '../types';

type CustomerForm = CustomerInput & { addressStreet: string; addressNumber: string; addressDistrict: string; addressCity: string; addressState: string; postalCode: string };
type SaleLine = { productId: string; quantity: string };

const blankCustomer: CustomerForm = { name: '', company: '', email: '', phone: '', city: '', notes: '', addressStreet: '', addressNumber: '', addressDistrict: '', addressCity: '', addressState: '', postalCode: '' };
const today = () => new Date().toISOString().slice(0, 10);
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [search, setSearch] = useState('');
  const [showCustomerForm, setShowCustomerForm] = useState(false);
  const [editingCustomer, setEditingCustomer] = useState<Customer | null>(null);
  const [saleCustomer, setSaleCustomer] = useState<Customer | null>(null);
  const [customerForm, setCustomerForm] = useState<CustomerForm>(blankCustomer);
  const [saleDate, setSaleDate] = useState(today());
  const [saleNotes, setSaleNotes] = useState('');
  const [saleLines, setSaleLines] = useState<SaleLine[]>([]);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const loadData = async () => {
    const [nextCustomers, nextProducts] = await Promise.all([customerService.getAll(search), productService.getAll()]);
    setCustomers(nextCustomers);
    setProducts(nextProducts);
  };

  useEffect(() => {
    let active = true;
    void productService.getAll()
      .then((nextProducts) => { if (active) setProducts(nextProducts); })
      .catch(() => { if (active) setError('Não foi possível carregar o catálogo da API.'); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    setError('');
    void customerService.getAll(search)
      .then((nextCustomers) => { if (active) setCustomers(nextCustomers); })
      .catch(() => { if (active) setError('Não foi possível carregar os clientes da API.'); })
      .finally(() => { if (active) setIsLoading(false); });
    return () => { active = false; };
  }, [search]);

  const saleTotalCents = useMemo(() => saleLines.reduce((total, line) => {
    const product = products.find((entry) => entry.id === line.productId);
    const quantity = Number(line.quantity);
    if (!product || !Number.isFinite(quantity) || quantity <= 0) return total;
    return total + Math.round(Math.round(product.price * 100) * Math.round(quantity * 1000) / 1000);
  }, 0), [saleLines, products]);

  const openSale = (customer: Customer) => {
    setSaleCustomer(customer);
    setSaleDate(today());
    setSaleNotes('');
    setSaleLines([{ productId: products[0]?.id ?? '', quantity: '1' }]);
    setError('');
  };

  const saveCustomer = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    const hasAddress = [customerForm.addressStreet, customerForm.addressNumber, customerForm.addressDistrict, customerForm.addressCity, customerForm.addressState, customerForm.postalCode].some((value) => value.trim());
    const input: CustomerInput = {
      name: customerForm.name.trim(), company: customerForm.company?.trim() || undefined,
      email: customerForm.email?.trim() || undefined, phone: customerForm.phone?.trim() || undefined,
      city: customerForm.addressCity.trim() || customerForm.city?.trim() || undefined,
      notes: customerForm.notes?.trim() || undefined,
      ...(hasAddress ? { address: { label: 'Principal', street: customerForm.addressStreet.trim() || null, number: customerForm.addressNumber.trim() || null, district: customerForm.addressDistrict.trim() || null, city: customerForm.addressCity.trim() || null, state: customerForm.addressState.trim() || null, postal_code: customerForm.postalCode.trim() || null } } : {}),
    };
    setIsSaving(true);
    try {
      const customer = editingCustomer ? await customerService.update(editingCustomer.id, input) : await customerService.create(input);
      setShowCustomerForm(false);
      setEditingCustomer(null);
      setCustomerForm(blankCustomer);
      setFeedback(editingCustomer ? `Cliente ${customer.name} atualizado.` : `Cliente ${customer.name} cadastrado.`);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível cadastrar o cliente.');
    } finally { setIsSaving(false); }
  };

  const openCustomer = (customer?: Customer) => {
    setEditingCustomer(customer ?? null);
    setCustomerForm(customer ? {
      name: customer.name, company: customer.company, email: customer.email ?? '', phone: customer.phone,
      city: customer.city ?? '', notes: customer.notes ?? '', addressStreet: customer.address?.street ?? '',
      addressNumber: customer.address?.number ?? '', addressDistrict: customer.address?.district ?? '',
      addressCity: customer.address?.city ?? '', addressState: customer.address?.state ?? '',
      postalCode: customer.address?.postal_code ?? '',
    } : blankCustomer);
    setShowCustomerForm(true);
    setError('');
  };

  const saveSale = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!saleCustomer || !saleDate || !saleLines.length || saleLines.some((line) => !line.productId || !Number.isFinite(Number(line.quantity)) || Number(line.quantity) <= 0)) {
      setError('Informe data, cliente e produtos com quantidades maiores que zero.');
      return;
    }
    setError('');
    setIsSaving(true);
    try {
      const order = await orderService.createSale({ customerId: saleCustomer.id, customerName: saleCustomer.name, date: saleDate, notes: saleNotes.trim(), items: saleLines.map((line) => ({ productId: line.productId, quantity: Number(line.quantity) })) });
      setSaleCustomer(null);
      setFeedback(`Venda ${order.id} registrada como pedido novo; indicadores do cliente serão recalculados pela API.`);
      await loadData();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Não foi possível registrar a venda.');
    } finally { setIsSaving(false); }
  };

  return <>
    <Header title="Clientes" breadcrumb="Comercial / Clientes" />
    <div className="page-shell">
      <PageHeader title="Clientes" description="Cadastre clientes uma única vez e acompanhe pedidos e histórico comercial." actions={<button className="btn btn--primary" type="button" onClick={() => openCustomer()}>+ Adicionar cliente</button>} />
      {feedback ? <div className="inline-feedback" role="status">{feedback}</div> : null}
      {error && !showCustomerForm && !saleCustomer ? <ErrorState message={error} /> : null}
      <section className="panel">
        <div className="toolbar"><input aria-label="Buscar clientes" placeholder="Buscar por nome, empresa, e-mail ou telefone" value={search} onChange={(event) => setSearch(event.target.value)} /></div>
        <div className="panel__header"><div><h3>Carteira de clientes</h3><p className="panel__description">Pedidos, total comprado, ticket médio e última compra calculados pelo histórico não cancelado.</p></div><span className="page-header__meta">{customers.length} clientes</span></div>
        {isLoading ? <LoadingState message="Carregando clientes…" /> : error && !customers.length ? <ErrorState message={error} /> : customers.length ? <DataTable label="Carteira de clientes" columns={<><th>Nome</th><th>Empresa</th><th>Pedidos</th><th>Total comprado</th><th>Ticket médio</th><th>Última compra</th><th>Ações</th></>} rows={customers.map((customer) => <tr key={customer.id}><td><strong>{customer.name}</strong><small>{customer.email || customer.phone}</small></td><td>{customer.company || '—'}</td><td>{customer.orders ?? 0}</td><td>{money.format(customer.totalSpent ?? 0)}</td><td>{money.format(customer.averageTicket ?? 0)}</td><td>{customer.lastPurchase ? new Date(`${customer.lastPurchase}T12:00:00`).toLocaleDateString('pt-BR') : 'Nenhuma compra'}</td><td><div className="commercial-row-actions"><button className="btn btn--secondary" type="button" onClick={() => openCustomer(customer)}>Editar</button><button className="btn btn--primary" type="button" onClick={() => openSale(customer)}>Registrar venda</button></div></td></tr>)} /> : <EmptyState title="Nenhum cliente cadastrado" description="Adicione o primeiro cliente para começar a registrar o histórico comercial." />}
      </section>
    </div>

    {showCustomerForm ? <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setShowCustomerForm(false); }}><form className="admin-modal commercial-modal" role="dialog" aria-modal="true" aria-labelledby="customer-form-title" onSubmit={(event) => void saveCustomer(event)}>
      <header className="admin-modal__header"><div><span className="eyebrow">COMERCIAL</span><h2 id="customer-form-title">{editingCustomer ? 'Editar cliente' : 'Adicionar cliente'}</h2></div><button type="button" aria-label="Fechar" onClick={() => setShowCustomerForm(false)}>×</button></header>
      <div className="commercial-form-grid">
        <label>Nome<input required minLength={2} maxLength={180} value={customerForm.name} onChange={(event) => setCustomerForm((current) => ({ ...current, name: event.target.value }))} /></label>
        <label>Empresa<input value={customerForm.company} onChange={(event) => setCustomerForm((current) => ({ ...current, company: event.target.value }))} /></label>
        <label>E-mail<input type="email" value={customerForm.email} onChange={(event) => setCustomerForm((current) => ({ ...current, email: event.target.value }))} /></label>
        <label>Telefone<input type="tel" value={customerForm.phone} onChange={(event) => setCustomerForm((current) => ({ ...current, phone: event.target.value }))} /></label>
        <label>Rua<input value={customerForm.addressStreet} onChange={(event) => setCustomerForm((current) => ({ ...current, addressStreet: event.target.value }))} /></label>
        <label>Número<input value={customerForm.addressNumber} onChange={(event) => setCustomerForm((current) => ({ ...current, addressNumber: event.target.value }))} /></label>
        <label>Bairro<input value={customerForm.addressDistrict} onChange={(event) => setCustomerForm((current) => ({ ...current, addressDistrict: event.target.value }))} /></label>
        <label>Cidade<input value={customerForm.addressCity} onChange={(event) => setCustomerForm((current) => ({ ...current, addressCity: event.target.value }))} /></label>
        <label>UF<input maxLength={2} value={customerForm.addressState} onChange={(event) => setCustomerForm((current) => ({ ...current, addressState: event.target.value.toUpperCase() }))} /></label>
        <label>CEP<input value={customerForm.postalCode} onChange={(event) => setCustomerForm((current) => ({ ...current, postalCode: event.target.value }))} /></label>
        <label className="commercial-form-grid__wide">Observações<textarea rows={2} value={customerForm.notes} onChange={(event) => setCustomerForm((current) => ({ ...current, notes: event.target.value }))} /></label>
      </div>
      {error ? <ErrorState message={error} /> : null}
      <footer className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setShowCustomerForm(false)}>Cancelar</button><button type="submit" className="btn btn--primary" disabled={isSaving}>{isSaving ? 'Salvando…' : editingCustomer ? 'Salvar alterações' : 'Salvar cliente'}</button></footer>
    </form></div> : null}

    {saleCustomer ? <div className="admin-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setSaleCustomer(null); }}><form className="admin-modal commercial-modal" role="dialog" aria-modal="true" aria-labelledby="sale-form-title" onSubmit={(event) => void saveSale(event)}>
      <header className="admin-modal__header"><div><span className="eyebrow">CLIENTE · {saleCustomer.name}</span><h2 id="sale-form-title">Registrar venda</h2></div><button type="button" aria-label="Fechar" onClick={() => setSaleCustomer(null)}>×</button></header>
      <label>Cliente<input value={saleCustomer.company ? `${saleCustomer.name} · ${saleCustomer.company}` : saleCustomer.name} readOnly /></label>
      <label>Data da venda<input type="date" required value={saleDate} onChange={(event) => setSaleDate(event.target.value)} /></label>
      <div className="commercial-sale-lines"><div className="commercial-sale-lines__heading"><strong>Produtos</strong><button type="button" className="btn btn--secondary" onClick={() => setSaleLines((current) => [...current, { productId: products[0]?.id ?? '', quantity: '1' }])}>+ Adicionar produto</button></div>
            {saleLines.map((line, index) => {
              const product = products.find((item) => item.id === line.productId);
              const subtotalCents = product ? Math.round(Math.round(product.price * 100) * Math.round((Number(line.quantity) || 0) * 1000) / 1000) : 0;
              return <div className="commercial-sale-line" key={`sale-line-${index}`}><select aria-label="Produto da venda" required value={line.productId} onChange={(event) => setSaleLines((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, productId: event.target.value } : item))}><option value="">Selecione um produto</option>{products.map((item) => <option key={item.id} value={item.id}>{item.name} · {money.format(item.price)}</option>)}</select><input aria-label="Quantidade" type="number" min="0.001" step="0.001" required value={line.quantity} onChange={(event) => setSaleLines((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, quantity: event.target.value } : item))} /><span>{money.format(subtotalCents / 100)}</span><button type="button" className="btn btn--secondary" aria-label="Remover produto" onClick={() => setSaleLines((current) => current.filter((_, itemIndex) => itemIndex !== index))} disabled={saleLines.length === 1}>Remover</button></div>;
            })}
      </div>
      <label>Observações<textarea rows={2} value={saleNotes} onChange={(event) => setSaleNotes(event.target.value)} /></label>
      <div className="commercial-sale-total"><span>Total calculado</span><strong>{money.format(saleTotalCents / 100)}</strong></div>
      <p className="admin-modal__hint">A venda será registrada como pedido novo. O estoque só é consumido quando o pedido for confirmado.</p>
      {error ? <ErrorState message={error} /> : null}
      <footer className="admin-modal__actions"><button type="button" className="btn btn--secondary" onClick={() => setSaleCustomer(null)}>Cancelar</button><button type="submit" className="btn btn--primary" disabled={isSaving || !products.length}>{isSaving ? 'Salvando…' : 'Salvar venda'}</button></footer>
    </form></div> : null}
  </>;
}