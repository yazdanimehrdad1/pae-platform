import { FileText } from "lucide-react-native";

import { Notice } from "@/shared/components/ui";

// Planned: a site report readable on the phone, once backend-ot serves reports.
export default function ReportsScreen() {
  return <Notice Icon={FileText} title="Reports are coming" body="Daily site reports will be readable here." />;
}
