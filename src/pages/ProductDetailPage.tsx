import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { authService } from '../services/authService';
import { inventoryService } from '../services/inventoryService';
import { pricingService } from '../services/pricingService';
import { productService } from '../services/productService';
import type { CostHistoryEntry, InventoryMovement, PriceHistoryEntry, PricingReviewRow, Product } from '../types';
export function ProductDetailPage() {
  const { id } = useParams();
  const [product, setProduct] = useState<Product | null>(null);
  const [costEntries, setCostEntries] = useState<CostHistoryEntry[]>([]);
  const [priceEntries, setPriceEntries] = useState<PriceHistoryEntry[]>([]);
  const [stockEntries, setStockEntries] = useState<InventoryMovement[]>([]);
  const [priceReview, setPriceReview] = useState<PricingReviewRow | null>(null);
  const [isRecalculating, setIsRecalculating] = useState(false);
  const [isApprovingPrice, setIsApprovingPrice] = useState(false);
  const [pricingFeedback, setPricingFeedback] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const canManagePricing = authService.can('manage_pricing');
  useEffect(() => {
    const loadProduct = async () => {
      if (!id) return;
      try {
        const nextProduct = await productService.getById(id); setProduct(nextProduct ?? null);
        const [nextCostEntries, nextPriceEntries, nextStockEntries] = await Promise.all([productService.getCostHistory(id), productService.getPriceHistory(id), inventoryService.getMovements(id)]);
        setCostEntries(nextCostEntries); setPriceEntries(nextPriceEntries); setStockEntries(nextStockEntries);
      } catch { setErrorMessage('N\u00e3o foi poss\u00edvel carregar o produto.'); } finally { setIsLoading(false); }
    };
    loadProduct();
  }, [id]);
  const recalculatePrice = async () => {
    if (!id) return;
    setIsRecalculating(true);
    setPricingFeedback('');
    try {
      setPriceReview(await pricingService.recalculateProduct(id));
    } catch (error) {
      setPricingFeedback(error instanceof Error ? error.message : 'Não foi possível recalcular o preço.');
    } finally {
      setIsRecalculating(false);
    }
  };
  const approvePrice = async () => {
    if (!id || !priceReview) return;
    setIsApprovingPrice(true);
    setPricingFeedback('');
    try {
      await pricingService.approveRecommendedPrice(id, priceReview.recommendedPrice);
      const [nextProduct, nextPriceEntries] = await Promise.all([
        productService.getById(id),
        productService.getPriceHistory(id),
      ]);
      setProduct(nextProduct ?? null);
      setPriceEntries(nextPriceEntries);
      setPriceReview(null);
      setPricingFeedback('Preço recomendado aprovado e histórico atualizado.');
    } catch (error) {
      setPricingFeedback(error instanceof Error ? error.message : 'Não foi possível aprovar o preço recomendado.');
    } finally {
      setIsApprovingPrice(false);
    }
  };
  if (isLoading) return <div className="page-shell"><LoadingState message="Carregando os dados do produto…" /></div>;
  if (errorMessage) return <div className="page-shell"><ErrorState message={errorMessage} /></div>;
  if (!product) return <div className="page-shell"><EmptyState title="Produto n&atilde;o encontrado" description="O item pode ter sido removido ou o endere&ccedil;o est&aacute; incorreto." action={<Link to="/produtos" className="btn btn--secondary">Voltar ao cat&aacute;logo</Link>} /></div>;
  return <><Header title={product.name} breadcrumb="Cat&aacute;logo / Produtos / Detalhe" /><div className="page-shell"><PageHeader title={product.name} description="Dados comerciais e hist&oacute;rico de custo, pre&ccedil;o e movimenta&ccedil;&atilde;o." actions={<>{canManagePricing ? <button className="btn btn--secondary" type="button" onClick={() => void recalculatePrice()} disabled={isRecalculating}>{isRecalculating ? 'Recalculando…' : 'Recalcular preço deste produto'}</button> : null}<Link to="/precificacao" className="btn btn--secondary">Ver precificação</Link><Link to="/produtos" className="btn btn--primary">Voltar ao cat&aacute;logo</Link></>} />
    {pricingFeedback ? <div className="inline-feedback" role="status">{pricingFeedback}</div> : null}
    {priceReview ? <section className="panel"><div className="panel__header"><div><h3>Recomendação individual de preço</h3><p className="panel__description">Calculada somente para este produto, usando seu custo atual. O preço só muda após aprovação.</p></div></div><div className="product-detail__summary"><div className="summary-row"><span>Preço atual</span><strong>R$ {priceReview.currentPrice.toFixed(2)}</strong></div><div className="summary-row"><span>Custo utilizado</span><strong>R$ {priceReview.realCost.toFixed(2)}</strong></div><div className="summary-row"><span>Preço recomendado</span><strong>R$ {priceReview.recommendedPrice.toFixed(2)}</strong></div><div className="summary-row"><span>Faixa permitida</span><strong>R$ {priceReview.minimumPrice.toFixed(2)} – R$ {priceReview.maximumPrice.toFixed(2)}</strong></div></div>{priceReview.recommendedPrice > 0 ? <div className="page-header__actions"><button className="btn btn--primary" type="button" onClick={() => void approvePrice()} disabled={isApprovingPrice}>{isApprovingPrice ? 'Aplicando…' : 'Aprovar preço recomendado'}</button><button className="btn btn--secondary" type="button" onClick={() => setPriceReview(null)} disabled={isApprovingPrice}>Cancelar</button></div> : <p className="admin-modal__hint">O custo do produto é zero; registre uma compra com custo antes de aprovar uma recomendação.</p>}</section> : null}
    <section className="product-detail"><div className="product-detail__image" style={{ backgroundImage: `url(${product.image})` }} role="img" aria-label={product.name} /><div className="product-detail__summary"><div className="summary-row"><span>Categoria</span><strong>{product.category}</strong></div><div className="summary-row"><span>Fornecedor</span><strong>{product.supplier}</strong></div><div className="summary-row"><span>Custo</span><strong>R$ {product.cost.toFixed(2)}</strong></div><div className="summary-row"><span>Pre&ccedil;o</span><strong>R$ {product.price.toFixed(2)}</strong></div><div className="summary-row"><span>Margem</span><strong>{product.margin}%</strong></div><div className="summary-row"><span>Markup</span><strong>{product.markup}%</strong></div><div className="summary-row"><span>Estoque</span><strong>{product.stock} unidades</strong></div><div className="summary-row"><span>Estoque m&iacute;nimo</span><strong>{product.minStock}</strong></div></div></section>
    <section className="panel"><div className="panel__header"><div><h3>Hist&oacute;rico do produto</h3><p className="panel__description">Altera&ccedil;&otilde;es registradas pelos fluxos de compra, pre&ccedil;o e estoque.</p></div></div><div className="history-grid"><div className="history-block"><h4>Custos</h4><ul>{costEntries.length ? costEntries.map((entry) => <li key={entry.id}>R$ {entry.newCost.toFixed(2)} em {entry.date}</li>) : <li>Nenhum custo registrado.</li>}</ul></div><div className="history-block"><h4>Pre&ccedil;os</h4><ul>{priceEntries.length ? priceEntries.map((entry) => <li key={entry.id}>R$ {entry.newPrice.toFixed(2)} em {entry.date}</li>) : <li>Nenhum pre&ccedil;o registrado.</li>}</ul></div><div className="history-block"><h4>Estoque</h4><ul>{stockEntries.length ? stockEntries.map((entry) => <li key={entry.id}>{entry.quantity} unidades em {entry.date}</li>) : <li>Sem movimenta&ccedil;&atilde;o registrada.</li>}</ul></div></div></section>
  </div></>;
}
