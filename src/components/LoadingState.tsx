type LoadingStateProps = { message?: string };
export function LoadingState({ message = 'Carregando...' }: LoadingStateProps) { return <div className="loading-state" role="status" aria-live="polite">{message}</div>; }
