import type { ReactNode } from 'react';
type DataTableProps = { columns: ReactNode; rows: ReactNode; label?: string };
export function DataTable({ columns, rows, label = 'Tabela de dados' }: DataTableProps) {
  return <div className="data-table-shell"><table className="data-table" aria-label={label}><thead><tr>{columns}</tr></thead><tbody>{rows}</tbody></table></div>;
}
