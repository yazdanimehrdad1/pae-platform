import { useState, useEffect } from "react";
import { useBreakpoint } from "@/shared/hooks/use-mobile";
import { useLocation, useNavigate, useSearchParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import type { Device } from "@/api/types/devices";
import { devicesApi, sitesApi } from "@/api";
import type { Site } from "@/api/types/sites";
import { deviceTypeConfig } from "@/shared/config/device-types";
import {
  Search, Activity, Filter, ArrowLeft, BarChart3,
  AlertTriangle, CheckCircle, Clock, Settings, XCircle, Info, ChevronDown
} from "lucide-react";

const LAST_SITE_STORAGE_KEY = "site_devices_last_site";

function readLastSiteId(): string | null {
  try {
    return localStorage.getItem(LAST_SITE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function rememberSiteId(siteId: string) {
  try {
    localStorage.setItem(LAST_SITE_STORAGE_KEY, siteId);
  } catch {
    // Storage blocked: the page opens on the first site next time.
  }
}

function DeviceListItem({ device, onDataMetadata }: { device: Device; onDataMetadata: (device: Device) => void }) {
  const deviceConfig = deviceTypeConfig[device.type];
  const DeviceIcon = deviceConfig.icon;

  const getStatusColor = (status: Device['status']) => {
    switch (status) {
      case 'online': return 'status-ok';
      case 'warning': return 'status-warning';
      case 'offline': return 'status-error';
      case 'fault': return 'status-error';
    }
  };

  const getStatusIcon = (status: Device['status']) => {
    switch (status) {
      case 'online': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'offline': return Clock;
      case 'fault': return XCircle;
    }
  };

  const StatusIcon = getStatusIcon(device.status);

  return (
    <Card className="hover:bg-muted/30 transition-colors">
      <CardContent className="p-4">
        <div className="flex flex-col gap-3">
          <div className="flex min-w-0 items-center space-x-4 flex-1">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${deviceConfig.bgColor}`}>
              <DeviceIcon className={`w-5 h-5 ${deviceConfig.color}`} />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg truncate">{device.name}</h3>
              <p className="text-sm text-muted-foreground">
                {device.make} {device.model} • {device.location}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <div className="text-center">
              <div className="data-metric text-sm">{device.points.length}</div>
              <div className="data-label text-xs">Points</div>
            </div>
            <div className="text-center min-w-[100px]">
              <div className="text-sm font-medium">{device.lastUpdate}</div>
              <div className="data-label text-xs">Updated</div>
            </div>
            <div className="hidden text-center min-w-[80px] sm:block">
              <div className="text-xs">{device.firmware}</div>
              <div className="data-label text-xs">Firmware</div>
            </div>
            <Badge className={`btn-status ${getStatusColor(device.status)} min-w-[80px]`}>
              <StatusIcon className="w-3 h-3 mr-1" />
              {device.status}
            </Badge>
            <Button size="sm" variant="outline" onClick={() => onDataMetadata(device)}>
              <Info className="w-4 h-4 mr-2" />
              Metadata
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function SiteDevices() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");
  // On phones the status cards fold into a one-line summary (always shown from tablet up).
  const [isStatusCardsOpen, setIsStatusCardsOpen] = useState(false);
  // By breakpoint, not width: a phone turned sideways is still a phone.
  const isPhone = useBreakpoint() === "phone";

  const [searchParams, setSearchParams] = useSearchParams();
  const { data: sites, isLoading: areSitesLoading } = useQuery<Site[]>({
    queryKey: ['sites'],
    queryFn: sitesApi.getAll,
  });

  // The site shown: ?siteId, else the one the link passed (Sites > Devices), else the last one
  // viewed here, else the first. Opened from the navigation there is no link state.
  const siteIdParam = searchParams.get('siteId');
  const stateSite: Site | undefined = location.state?.selectedSite;
  const selectedSite: Site | undefined = sites
    ? [siteIdParam, stateSite?.id, readLastSiteId()]
        .map(siteId => siteId && sites.find(site => site.id === siteId))
        .find(Boolean) || sites[0]
    : stateSite;

  // Keep the site in the URL (refresh and shared links) and remember it for next time.
  useEffect(() => {
    if (!selectedSite) return;
    rememberSiteId(selectedSite.id);
    if (siteIdParam !== selectedSite.id) {
      setSearchParams({ siteId: selectedSite.id }, { replace: true, state: location.state });
    }
  }, [selectedSite, siteIdParam, setSearchParams, location.state]);

  useEffect(() => {
    if (sites && sites.length === 0) navigate('/sites');
  }, [sites, navigate]);

  const selectSite = (siteId: string) => {
    const site = sites?.find(candidate => candidate.id === siteId);
    setSearchParams({ siteId }, { state: { selectedSite: site } });
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ['site-devices', selectedSite?.id],
    queryFn: () => devicesApi.getBySite(selectedSite.id),
    enabled: !!selectedSite,
  });

  const devices = data ?? [];

  const filteredDevices = devices.filter(device => {
    const matchesSearch = device.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      device.make.toLowerCase().includes(searchQuery.toLowerCase()) ||
      device.model.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'all' || device.status === statusFilter;
    const matchesType = typeFilter === 'all' || device.type === typeFilter;

    return matchesSearch && matchesStatus && matchesType;
  });

  // The Historian opens on the site; its devices and points are picked in its Trends panel.
  const handleViewData = () => {
    navigate('/historian', { state: { selectedSite } });
  };

  const handleViewMetadata = (device: Device) => {
    navigate(`/devices/${device.id}`, { state: { device, selectedSite } });
  };

  if (!selectedSite && !areSitesLoading) return null;

  if (isLoading || !selectedSite) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <AlertTriangle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h3 className="text-lg font-semibold mb-2">Failed to load site data</h3>
          <p className="text-muted-foreground">Check your connection and try again</p>
        </div>
      </div>
    );
  }

  const statusCounts = {
    online: devices.filter(d => d.status === 'online').length,
    warning: devices.filter(d => d.status === 'warning').length,
    offline: devices.filter(d => d.status === 'offline').length
  };

  return (
    <div className="h-full flex flex-col">
      <div className="border-b border-border p-4 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <Breadcrumb className="mb-4">
              <BreadcrumbList>
                <BreadcrumbItem>
                  <BreadcrumbLink asChild>
                    <Link to="/sites">Sites</Link>
                  </BreadcrumbLink>
                </BreadcrumbItem>
                <BreadcrumbSeparator />
                <BreadcrumbItem>
                  <BreadcrumbPage>{selectedSite.name}</BreadcrumbPage>
                </BreadcrumbItem>
              </BreadcrumbList>
            </Breadcrumb>
            <h1 className="text-2xl md:text-3xl font-bold text-foreground">{selectedSite.name} Devices</h1>
            <p className="text-muted-foreground mt-1">
              {selectedSite.location} • {devices.length} devices configured
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <Select value={selectedSite.id} onValueChange={selectSite}>
              <SelectTrigger className="h-9 w-full sm:w-56" aria-label="Site">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(sites ?? [selectedSite]).map(site => <SelectItem key={site.id} value={site.id}>{site.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm" asChild>
              <Link to="/sites">
                <ArrowLeft className="w-4 h-4 mr-2" />
                Back to Sites
              </Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate('/site-devices/manage', { state: { selectedSite } })}>
              <Settings className="w-4 h-4 mr-2" />
              Configure
            </Button>
            <Button size="sm" onClick={handleViewData}>
              <BarChart3 className="w-4 h-4 mr-2" />
              View Data
            </Button>
          </div>
        </div>
      </div>

      <div className="border-b border-border p-4 md:p-6">
        {isPhone && (
        <button
          type="button"
          onClick={() => setIsStatusCardsOpen(open => !open)}
          aria-expanded={isStatusCardsOpen}
          aria-controls="site-device-status-cards"
          className="flex w-full items-center justify-between gap-2 text-left text-sm"
        >
          <span className="flex flex-wrap gap-x-3 gap-y-1">
            <span className="font-medium">{devices.length} devices</span>
            <span className="text-success">{statusCounts.online} online</span>
            <span className="text-warning">{statusCounts.warning} warnings</span>
            <span className="text-destructive">{statusCounts.offline} offline</span>
          </span>
          <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${isStatusCardsOpen ? "rotate-180" : ""}`} />
        </button>
        )}
        <div
          id="site-device-status-cards"
          className={`${!isPhone ? "grid" : isStatusCardsOpen ? "mt-4 grid" : "hidden"} grid-cols-2 md:grid-cols-4 gap-4`}
        >
          <div className="bg-card rounded-lg p-4 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">Total Devices</p>
                <p className="data-metric">{devices.length}</p>
              </div>
              <Activity className="w-8 h-8 text-primary" />
            </div>
          </div>
          <div className="bg-card rounded-lg p-4 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">Online</p>
                <p className="data-metric text-success">{statusCounts.online}</p>
              </div>
              <CheckCircle className="w-8 h-8 text-success" />
            </div>
          </div>
          <div className="bg-card rounded-lg p-4 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">Warnings</p>
                <p className="data-metric text-warning">{statusCounts.warning}</p>
              </div>
              <AlertTriangle className="w-8 h-8 text-warning" />
            </div>
          </div>
          <div className="bg-card rounded-lg p-4 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">Offline</p>
                <p className="data-metric text-destructive">{statusCounts.offline}</p>
              </div>
              <Clock className="w-8 h-8 text-destructive" />
            </div>
          </div>
        </div>
      </div>

      {/* Search and filters: tablets and laptops only; phones list every device. */}
      {!isPhone && (
      <div className="border-b border-border p-4 md:p-6">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex flex-1 flex-wrap gap-4 items-center">
            <div className="relative w-full sm:w-auto sm:flex-1 sm:min-w-[14rem] max-w-md">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search devices, make, or model..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="online">Online</SelectItem>
                <SelectItem value="warning">Warning</SelectItem>
                <SelectItem value="offline">Offline</SelectItem>
                <SelectItem value="fault">Fault</SelectItem>
              </SelectContent>
            </Select>

            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                {Object.entries(deviceTypeConfig).map(([type, config]) => (
                  <SelectItem key={type} value={type}>
                    {config.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              More Filters
            </Button>
          </div>
        </div>
      </div>
      )}

      <div className="flex-1 overflow-auto p-4 md:p-6">
        {filteredDevices.length === 0 ? (
          <div className="text-center py-12">
            <Activity className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No devices found</h3>
            <p className="text-muted-foreground">
              Try adjusting your search criteria or filters
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredDevices.map((device) => (
              <DeviceListItem
                key={device.id}
                device={device}
                onDataMetadata={handleViewMetadata}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
