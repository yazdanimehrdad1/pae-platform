import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent } from "@/components/ui/card";
import type { Site } from "@/shared/types/site";
import { sitesApi } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Building2, Search, MapPin, Filter, Settings,
  AlertTriangle, CheckCircle, Clock, Network
} from "lucide-react";
import { useNavigate } from "react-router-dom";

function SiteListItem({ site, onSelect }: { site: Site; onSelect: (site: Site) => void }) {
  const navigate = useNavigate();

  const getStatusColor = (status: Site['status']) => {
    switch (status) {
      case 'online': return 'bg-success text-success-foreground hover:bg-success/90';
      case 'warning': return 'bg-warning text-warning-foreground hover:bg-warning/90';
      case 'offline': return 'bg-destructive text-destructive-foreground hover:bg-destructive/90';
    }
  };

  const getStatusIcon = (status: Site['status']) => {
    switch (status) {
      case 'online': return CheckCircle;
      case 'warning': return AlertTriangle;
      case 'offline': return Clock;
    }
  };

  const StatusIcon = getStatusIcon(site.status);

  const handleViewSLD = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate('/sld', { state: { siteId: site.id, siteName: site.name } });
  };

  return (
    <Card className="hover:bg-muted/30 transition-colors cursor-pointer" onClick={() => onSelect(site)}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4 flex-1">
            <div className="w-10 h-10 bg-gradient-secondary rounded-lg flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <h3 className="font-semibold text-lg truncate">{site.name}</h3>
              <p className="text-sm text-muted-foreground flex items-center">
                <MapPin className="w-3 h-3 mr-1" />
                {site.location}
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-6">
            <div className="text-center">
              <div className="data-metric text-sm">{site.capacity}</div>
              <div className="data-label text-xs">Capacity</div>
            </div>
            <div className="text-center min-w-[80px]">
              <div className="text-sm font-medium">{site.operator}</div>
              <div className="data-label text-xs">Operator</div>
            </div>
            <div className="text-center min-w-[90px]">
              <div className="text-xs">{site.lastUpdate}</div>
              <div className="data-label text-xs">Updated</div>
            </div>
            <Badge className={`btn-status ${getStatusColor(site.status)} min-w-[80px]`}>
              <StatusIcon className="w-3 h-3 mr-1" />
              {site.status}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={handleViewSLD}
              className="gap-2"
            >
              <Network className="w-4 h-4" />
              View SLD
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Sites() {
  const { data: sites = [], isLoading, isError } = useQuery<Site[]>({
    queryKey: ['sites'],
    queryFn: sitesApi.getAll,
  });
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const navigate = useNavigate();

  const filteredSites = sites.filter(site => {
    const matchesSearch = site.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      site.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
      site.operator.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus = statusFilter === 'all' || site.status === statusFilter;
    const matchesType = typeFilter === 'all' || site.type === typeFilter;

    return matchesSearch && matchesStatus && matchesType;
  });

  const handleSiteSelect = (site: Site) => {
    navigate('/site-devices', { state: { selectedSite: site } });
  };

  const statusCounts = {
    online: sites.filter(s => s.status === 'online').length,
    warning: sites.filter(s => s.status === 'warning').length,
    offline: sites.filter(s => s.status === 'offline').length
  };

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
          <h3 className="text-lg font-semibold mb-2">Failed to load sites</h3>
          <p className="text-muted-foreground">Check your connection and try again</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Sites</h1>
            <p className="text-muted-foreground mt-1">
              Select a site to access historian data and monitoring tools
            </p>
          </div>
          <div className="flex space-x-2">
            <Button variant="outline" size="sm" onClick={() => navigate('/sites/manage')}>
              <Settings className="w-4 h-4 mr-2" />
              Manage
            </Button>
          </div>
        </div>
      </div>

      <div className="border-b border-border p-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-card rounded-lg p-4 border">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">Total Sites</p>
                <p className="data-metric">{sites.length}</p>
              </div>
              <Building2 className="w-8 h-8 text-primary" />
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
                placeholder="Search sites, locations, or operators..."
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
              </SelectContent>
            </Select>

            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Types</SelectItem>
                <SelectItem value="substation">Substation</SelectItem>
                <SelectItem value="plant">Plant</SelectItem>
                <SelectItem value="facility">Facility</SelectItem>
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
        {filteredSites.length === 0 ? (
          <div className="text-center py-12">
            <Building2 className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-semibold mb-2">No sites found</h3>
            <p className="text-muted-foreground">
              Try adjusting your search criteria or filters
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSites.map((site) => (
              <SiteListItem key={site.id} site={site} onSelect={handleSiteSelect} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
