import { describe, expect, it } from 'vitest';
import { calculatePurchaseSummary } from './purchaseCalculations';

describe('purchase calculations', () => {
  it('calculates discounted line subtotals and purchase total in cents', () => {
    const summary = calculatePurchaseSummary([
      { productId: 'rice', quantity: 20, unitCost: 22, discount: 10 },
    ], 100);

    expect(summary.lines[0]).toEqual({ grossCents: 44000, discountCents: 1000, subtotalCents: 43000 });
    expect(summary.productsSubtotalCents).toBe(44000);
    expect(summary.discountsCents).toBe(1000);
    expect(summary.freightCents).toBe(10000);
    expect(summary.totalCents).toBe(53000);
  });

  it('allocates displayed line values without floating-point currency drift', () => {
    const summary = calculatePurchaseSummary([
      { productId: 'first', quantity: 3, unitCost: 0.1, discount: 0 },
      { productId: 'second', quantity: 7, unitCost: 0.1, discount: 0 },
    ], 0.2);

    expect(summary.productsSubtotalCents).toBe(100);
    expect(summary.totalCents).toBe(120);
  });
});