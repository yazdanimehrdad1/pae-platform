import AsyncStorage from "@react-native-async-storage/async-storage";
import { useSyncExternalStore } from "react";

/** A string setting kept on the device and readable synchronously after `load()`.
 *  Storage failures fall back to the in-memory value: the app keeps working, it just forgets. */
export type PersistedValue<T extends string | null> = {
  get: () => T;
  load: () => Promise<T>;
  set: (value: T) => Promise<void>;
  use: () => T;
};

export function persistedValue<T extends string | null>(storageKey: string, initial: T): PersistedValue<T> {
  let current = initial;
  const listeners = new Set<() => void>();
  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };
  const get = () => current;
  const update = (value: T) => {
    current = value;
    listeners.forEach((listener) => listener());
  };

  return {
    get,
    async load() {
      try {
        const stored = await AsyncStorage.getItem(storageKey);
        if (stored !== null) update(stored as T);
      } catch {
        // Keep the initial value.
      }
      return current;
    },
    async set(value) {
      update(value);
      try {
        if (value === null) await AsyncStorage.removeItem(storageKey);
        else await AsyncStorage.setItem(storageKey, value);
      } catch {
        // Kept in memory for this session.
      }
    },
    use: () => useSyncExternalStore(subscribe, get),
  };
}
