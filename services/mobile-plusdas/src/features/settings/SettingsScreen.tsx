import Constants from "expo-constants";
import { ScrollView, StyleSheet, Text } from "react-native";

import { FONT, SPACE, usePalette } from "@/shared/theme/tokens";

import { ServerUrlSection } from "./ServerUrlSection";

export function SettingsScreen() {
  const palette = usePalette();
  return (
    <ScrollView
      style={{ backgroundColor: palette.background }}
      contentContainerStyle={styles.content}
      keyboardShouldPersistTaps="handled"
    >
      <ServerUrlSection />
      <Text style={[styles.version, { color: palette.textMuted }]}>
        PAE PlusDAS mobile {Constants.expoConfig?.version ?? ""}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { gap: SPACE.lg, padding: SPACE.lg },
  version: { fontSize: FONT.caption, textAlign: "center" },
});
