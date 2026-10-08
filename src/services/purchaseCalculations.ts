import type { PurchaseDraftItem } from '../types';

export type PurchaseLineAmount = {
  grossCents: number;
  discountCents: number;
  subtotalCents: number;
};

export type PurchaseSummary = {
  lines: PurchaseLineAmount[];
  productsSubtotalCents: number;
  discountsCents: number;
  freightCents: number;
  totalCents: number;
};

export const toCents = (value: number): number => Math.round((value + Number.EPSILON) * 100);

export function calculatePurchaseSummary(items: PurchaseDraftItem[], freight: number): PurchaseSummary {
  const lines = items.map((item) => {
    const quantityMilli = Math.round(item.quantity * 1000);
    const grossCents = Math.round(quantityMilli * toCents(item.unitCost) / 1000);
    const discountCents = toCents(item.discount);
    return { grossCents, discountCents, subtotalCents: grossCents - discountCents };
  });
  const productsSubtotalCents = lines.reduce((total, line) => total + line.grossCents, 0);
  const discountsCents = lines.reduce((total, line) => total + line.discountCents, 0);
  const freightCents = toCents(freight);
  return { lines, productsSubtotalCents, discountsCents, freightCents, totalCents: productsSubtotalCents - discountsCents + freightCents };
}