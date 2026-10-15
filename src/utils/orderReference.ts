/** Short, human-readable reference for showing orders in the UI. */
export function formatOrderReference(id: string): string {
  return `#${id.slice(0, 8).toLocaleUpperCase()}`;
}
