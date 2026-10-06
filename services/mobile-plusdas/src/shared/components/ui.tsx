import type { LucideIcon } from "lucide-react-native";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { FONT, RADIUS, SPACE, usePalette } from "@/shared/theme/tokens";

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const palette = usePalette();
  return (
    <View style={[styles.card, { backgroundColor: palette.surface, borderColor: palette.border }, style]}>
      {children}
    </View>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  const palette = usePalette();
  return <Text style={[styles.sectionTitle, { color: palette.textMuted }]}>{children}</Text>;
}

/** Centered icon + title + body; for empty lists, errors and placeholder tabs. */
export function Notice({
  Icon,
  title,
  body,
  actionLabel,
  onAction,
}: {
  Icon: LucideIcon;
  title: string;
  body?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  const palette = usePalette();
  return (
    <View style={[styles.notice, { backgroundColor: palette.background }]}>
      <Icon color={palette.textMuted} size={36} strokeWidth={1.5} />
      <Text style={[styles.noticeTitle, { color: palette.text }]}>{title}</Text>
      {body ? <Text style={[styles.noticeBody, { color: palette.textMuted }]}>{body}</Text> : null}
      {actionLabel && onAction ? <Button label={actionLabel} onPress={onAction} /> : null}
    </View>
  );
}

export function Loading() {
  const palette = usePalette();
  return (
    <View style={[styles.notice, { backgroundColor: palette.background }]}>
      <ActivityIndicator color={palette.textMuted} />
    </View>
  );
}

export function Button({
  label,
  onPress,
  disabled,
  variant = "primary",
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  variant?: "primary" | "secondary";
}) {
  const palette = usePalette();
  const primary = variant === "primary";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled: Boolean(disabled) }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        {
          backgroundColor: primary ? palette.accent : palette.surface,
          borderColor: primary ? palette.accent : palette.border,
          opacity: disabled ? 0.5 : pressed ? 0.8 : 1,
        },
      ]}
    >
      <Text style={[styles.buttonLabel, { color: primary ? palette.onAccent : palette.text }]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth, padding: SPACE.lg },
  sectionTitle: {
    fontSize: FONT.caption,
    fontWeight: "600",
    letterSpacing: 0.6,
    textTransform: "uppercase",
    marginTop: SPACE.xl,
    marginBottom: SPACE.sm,
    marginHorizontal: SPACE.lg,
  },
  notice: { alignItems: "center", flex: 1, gap: SPACE.sm, padding: SPACE.xl, paddingTop: 64 },
  noticeTitle: { fontSize: FONT.title, fontWeight: "600", textAlign: "center" },
  noticeBody: { fontSize: FONT.body, textAlign: "center", lineHeight: 21, marginBottom: SPACE.sm },
  button: {
    alignItems: "center",
    borderRadius: RADIUS.md,
    borderWidth: 1,
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: SPACE.lg,
  },
  buttonLabel: { fontSize: FONT.body, fontWeight: "600" },
});
