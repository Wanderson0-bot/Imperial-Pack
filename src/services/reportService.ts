import { customerService } from './customerService';
import { orderService } from './orderService';

export const reportService = {
  getOverview: async () => {
    const [customers, orders] = await Promise.all([customerService.getAll(), orderService.getAll()]);
    return {
      customers,
      orders: orders.filter((order) =>
        ['Confirmado', 'Em separação', 'Pronto', 'Entregue'].includes(order.status),
      ),
    };
  },
};
