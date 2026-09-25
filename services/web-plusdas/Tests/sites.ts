import type { Site } from "@/shared/types/site";

export const mockSites: Site[] = [
  {
    id: 'site-alpha',
    name: 'Site Alpha',
    location: 'Industrial District, North',
    type: 'substation',
    status: 'online',
    deviceCount: 24,
    lastUpdate: '2 minutes ago',
    capacity: '150 MVA',
    operator: 'John Smith',
    description: 'Primary 132kV substation serving industrial zone'
  },
  {
    id: 'site-beta',
    name: 'Site Beta',
    location: 'Downtown Core',
    type: 'plant',
    status: 'warning',
    deviceCount: 18,
    lastUpdate: '5 minutes ago',
    capacity: '75 MW',
    operator: 'Sarah Johnson',
    description: 'Combined cycle power generation facility'
  },
  {
    id: 'site-gamma',
    name: 'Site Gamma',
    location: 'Coastal Industrial Park',
    type: 'facility',
    status: 'online',
    deviceCount: 32,
    lastUpdate: '1 minute ago',
    capacity: '200 MVA',
    operator: 'Mike Chen',
    description: 'Distribution facility with renewable integration'
  },
  {
    id: 'site-delta',
    name: 'Site Delta',
    location: 'Mountain View Complex',
    type: 'substation',
    status: 'offline',
    deviceCount: 12,
    lastUpdate: '15 minutes ago',
    capacity: '50 MVA',
    operator: 'Lisa Rodriguez',
    description: 'Remote substation - scheduled maintenance'
  },
  {
    id: 'site-epsilon',
    name: 'Site Epsilon',
    location: 'Harbor District',
    type: 'plant',
    status: 'online',
    deviceCount: 28,
    lastUpdate: '3 minutes ago',
    capacity: '100 MW',
    operator: 'David Kim',
    description: 'Natural gas peaking plant with energy storage'
  },
  {
    id: 'site-zeta',
    name: 'Site Zeta',
    location: 'Technology Park',
    type: 'facility',
    status: 'warning',
    deviceCount: 16,
    lastUpdate: '8 minutes ago',
    capacity: '80 MVA',
    operator: 'Emma Wilson',
    description: 'Smart grid demonstration facility'
  }
];
