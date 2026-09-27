import { mockAlarmSource } from "@/mocks/alarms/mockAlarmSource";
import type { AlarmDataSource } from "./AlarmDataSource";

// The one place that picks where alarm data comes from. Mocked until backend-ot has an alarms
// API (docs/backend-gaps.md); a live implementation of AlarmDataSource replaces this line.
export const alarmSource: AlarmDataSource = mockAlarmSource;
