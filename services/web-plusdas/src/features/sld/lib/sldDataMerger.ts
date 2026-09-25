import type { SLDLayout, SLDDataInfo, SLDData, SLDDevice, SLDDeviceLayout, SLDDeviceData } from "../types";

export function mergeSLDData(layout: SLDLayout, data: SLDDataInfo): SLDData {
  const deviceDataMap = new Map<string, SLDDeviceData>();
  data.devices.forEach(deviceData => {
    deviceDataMap.set(deviceData.id, deviceData);
  });

  const mergedDevices: SLDDevice[] = layout.devices.map(deviceLayout => {
    const deviceData = deviceDataMap.get(deviceLayout.id);
    const mergedProperties = { ...deviceLayout.properties, ...deviceData?.properties };

    const mergedDevice: SLDDevice = {
      ...deviceLayout,
      status: deviceData?.status ?? "online",
      power: deviceData?.power,
      powerFlow: deviceData?.powerFlow,
      properties: Object.keys(mergedProperties).length > 0 ? mergedProperties : undefined,
    };

    return mergedDevice;
  });

  return {
    siteId: layout.siteId || data.siteId,
    siteName: layout.siteName,
    devices: mergedDevices,
    connections: layout.connections,
    buses: layout.buses,
    summary: data.summary,
  };
}

export async function fetchSLDLayout(siteId: string): Promise<SLDLayout> {
  // TODO: replace with real API call: GET /api/sites/${siteId}/sld/layout
  const layoutModule = await import("../test/sld-layout.json");
  return layoutModule.default as SLDLayout;
}

export async function fetchSLDData(siteId: string): Promise<SLDDataInfo> {
  // TODO: replace with real API call: GET /api/sites/${siteId}/sld/data
  const dataModule = await import("../test/sld-data.json");
  return dataModule.default as SLDDataInfo;
}

export async function fetchCompleteSLDData(siteId: string): Promise<SLDData> {
  const [layout, data] = await Promise.all([fetchSLDLayout(siteId), fetchSLDData(siteId)]);
  return mergeSLDData(layout, data);
}
