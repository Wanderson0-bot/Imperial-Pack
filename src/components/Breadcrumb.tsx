type BreadcrumbProps = {
  items: Array<{ label: string; href?: string }>;
};

export function Breadcrumb({ items }: BreadcrumbProps) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {items.map((item, index) => (
        <span key={`${item.label}-${index}`} className="breadcrumb__item">
          {item.href ? <a href={item.href}>{item.label}</a> : <span>{item.label}</span>}
          {index < items.length - 1 ? <span className="breadcrumb__separator">/</span> : null}
        </span>
      ))}
    </nav>
  );
}
