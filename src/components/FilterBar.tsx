import type { ReactNode } from 'react';

type FilterBarProps = {
  children: ReactNode;
};

export function FilterBar({ children }: FilterBarProps) {
  return <div className="filter-bar">{children}</div>;
}
