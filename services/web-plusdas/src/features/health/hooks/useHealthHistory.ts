import { useState, useEffect } from 'react';
import { generateMockHealthHistory } from '@/mocks/health';
import type { HealthState } from '../types';

// Health history per device. Mocked until backend-ot stores health over time; this hook is the
// one place to switch to the real API.
export const useHealthHistory = (deviceIds: string[]) => {
  const [data, setData] = useState<HealthState[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    setData(generateMockHealthHistory(deviceIds));
    setIsLoading(false);
  }, [deviceIds]);

  return { data, isLoading };
};
