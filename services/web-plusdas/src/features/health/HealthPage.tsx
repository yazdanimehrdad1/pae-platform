import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Activity, AlertTriangle, CheckCircle, XCircle, Clock, Filter, TestTube } from "lucide-react";
import { useMockHealth } from "./hooks/useMockHealth";

const deviceList = [
  "Transformer T1", "Transformer T2", "Generator G1", "Feeder F1",
  "Protection P1", "Protection P2", "Switch S1", "Switch S2"
];

function HealthTimeline() {
  const { data: healthData, isLoading } = useMockHealth(deviceList);
  const [timeRange, setTimeRange] = useState("24h");

  if (isLoading) {
    return (
      <div className="h-96 flex items-center justify-center">
        <div className="text-muted-foreground">Loading health data...</div>
      </div>
    );
  }

  const timeSlots = 24;
  const now = Date.now();
  const slotDuration = 60 * 60 * 1000;

  const deviceHealthMap = deviceList.reduce((acc, deviceId) => {
    acc[deviceId] = Array(timeSlots).fill(2);

    const deviceData = healthData.filter(h => h.deviceId === deviceId);
    deviceData.forEach(health => {
      const slotIndex = Math.floor((now - health.timestamp) / slotDuration);
      if (slotIndex >= 0 && slotIndex < timeSlots) {
        acc[deviceId][timeSlots - 1 - slotIndex] = health.state;
      }
    });

    return acc;
  }, {} as Record<string, number[]>);

  const getStateColor = (state: number) => {
    switch (state) {
      case 0: return 'bg-destructive';
      case 1: return 'bg-warning';
      case 2: return 'bg-success';
      default: return 'bg-muted';
    }
  };

  const getStateLabel = (state: number) => {
    switch (state) {
      case 0: return 'Down';
      case 1: return 'Warning';
      case 2: return 'OK';
      default: return 'Unknown';
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center">
            <Activity className="w-5 h-5 mr-2" />
            Device Health Timeline
          </CardTitle>
          <div className="flex items-center space-x-2">
            <Select value={timeRange} onValueChange={setTimeRange}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1h">Last Hour</SelectItem>
                <SelectItem value="24h">Last 24 Hours</SelectItem>
                <SelectItem value="7d">Last 7 Days</SelectItem>
                <SelectItem value="30d">Last 30 Days</SelectItem>
              </SelectContent>
            </Select>
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              Filter
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex text-xs text-muted-foreground mb-2">
            <div className="w-32"></div>
            <div className="flex-1 flex justify-between">
              <span>24h ago</span>
              <span>12h ago</span>
              <span>Now</span>
            </div>
          </div>

          {Object.entries(deviceHealthMap).map(([deviceId, states]) => (
            <div key={deviceId} className="flex items-center">
              <div className="w-32 text-sm font-medium truncate pr-4">
                {deviceId}
              </div>
              <div className="flex-1 flex gap-1">
                {states.map((state, index) => (
                  <div
                    key={index}
                    className={`timeline-segment ${getStateColor(state)}`}
                    title={`${getStateLabel(state)} - ${deviceId}`}
                    style={{ flex: 1 }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-center space-x-6 mt-6 pt-4 border-t border-border">
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-success rounded"></div>
            <span className="text-xs text-muted-foreground">OK</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-warning rounded"></div>
            <span className="text-xs text-muted-foreground">Warning</span>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-4 h-4 bg-destructive rounded"></div>
            <span className="text-xs text-muted-foreground">Down</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function PerformanceInformation() {
  const passedSystems = [
    { name: 'BESS Unit 1', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-1' },
    { name: 'BESS Unit 2', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-2' },
    { name: 'BESS Unit 3', test: 'Self Discharge', status: 'PASS', lastRun: 'Dec 12, 2024 14:30', reportId: 'report-3' },
    { name: 'Transformer T1', test: 'Thermal Performance', status: 'PASS', lastRun: 'Dec 11, 2024 16:45', reportId: 'report-4' },
    { name: 'Transformer T2', test: 'Thermal Performance', status: 'PASS', lastRun: 'Dec 11, 2024 16:45', reportId: 'report-5' },
  ];

  const handleGoToReport = (reportId: string) => {
    console.log('Navigate to report:', reportId);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center">
          <Activity className="w-5 h-5 mr-2" />
          Performance Information
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div>
          <div className="flex items-center space-x-2 mb-4">
            <TestTube className="w-5 h-5 text-success" />
            <h3 className="text-lg font-semibold">Systems Passed Tests</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {passedSystems.map((system, index) => {
              const isPass = system.status === 'PASS';
              return (
                <div key={index} className={`p-4 rounded-lg border ${isPass ? 'bg-success/5 border-success/20' : 'bg-destructive/5 border-destructive/20'}`}>
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center space-x-3 flex-1">
                      {isPass ? (
                        <CheckCircle className="w-5 h-5 text-success flex-shrink-0" />
                      ) : (
                        <XCircle className="w-5 h-5 text-destructive flex-shrink-0" />
                      )}
                      <div className="flex-1">
                        <div className="text-sm font-semibold">{system.name}</div>
                        <div className="text-xs text-muted-foreground">{system.test}</div>
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className={isPass ? 'bg-success/10 text-success border-success' : 'bg-destructive/10 text-destructive border-destructive'}
                    >
                      {system.status}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="text-xs text-muted-foreground">
                      Last run: {system.lastRun}
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleGoToReport(system.reportId)}
                      className="h-7 text-xs"
                    >
                      Go to Report
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function HealthSummary() {
  const { data: healthData } = useMockHealth(deviceList);

  const latestStates = deviceList.map(deviceId => {
    const deviceData = healthData.filter(h => h.deviceId === deviceId);
    return deviceData.length > 0 ? deviceData[0].state : 2;
  });

  const okCount = latestStates.filter(s => s === 2).length;
  const warningCount = latestStates.filter(s => s === 1).length;
  const downCount = latestStates.filter(s => s === 0).length;

  const stats = [
    { title: "Online", value: okCount, total: deviceList.length, icon: CheckCircle, color: "text-success", bgColor: "bg-success/10" },
    { title: "Warnings", value: warningCount, total: deviceList.length, icon: AlertTriangle, color: "text-warning", bgColor: "bg-warning/10" },
    { title: "Offline", value: downCount, total: deviceList.length, icon: XCircle, color: "text-destructive", bgColor: "bg-destructive/10" },
    { title: "Uptime", value: Math.round((okCount / deviceList.length) * 100), unit: "%", icon: Clock, color: "text-primary", bgColor: "bg-primary/10" }
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
      {stats.map((stat) => (
        <Card key={stat.title} className="card-industrial">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label">{stat.title}</p>
                <div className="flex items-baseline space-x-1">
                  <span className="data-metric">{stat.value}</span>
                  {stat.total && (
                    <span className="text-sm text-muted-foreground">/ {stat.total}</span>
                  )}
                  {stat.unit && (
                    <span className="text-sm text-muted-foreground">{stat.unit}</span>
                  )}
                </div>
              </div>
              <div className={`w-12 h-12 rounded-lg ${stat.bgColor} flex items-center justify-center`}>
                <stat.icon className={`w-6 h-6 ${stat.color}`} />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function Health() {
  return (
    <div className="h-screen flex flex-col">
      <div className="border-b border-border p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-foreground">Health Board</h1>
            <p className="text-muted-foreground mt-1">Real-time system health and device status monitoring</p>
          </div>
          <div className="flex space-x-2">
            <Badge variant="outline" className="bg-success/10 text-success border-success">
              All Systems Operational
            </Badge>
            <Button variant="outline" size="sm">
              Export Report
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        <HealthTimeline />
        <PerformanceInformation />
      </div>
    </div>
  );
}
