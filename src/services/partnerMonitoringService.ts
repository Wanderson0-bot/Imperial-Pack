import type { Customer, PartnerProfile, Product, ReplenishmentPrediction } from '../types';
import { consumptionService, type ProductConsumption } from './consumptionService';
import { partnerPredictionService } from './partnerPredictionService';
import { partnerService } from './partnerService';
import { productService } from './productService';

export type TrackedPartnerProduct = {
  product?: Product;
  consumption: ProductConsumption;
  prediction?: ReplenishmentPrediction;
  status: string;
  alert?: string;
};
export type PartnerMonitoring = {
  customer?: Customer;
  profile: PartnerProfile;
  products: TrackedPartnerProduct[];
  alerts: string[];
  opportunities: Product[];
  predictionStatus: 'insufficient-data' | 'model-unavailable' | 'ready';
};
export type PartnerMonitoringOverview = {
  partners: PartnerMonitoring[];
  activePartners: number;
  monitoredProducts: number;
  upcomingReplenishments: number;
  alertCount: number;
};

export const partnerMonitoringService = {
  getOverview: async (): Promise<PartnerMonitoringOverview> => {
    const [customers, profiles, catalog] = await Promise.all([
      partnerService.getCandidates(), partnerService.getProfiles(), productService.getAll(),
    ]);
    const activeProfiles = profiles.filter((profile) => profile.status === 'active');
    const partners = await Promise.all(activeProfiles.map(async (profile): Promise<PartnerMonitoring> => {
      const [consumption, predictionResult] = await Promise.all([
        consumptionService.getForPartner(profile.customerId),
        partnerPredictionService.getForPartner(profile.customerId),
      ]);
      const predictionByProduct = new Map(predictionResult.predictions.map((prediction) => [prediction.productId, prediction]));
      const trackedProducts = consumption.map((item): TrackedPartnerProduct => {
        const prediction = predictionByProduct.get(item.productId);
        const hasReplenishment = prediction?.confidence !== 'insufficient-data' && Boolean(prediction?.replenishmentWindow);
        const possibleRisk = prediction?.confidence !== 'insufficient-data' && Boolean(prediction?.depletionWindow);
        const cycleDays = profile.cycle === 'weekly' ? 7 : profile.cycle === 'fortnightly' ? 14 : profile.cycle === 'monthly' ? 30 : profile.cycle === 'bimonthly' ? 60 : profile.cycle === 'custom' ? profile.customCycleDays : undefined;
        const plannedNextCycle = cycleDays ? Date.parse(`${item.lastPurchase}T12:00:00`) + cycleDays * 86_400_000 : undefined;
        const depletionBeforeCycle = Boolean(prediction?.depletionWindow && plannedNextCycle && Date.parse(`${prediction.depletionWindow.start}T12:00:00`) < plannedNextCycle);
        return {
          product: catalog.find((product) => product.id === item.productId),
          consumption: item,
          prediction,
          status: depletionBeforeCycle ? 'Risco antes do ciclo planejado' : hasReplenishment ? 'Reposição prevista' : possibleRisk ? 'Possível risco' : 'Acompanhamento ativo',
          alert: hasReplenishment
            ? 'Reposição recomendada. Confirme a necessidade com o parceiro antes de registrar pedido.'
            : possibleRisk ? depletionBeforeCycle ? 'Esgotamento previsto antes do próximo ciclo. Recomenda-se confirmar o consumo com o parceiro.' : 'Possível risco de ruptura; confirmar consumo com o parceiro.' : undefined,
        };
      });
      const alerts = trackedProducts.flatMap((item) => item.alert ? [item.alert] : []);
      if (predictionResult.status === 'insufficient-data') alerts.push('Dados insuficientes para previsão confiável');
      if (predictionResult.status === 'model-unavailable') alerts.push('Histórico disponível; previsões dependem da conexão do modelo ML');
      const purchasedIds = new Set(consumption.map((item) => item.productId));
      const opportunities = consumption.length ? catalog.filter((product) => !purchasedIds.has(product.id)) : [];
      return {
        customer: customers.find((customer) => customer.id === profile.customerId),
        profile,
        products: trackedProducts,
        alerts,
        opportunities,
        predictionStatus: predictionResult.status,
      };
    }));
    const upcomingReplenishments = partners.reduce((total, partner) => total + partner.products.filter((item) => {
      const start = item.prediction?.replenishmentWindow?.start;
      const daysUntil = start ? (Date.parse(`${start}T12:00:00`) - Date.now()) / 86_400_000 : Infinity;
      return daysUntil >= 0 && daysUntil <= 7;
    }).length, 0);
    return {
      partners,
      activePartners: activeProfiles.length,
      monitoredProducts: partners.reduce((total, partner) => total + partner.products.length, 0),
      upcomingReplenishments,
      alertCount: partners.reduce((total, partner) => total + partner.alerts.length, 0),
    };
  },
};
