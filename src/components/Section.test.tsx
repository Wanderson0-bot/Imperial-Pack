import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { Section } from './Section';

describe('Section', () => {
  it('uses a level-two heading beneath the page heading', () => {
    const markup = renderToStaticMarkup(<Section title="Resumo">Conteúdo</Section>);
    expect(markup).toContain('<h2>Resumo</h2>');
    expect(markup).not.toContain('<h3>Resumo</h3>');
  });
});
