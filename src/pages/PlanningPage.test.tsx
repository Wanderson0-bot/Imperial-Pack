import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PlanningPage } from './PlanningPage';

describe('PlanningPage', () => {
  it('renders an accessible loading state while persistent data is loading', () => {
    const markup = renderToStaticMarkup(<PlanningPage />);
    expect(markup).toContain('role="status"');
    expect(markup).toContain('Carregando planejamentos');
  });
});
