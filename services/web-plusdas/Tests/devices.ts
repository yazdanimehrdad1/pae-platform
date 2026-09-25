import type { Device } from "@/shared/types/device";

export const mockDevices: Record<string, Device[]> = {
  'site-alpha': [
    {
      id: 'txf-001',
      name: 'Transformer T1',
      type: 'transformer',
      status: 'online',
      location: 'Bay 1',
      lastUpdate: '1 minute ago',
      points: ['Voltage L1', 'Voltage L2', 'Voltage L3', 'Current L1', 'Current L2', 'Current L3', 'Power', 'Temperature'],
      make: 'ABB',
      model: 'TXF-150MVA',
      serialNumber: 'TX150-2023-001',
      commStatus: 'connected',
      firmware: 'v2.1.4'
    },
    {
      id: 'gen-001',
      name: 'Generator G1',
      type: 'generator',
      status: 'online',
      location: 'Gen Hall',
      lastUpdate: '30 seconds ago',
      points: ['Power Output', 'RPM', 'Temperature', 'Fuel Level', 'Voltage', 'Current'],
      make: 'Siemens',
      model: 'SGT-A65',
      serialNumber: 'GEN-2023-001',
      commStatus: 'connected',
      firmware: 'v3.2.1'
    },
    {
      id: 'prot-001',
      name: 'Protection P1',
      type: 'protection',
      status: 'warning',
      location: 'Control Room',
      lastUpdate: '5 minutes ago',
      points: ['Status', 'Fault Current', 'Trip Count', 'Pickup Current'],
      make: 'Schneider',
      model: 'Micom P633',
      serialNumber: 'PROT-2023-001',
      commStatus: 'timeout',
      firmware: 'v1.8.3'
    },
    {
      id: 'feed-001',
      name: 'Feeder F1',
      type: 'feeder',
      status: 'online',
      location: 'Bay 3',
      lastUpdate: '2 minutes ago',
      points: ['Voltage', 'Current', 'Power Factor', 'Energy'],
      make: 'GE',
      model: 'F650',
      serialNumber: 'FEED-2023-001',
      commStatus: 'connected',
      firmware: 'v2.0.1'
    }
  ],
  'site-beta': [
    {
      id: 'txf-002',
      name: 'Transformer T2',
      type: 'transformer',
      status: 'online',
      location: 'Bay 1',
      lastUpdate: '3 minutes ago',
      points: ['Voltage L1', 'Voltage L2', 'Voltage L3', 'Current L1', 'Current L2', 'Current L3', 'Power', 'Temperature'],
      make: 'Siemens',
      model: 'TXF-100MVA',
      serialNumber: 'TX100-2023-002',
      commStatus: 'connected',
      firmware: 'v2.0.8'
    },
    {
      id: 'meter-001',
      name: 'Energy Meter M1',
      type: 'meter',
      status: 'online',
      location: 'Main Panel',
      lastUpdate: '1 minute ago',
      points: ['Active Power', 'Reactive Power', 'Energy Import', 'Energy Export', 'THD Voltage', 'THD Current'],
      make: 'Landis+Gyr',
      model: 'E850',
      serialNumber: 'MTR-2023-001',
      commStatus: 'connected',
      firmware: 'v4.1.2'
    }
  ]
};
