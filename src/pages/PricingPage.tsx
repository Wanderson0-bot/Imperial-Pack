import { useEffect, useState } from 'react';
import { Header } from '../components/Header';
import { PageHeader } from '../components/PageHeader';
import { Section } from '../components/Section';
import { DataTable } from '../components/DataTable';
import { StatusBadge } from '../components/StatusBadge';
import { EmptyState } from '../components/EmptyState';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/LoadingState';
import { pricingService } from '../services/pricingService';
import type { PricingReviewRow } from '../types';
export function PricingPage() {
  const [rows, setRows] = useState<PricingReviewRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');
  const refreshRows = async () => { setIsLoading(true); setErrorMessage(''); try { setRows(await pricingService.getReviewRows()); } catch { setErrorMessage('N\u00e3o foi poss\u00edvel carregar a revis\u00e3o de pre\u00e7os.'); } finally { setIsLoading(false); } };
  useEffect(() => { refreshRows(); }, []);
  const approve = async (row: PricingReviewRow) => { await pricingService.approveRecommendedPrice(row.productId, row.recommendedPrice); await refreshRows(); };
  return <><Header title="Precifica&ccedil;&atilde;o" breadcrumb="Cat&aacute;logo / Precifica&ccedil;&atilde;o" /><div className="page-shell"><PageHeader title="Precifica&ccedil;&atilde;o" description="Revise custo, margem e pre&ccedil;o recomendado antes de aplicar altera&ccedil;&otilde;es." actions={<button className="btn btn--primary" type="button" onClick={refreshRows}>Recalcular pre&ccedil;os</button>} /><Section title="Revis&atilde;o de pre&ccedil;os" description={`${rows.length} produtos dispon&iacute;veis para an&aacute;lise`}>
    {isLoading ? <LoadingState message="Atualizando recomenda&ccedil;&otilde;es de pre&ccedil;o…" /> : errorMessage ? <ErrorState message={errorMessage} /> : rows.length === 0 ? <EmptyState title="Tudo revisado" description="N&atilde;o h&aacute; produtos dispon&iacute;veis para revis&atilde;o de pre&ccedil;o." /> : <DataTable label="Revis&atilde;o de pre&ccedil;os" columns={<><th>Produto</th><th>Custo real</th><th>Pre&ccedil;o atual</th><th>Margem</th><th>Markup</th><th>Recomendado</th><th>Situa&ccedil;&atilde;o</th><th>A&ccedil;&atilde;o</th></>} rows={rows.map((row) => <tr key={row.productId}><td><strong>{row.productName}</strong></td><td>R$ {row.realCost.toFixed(2)}</td><td>R$ {row.currentPrice.toFixed(2)}</td><td>{row.margin.toFixed(2)}%</td><td>{row.markup.toFixed(2)}%</td><td><strong>R$ {row.recommendedPrice.toFixed(2)}</strong></td><td><StatusBadge tone={row.needsReview ? 'warning' : 'info'}>{row.situation}</StatusBadge></td><td><button className="btn btn--secondary" type="button" onClick={() => void approve(row)}>Aprovar</button></td></tr>)} />}
  </Section></div></>;
}
