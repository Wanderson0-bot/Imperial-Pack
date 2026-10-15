/** Short, human-readable reference for showing purchases in the UI. */
export function formatPurchaseReference(id: string): string {
  return `C-${id.slice(0, 8).toLocaleUpperCase()}`;
}
