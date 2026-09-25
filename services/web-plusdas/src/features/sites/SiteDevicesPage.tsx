import { useState, useEffect } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";
import type { Device } from "@/shared/types/device";
import { devicesApi } from "@/api";
import { deviceTypeConfig } from "@/shared/config/device-types";
import {
  Search, Activity, Filter, ArrowLeft, BarChart3,
  AlertTriangle, CheckCircle, Clock, Settings, XCircle, Info
} from "lucide-react";

function DeviceListItem({ device, onViewHistorian, onDataMetadata }: { device: Device; onViewHistorian: (device: Device) => void, onDataMetadata: (device: Device) => void }) {
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
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4 flex-1">
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

          <div className="flex items-center space-x-6">
            <div className="text-center">
              <div className="data-metric text-sm">{device.points.length}</div>
              <div className="data-label text-xs">Points</div>
            </div>
            <div className="text-center min-w-[100px]">
              <div className="text-sm font-medium">{device.lastUpdate}</div>
              <div className="data-label text-xs">Updated</div>
            </div>
            <div className="text-center min-w-[80px]">
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
            <Button size="sm" onClick={() => onViewHistorian(device)}>
              <BarChart3 className="w-4 h-4 mr-2" />
              View Data
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

  const selectedSite = location.state?.selectedSite;

  useEffect(() => {
    if (!selectedSite) {
      navigate('/sites');
    }
  }, [selectedSite, navigate]);

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

  const handleViewHistorian = (device: Device) => {
    navigate('/historian', { state: { selectedSite, selectedDevice: device } });
  };

  const handleViewMetadata = (device: Device) => {
    navigate(`/devices/${device.id}`, { state: { device, selectedSite } });
  };

  if (!selectedSite) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-screen">
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
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
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
            <h1 className="text-3xl font-bold text-foreground">{selectedSite.name} Devices</h1>
            <p className="text-muted-foreground mt-1">
              {selectedSite.location} • {devices.length} devices configured
            </p>
          </div>
          <div className="flex space-x-2">
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
          </div>
        </div>
      </div>

      <div className="border-b border-border p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
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

      <div className="border-b border-border p-6">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex flex-1 gap-4 items-center">
            <div className="relative flex-1 max-w-md">
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
                <SelectItem value="transformer">Transformer</SelectItem>
                <SelectItem value="generator">Generator</SelectItem>
                <SelectItem value="protection">Protection</SelectItem>
                <SelectItem value="feeder">Feeder</SelectItem>
                <SelectItem value="switch">Switch</SelectItem>
                <SelectItem value="meter">Meter</SelectItem>
                <SelectItem value="pv">PV</SelectItem>
                <SelectItem value="bess">BESS</SelectItem>
                <SelectItem value="relay">Relay</SelectItem>
              </SelectContent>
            </Select>

            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              More Filters
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
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
                onViewHistorian={handleViewHistorian}
                onDataMetadata={handleViewMetadata}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
