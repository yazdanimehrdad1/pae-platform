export interface Site {
  id: string;
  name: string;
  location: string;
  type: 'substation' | 'plant' | 'microgrid' | 'solar' | 'wind' | 'facility';
  status: 'online' | 'warning' | 'offline';
  deviceCount: number;
  lastUpdate: string;
  capacity: string;
  operator: string;
  description: string;
}

export interface SiteLocation {
  street: string;
  city: string;
  state: string;
  zip_code: number;
}

export interface SiteCoordinates {
  lat: number;
  lng: number;
}

export interface SiteRecord {
  site_id: number;
  client_id: string;
  name: string;
  location: SiteLocation;
  operator: string;
  capacity: string;
  device_count: number;
  description: string;
  coordinates: SiteCoordinates;
  created_at: string;
  updated_at: string;
  last_update: string;
  deleted_at: string | null;
}

export interface SiteCreateRequest {
  client_id: string;
  name: string;
  location: SiteLocation;
  operator: string;
  capacity: string;
  description: string;
  coordinates: SiteCoordinates;
}

export type SiteUpdateRequest = Partial<SiteCreateRequest>;

export interface SiteDeleteResponse {
  site_id: number;
  mode: 'soft' | 'hard';
}
