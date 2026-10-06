import { focusManager, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";
import { AppState } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { serverUrl } from "@/shared/config/serverUrl";
import { usePalette } from "@/shared/theme/tokens";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnReconnect: true } },
});

// React Native has no window focus: treat "app in the foreground" as focus, so polling stops in
// the background and everything refreshes when the operator comes back.
focusManager.setEventListener((setFocused) => {
  const subscription = AppState.addEventListener("change", (state) => setFocused(state === "active"));
  return () => subscription.remove();
});

export default function RootLayout() {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    serverUrl.load().finally(() => setReady(true));
  }, []);
  if (!ready) return null;

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <AppStack />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}

function AppStack() {
  const palette = usePalette();
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: palette.surface },
          headerTintColor: palette.text,
          contentStyle: { backgroundColor: palette.background },
          headerBackButtonDisplayMode: "minimal",
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      </Stack>
    </>
  );
}
