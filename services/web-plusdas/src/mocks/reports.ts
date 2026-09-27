// Reports mocks: report catalogue and generated files. There is no reports API yet
// (docs/backend-gaps.md).
import { BarChart3, Clock, PieChart, TrendingUp } from "lucide-react";

export const MOCK_REPORT_TYPES = [
  { id: 'energy-consumption', title: 'Energy Consumption Report', description: 'Daily, weekly, and monthly energy usage analysis', icon: BarChart3, lastGenerated: '2 hours ago', frequency: 'Daily' },
  { id: 'power-quality', title: 'Power Quality Report', description: 'Voltage, frequency, and harmonic distortion analysis', icon: TrendingUp, lastGenerated: '1 day ago', frequency: 'Weekly' },
  { id: 'demand-analysis', title: 'Demand Analysis Report', description: 'Peak demand patterns and load factor calculations', icon: PieChart, lastGenerated: '3 hours ago', frequency: 'Daily' },
  { id: 'alarm-summary', title: 'Alarm Summary Report', description: 'Consolidated alarm and event history', icon: Clock, lastGenerated: '30 minutes ago', frequency: 'Real-time' },
];

export const MOCK_RECENT_REPORTS = [
  { name: 'Energy_Report_Dec_2024.pdf', date: 'Dec 12, 2024', size: '2.4 MB', status: 'ready' },
  { name: 'Power_Quality_Week49.pdf', date: 'Dec 10, 2024', size: '1.8 MB', status: 'ready' },
  { name: 'Demand_Analysis_Q4.pdf', date: 'Dec 8, 2024', size: '3.1 MB', status: 'ready' },
  { name: 'Monthly_Summary_Nov.pdf', date: 'Nov 30, 2024', size: '4.2 MB', status: 'ready' },
];
