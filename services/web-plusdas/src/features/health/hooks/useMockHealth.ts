import { useState, useEffect } from 'react';

export interface HealthState {
  timestamp: number;
  deviceId: string;
  state: 0 | 1 | 2;
  message?: string;
}

export const useMockHealth = (deviceIds: string[]) => {
  const [data, setData] = useState<HealthState[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const generateHealth = () => {
      const now = Date.now();
      const states: HealthState[] = [];

      deviceIds.forEach(deviceId => {
        for (let i = 48; i >= 0; i--) {
          const timestamp = now - (i * 3600000);
          let state: 0 | 1 | 2 = 2;

          if (Math.random() < 0.05) state = 0;
          else if (Math.random() < 0.15) state = 1;

          states.push({
            timestamp,
            deviceId,
            state,
            message: state === 0 ? 'Communication Lost' :
              state === 1 ? 'High Temperature' : 'Normal'
          });
        }
      });

      setData(states);
      setIsLoading(false);
    };

    generateHealth();
  }, [deviceIds]);

  return { data, isLoading };
};
