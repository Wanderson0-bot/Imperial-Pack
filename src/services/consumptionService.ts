import type { PartnerPurchaseRecord } from '../types';
import { partnerService } from './partnerService';

export type ProductConsumption = {
  productId: string;
  purchases: PartnerPurchaseRecord[];
  lastQuantity: number;
  lastPurchase: string;
  averageIntervalDays?: number;
  averageQuantityPerPurchase: number;
  estimatedDailyConsumption?: number;
  trend: 'increasing' | 'stable' | 'decreasing' | 'unknown';
};

const dayDifference = (from: string, to: string) => Math.max(0, (Date.parse(`${to}T12:00:00`) - Date.parse(`${from}T12:00:00`)) / 86_400_000);

export const consumptionService = {
  getForPartner: async (customerId: string): Promise<ProductConsumption[]> => {
    const records = (await partnerService.getPurchaseHistory(customerId)).sort((a, b) => a.purchasedAt.localeCompare(b.purchasedAt));
    const productIds = [...new Set(records.map((record) => record.productId))];
    return productIds.map((productId) => {
      const purchases = records.filter((record) => record.productId === productId);
      const intervals = purchases.slice(1).map((record, index) => dayDifference(purchases[index].purchasedAt, record.purchasedAt));
      const averageIntervalDays = intervals.length ? intervals.reduce((sum, value) => sum + value, 0) / intervals.length : undefined;
      const averageQuantityPerPurchase = purchases.reduce((sum, record) => sum + record.quantity, 0) / purchases.length;
      const elapsedDays = purchases.length > 1 ? dayDifference(purchases[0].purchasedAt, purchases[purchases.length - 1].purchasedAt) : 0;
      let trend: ProductConsumption['trend'] = 'unknown';
      if (purchases.length >= 4) {
        const middle = Math.floor(purchases.length / 2);
        const mean = (items: PartnerPurchaseRecord[]) => items.reduce((sum, item) => sum + item.quantity, 0) / items.length;
        const earlier = mean(purchases.slice(0, middle));
        const later = mean(purchases.slice(middle));
        const change = earlier > 0 ? (later - earlier) / earlier : 0;
        trend = change > 0.1 ? 'increasing' : change < -0.1 ? 'decreasing' : 'stable';
      }
      return {
        productId,
        purchases,
        lastQuantity: purchases[purchases.length - 1].quantity,
        lastPurchase: purchases[purchases.length - 1].purchasedAt,
        averageIntervalDays,
        averageQuantityPerPurchase,
        estimatedDailyConsumption: elapsedDays > 0 ? purchases.reduce((sum, record) => sum + record.quantity, 0) / elapsedDays : undefined,
        trend,
      };
    });
  },
};
