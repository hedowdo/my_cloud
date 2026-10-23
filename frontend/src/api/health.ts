export type ServiceState = 'ready' | 'unavailable';

export async function fetchHealth(signal: AbortSignal): Promise<ServiceState> {
  const response = await fetch('/api/health/ready', {
    signal,
    cache: 'no-store',
    credentials: 'same-origin',
  });
  if (!response.ok) return 'unavailable';
  const data: unknown = await response.json();
  return typeof data === 'object' &&
    data !== null &&
    'status' in data &&
    data.status === 'ready'
    ? 'ready'
    : 'unavailable';
}
