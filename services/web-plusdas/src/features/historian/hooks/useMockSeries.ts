import { useState, useEffect } from 'react';

export interface TimeSeriesPoint {
  timestamp: number;
  value: number;
}

const getMockValue = (pointName: string, i: number, timeSeed: number) => {
  let base = 50;
  let noise = Math.random() * 5;

  if (pointName.toLowerCase().includes('voltage')) {
    base = 115 + Math.sin(timeSeed * 0.05) * 5;
  } else if (pointName.toLowerCase().includes('current')) {
    base = 30 + Math.cos(timeSeed * 0.1) * 15;
  } else if (pointName.toLowerCase().includes('power')) {
    base = 45 + Math.sin(timeSeed * 0.1) * 10;
    noise = Math.random() * 8;
  } else if (pointName.toLowerCase().includes('temp')) {
    base = 65 + Math.sin(timeSeed * 0.01) * 20;
  }

  const pointHash = pointName.split('').reduce((a, b) => a + b.charCodeAt(0), 0);
  const offset = (pointHash % 20) - 10;
  return base + offset + noise;
};

// One row per timestamp, with one numeric column per point name.
type SeriesRow = { timestamp: number } & Record<string, number>;

export const useMockSeries = (points: string[], timeRangeHours: number = 1) => {
  const [data, setData] = useState<SeriesRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const pointsKey = points.join(',');

  useEffect(() => {
    const generateSeries = () => {
      const now = Date.now();
      const seriesData: SeriesRow[] = [];
      const totalMinutes = timeRangeHours * 60;
      const numberOfPoints = Math.floor(totalMinutes / 1);

      for (let i = numberOfPoints; i >= 0; i--) {
        const timestamp = now - (i * 60000);
        const pointData: SeriesRow = { timestamp };
        points.forEach(point => {
          pointData[point] = getMockValue(point, i, i);
        });
        seriesData.push(pointData);
      }

      setData(seriesData);
      setIsLoading(false);
    };

    if (points.length > 0) {
      setIsLoading(true);
      const timer = setTimeout(generateSeries, 300);
      return () => clearTimeout(timer);
    } else {
      setData([]);
      setIsLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pointsKey, timeRangeHours]);

  return { data, isLoading };
};
