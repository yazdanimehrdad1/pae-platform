import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";

import { fetchHealth } from "@/api/backendOt";
import { queryKeys } from "@/api/queryKeys";
import { DETECTED_SERVER_URL, serverUrl, serverUrlSchema } from "@/shared/config/serverUrl";
import { Button, Card } from "@/shared/components/ui";
import { FONT, RADIUS, SPACE, usePalette } from "@/shared/theme/tokens";

/** The backend-ot address, whether it answers, and (in development) the one detected from the PC. */
export function ServerUrlSection() {
  const palette = usePalette();
  const queryClient = useQueryClient();
  const current = serverUrl.use();
  const [draft, setDraft] = useState(current);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);
  const health = useQuery({
    queryKey: queryKeys.health(current),
    queryFn: fetchHealth,
    retry: false,
    refetchInterval: 15_000,
  });

  const apply = async (url: string) => {
    await serverUrl.set(url);
    setDraft(url);
    // Everything cached came from the old server.
    queryClient.clear();
  };

  const save = async () => {
    const parsed = serverUrlSchema.safeParse(draft);
    if (!parsed.success) {
      setMessage({ text: parsed.error.issues[0]?.message ?? "Invalid URL", isError: true });
      return;
    }
    await apply(parsed.data);
    setMessage({ text: "Saved", isError: false });
  };

  const detected = DETECTED_SERVER_URL;
  const usingDetected = detected !== null && current === detected;

  return (
    <Card style={styles.card}>
      <Text style={[styles.label, { color: palette.text }]}>Server</Text>
      <Text style={[styles.help, { color: palette.textMuted }]}>
        {usingDetected
          ? "Detected from the dev server this app was opened from."
          : "backend-ot address, without /api, e.g. http://192.168.1.10:8000."}
      </Text>
      <TextInput
        accessibilityLabel="Server URL"
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        value={draft}
        onChangeText={(text) => {
          setDraft(text);
          setMessage(null);
        }}
        onSubmitEditing={save}
        placeholder="http://192.168.1.10:8000"
        placeholderTextColor={palette.textMuted}
        style={[
          styles.input,
          { borderColor: palette.border, color: palette.text, backgroundColor: palette.background },
        ]}
      />
      <Text
        accessibilityLiveRegion="polite"
        style={[styles.status, { color: health.isError ? palette.fault : palette.textMuted }]}
      >
        {health.isPending ? "Checking connection…" : health.isError ? health.error.message : `Connected to ${current}`}
      </Text>
      {message ? (
        <Text style={[styles.status, { color: message.isError ? palette.fault : palette.textMuted }]}>
          {message.text}
        </Text>
      ) : null}
      <View style={styles.actions}>
        {detected && !usingDetected ? (
          <Button
            variant="secondary"
            label="Use detected"
            onPress={() => {
              setMessage(null);
              void apply(detected);
            }}
          />
        ) : null}
        <Button variant="secondary" label="Test" onPress={() => void health.refetch()} />
        <Button label="Save" onPress={save} disabled={draft.trim() === current} />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: SPACE.sm },
  label: { fontSize: FONT.title, fontWeight: "600" },
  help: { fontSize: FONT.caption, lineHeight: 17 },
  input: { borderRadius: RADIUS.md, borderWidth: 1, fontSize: FONT.body, minHeight: 44, paddingHorizontal: SPACE.md },
  status: { fontSize: FONT.caption },
  actions: { flexDirection: "row", flexWrap: "wrap", gap: SPACE.sm, justifyContent: "flex-end" },
});
