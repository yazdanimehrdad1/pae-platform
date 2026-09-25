import { useState } from "react";
import { Bot, Send, Clock, CheckCircle2, AlertCircle, Sparkles, FileText, Plus } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

const exampleTasks = [
  { id: '1', title: 'Daily Energy Report Automation', description: 'Generate and email a daily energy consumption summary to the operations team at 8 AM.', status: 'pending', createdAt: 'Dec 12, 2024' },
  { id: '2', title: 'Peak Demand Alert', description: 'Monitor all feeders and send an alert when any feeder exceeds 85% capacity for more than 5 minutes.', status: 'active', createdAt: 'Dec 10, 2024' },
  { id: '3', title: 'Monthly Compliance Check', description: 'At the start of each month, verify all power quality parameters meet regulatory standards and flag deviations.', status: 'completed', createdAt: 'Dec 1, 2024' },
];

const TaskBuilder = () => {
  const [taskTitle, setTaskTitle] = useState('');
  const [taskDescription, setTaskDescription] = useState('');

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'active': return <Badge className="bg-success/20 text-success border-success">Active</Badge>;
      case 'pending': return <Badge className="bg-warning/20 text-warning border-warning">Pending Review</Badge>;
      case 'completed': return <Badge variant="secondary">Completed</Badge>;
      default: return <Badge variant="outline">{status}</Badge>;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <CheckCircle2 className="w-5 h-5 text-success" />;
      case 'pending': return <Clock className="w-5 h-5 text-warning" />;
      case 'completed': return <CheckCircle2 className="w-5 h-5 text-muted-foreground" />;
      default: return <AlertCircle className="w-5 h-5" />;
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-foreground">AI Task Builder</h1>
          <p className="text-muted-foreground mt-1">
            Describe tasks in natural language for the AI agent to automate
          </p>
        </div>
        <Badge variant="outline" className="gap-2 px-3 py-1">
          <Sparkles className="w-4 h-4 text-primary" />
          Engineer Access Only
        </Badge>
      </div>

      <Card className="bg-primary/5 border-primary/20">
        <CardContent className="p-4">
          <div className="flex items-start gap-4">
            <div className="w-10 h-10 bg-primary/20 rounded-lg flex items-center justify-center shrink-0">
              <Bot className="w-5 h-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-foreground">How it works</h3>
              <p className="text-sm text-muted-foreground mt-1">
                Write your automation requirements in plain English. Our AI agent will analyze your request,
                create executable tasks, and set up the necessary monitoring and actions. Tasks go through
                a review process before activation.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Plus className="w-5 h-5" />
            Create New Task
          </CardTitle>
          <CardDescription>
            Describe what you want the system to do automatically
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-foreground mb-2 block">Task Title</label>
            <Input
              placeholder="e.g., Automated Load Balancing Alert"
              value={taskTitle}
              onChange={(e) => setTaskTitle(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-foreground mb-2 block">Task Description</label>
            <Textarea
              placeholder="Describe in detail what you want the AI to do..."
              value={taskDescription}
              onChange={(e) => setTaskDescription(e.target.value)}
              className="min-h-[150px]"
            />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Tasks will be reviewed by the AI agent before activation
            </p>
            <Button className="gap-2">
              <Send className="w-4 h-4" />
              Submit Task
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            Your Tasks
          </CardTitle>
          <CardDescription>Tasks you've created for the AI agent</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {exampleTasks.map((task) => (
              <div
                key={task.id}
                className="flex items-start gap-4 p-4 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
              >
                {getStatusIcon(task.status)}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h4 className="font-medium text-foreground">{task.title}</h4>
                    {getStatusBadge(task.status)}
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">{task.description}</p>
                  <p className="text-xs text-muted-foreground mt-2">Created: {task.createdAt}</p>
                </div>
                <Button variant="ghost" size="sm">View Details</Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TaskBuilder;
