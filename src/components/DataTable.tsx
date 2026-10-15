import type { ReactNode } from 'react';
type DataTableProps = { columns: ReactNode; rows: ReactNode; label?: string };
export function DataTable({ columns, rows, label = 'Tabela de dados' }: DataTableProps) {
  return <div className="data-table-shell" role="region" tabIndex={0} aria-label={`${label}. Use a rolagem horizontal para visualizar todas as colunas.`}><table className="data-table" aria-label={label}><thead><tr>{columns}</tr></thead><tbody>{rows}</tbody></table></div>;
}
