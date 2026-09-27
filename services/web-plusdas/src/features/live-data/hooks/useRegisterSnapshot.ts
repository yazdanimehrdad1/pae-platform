import { useQuery } from "@tanstack/react-query";
import { modbusStreamApi } from "@/api";

// The last polls backend-ot keeps for a session. Fetched once when the session tab opens, then
// only when the user takes a new snapshot (`refetch`): never on a timer or on window focus.
export function useRegisterSnapshot(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: ["modbus-snapshot", sessionId],
    queryFn: () => modbusStreamApi.getSnapshot(sessionId),
    enabled,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    retry: false,
  });
}
