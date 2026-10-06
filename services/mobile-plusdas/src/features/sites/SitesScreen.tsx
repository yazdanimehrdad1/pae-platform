import { useRouter } from "expo-router";
import { Building2, WifiOff } from "lucide-react-native";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";

import type { Site } from "@/api/types";
import { Loading, Notice } from "@/shared/components/ui";
import { usePullToRefresh } from "@/shared/lib/usePullToRefresh";
import { FONT, RADIUS, SPACE, usePalette } from "@/shared/theme/tokens";

import { useSites } from "./useSites";

/** A plain, read-only list of the sites. No alarm state is shown here. */
export function SitesScreen() {
  const palette = usePalette();
  const router = useRouter();
  const sites = useSites();
  const pull = usePullToRefresh(sites.refetch);

  if (sites.isLoading) return <Loading />;
  if (sites.error) {
    return (
      <Notice
        Icon={WifiOff}
        title="Can't load sites"
        body={sites.error.message}
        actionLabel="Check server in Settings"
        onAction={() => router.push("/settings")}
      />
    );
  }

  return (
    <FlatList
      style={{ backgroundColor: palette.background }}
      contentContainerStyle={styles.list}
      data={sites.data ?? []}
      keyExtractor={(site) => String(site.site_id)}
      refreshControl={<RefreshControl refreshing={pull.refreshing} onRefresh={pull.onRefresh} />}
      ListEmptyComponent={
        <Notice Icon={Building2} title="No sites yet" body="Sites created in PlusDAS show up here." />
      }
      renderItem={({ item }) => <SiteRow site={item} />}
    />
  );
}

/** "Austin, TX · 5 MW · 9 devices" (parts that are missing are left out). */
export function siteDetails(site: Site): string {
  const place = [site.location?.city, site.location?.state].filter(Boolean).join(", ");
  const devices = `${site.device_count} device${site.device_count === 1 ? "" : "s"}`;
  return [place, site.capacity, devices].filter(Boolean).join(" · ");
}

function SiteRow({ site }: { site: Site }) {
  const palette = usePalette();
  const details = siteDetails(site);
  return (
    <View
      accessible
      accessibilityLabel={`${site.name}, ${details}`}
      style={[styles.row, { backgroundColor: palette.surface, borderColor: palette.border }]}
    >
      <Text style={[styles.name, { color: palette.text }]} numberOfLines={1}>
        {site.name}
      </Text>
      <Text style={[styles.details, { color: palette.textMuted }]} numberOfLines={1}>
        {details}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: SPACE.md, padding: SPACE.lg },
  row: { borderRadius: RADIUS.lg, borderWidth: StyleSheet.hairlineWidth, gap: SPACE.xs, padding: SPACE.lg },
  name: { fontSize: FONT.title, fontWeight: "600" },
  details: { fontSize: FONT.caption },
});
