import { FileText, Download, Calendar, Filter, BarChart3, PieChart, TrendingUp, Clock } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const reportTypes = [
  { id: 'energy-consumption', title: 'Energy Consumption Report', description: 'Daily, weekly, and monthly energy usage analysis', icon: BarChart3, lastGenerated: '2 hours ago', frequency: 'Daily' },
  { id: 'power-quality', title: 'Power Quality Report', description: 'Voltage, frequency, and harmonic distortion analysis', icon: TrendingUp, lastGenerated: '1 day ago', frequency: 'Weekly' },
  { id: 'demand-analysis', title: 'Demand Analysis Report', description: 'Peak demand patterns and load factor calculations', icon: PieChart, lastGenerated: '3 hours ago', frequency: 'Daily' },
  { id: 'alarm-summary', title: 'Alarm Summary Report', description: 'Consolidated alarm and event history', icon: Clock, lastGenerated: '30 minutes ago', frequency: 'Real-time' },
];

const recentReports = [
  { name: 'Energy_Report_Dec_2024.pdf', date: 'Dec 12, 2024', size: '2.4 MB', status: 'ready' },
  { name: 'Power_Quality_Week49.pdf', date: 'Dec 10, 2024', size: '1.8 MB', status: 'ready' },
  { name: 'Demand_Analysis_Q4.pdf', date: 'Dec 8, 2024', size: '3.1 MB', status: 'ready' },
  { name: 'Monthly_Summary_Nov.pdf', date: 'Nov 30, 2024', size: '4.2 MB', status: 'ready' },
];

const Reports = () => {
  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">Reports</h1>
          <p className="text-muted-foreground mt-1">Generate and manage system reports</p>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="outline" className="gap-2">
            <Calendar className="w-4 h-4" />
            Schedule Report
          </Button>
          <Button className="gap-2">
            <FileText className="w-4 h-4" />
            New Report
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {reportTypes.map((report) => {
          const Icon = report.icon;
          return (
            <Card key={report.id} className="hover:shadow-lg transition-shadow cursor-pointer">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                    <Icon className="w-5 h-5 text-primary" />
                  </div>
                  <Badge variant="secondary">{report.frequency}</Badge>
                </div>
                <CardTitle className="text-lg mt-3">{report.title}</CardTitle>
                <CardDescription>{report.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Last: {report.lastGenerated}</span>
                  <Button variant="ghost" size="sm" className="gap-1">
                    <Download className="w-3 h-3" />
                    Generate
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Recent Reports</CardTitle>
              <CardDescription>Previously generated reports available for download</CardDescription>
            </div>
            <Button variant="outline" size="sm" className="gap-2">
              <Filter className="w-4 h-4" />
              Filter
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {recentReports.map((report, index) => (
              <div
                key={index}
                className="flex items-center justify-between p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-primary" />
                  <div>
                    <p className="font-medium text-foreground">{report.name}</p>
                    <p className="text-sm text-muted-foreground">{report.date} • {report.size}</p>
                  </div>
                </div>
                <Button variant="ghost" size="sm" className="gap-2">
                  <Download className="w-4 h-4" />
                  Download
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default Reports;
