import { Sparkles } from "lucide-react-native";

import { Notice } from "@/shared/components/ui";

// Planned: ask the AI agent questions about a site.
export default function AssistantScreen() {
  return (
    <Notice Icon={Sparkles} title="Assistant is coming" body="You'll be able to ask questions about your sites here." />
  );
}
