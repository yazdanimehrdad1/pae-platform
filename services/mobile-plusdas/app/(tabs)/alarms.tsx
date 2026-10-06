import { Bell } from "lucide-react-native";

import { Notice } from "@/shared/components/ui";

// Planned: every site's alarms in one list. Site alarms are on each site's screen meanwhile.
export default function AlarmsScreen() {
  return <Notice Icon={Bell} title="Alarms are coming" body="Open a site from the Sites tab to see its alarms." />;
}
