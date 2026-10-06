import { useCallback, useState } from "react";

/**
 * Spinner state for a RefreshControl that reflects only the user's pull, not the background
 * polling (which would flash the spinner every poll and look like the screen reloading).
 */
export function usePullToRefresh(refresh: () => Promise<unknown>) {
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await refresh();
    } finally {
      setRefreshing(false);
    }
  }, [refresh]);
  return { refreshing, onRefresh };
}
