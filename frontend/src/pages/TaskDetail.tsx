import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/api/client';
import { Task, TaskLog } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Clock, CheckCircle2, AlertCircle, Loader2, Info, AlertTriangle } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';

const TaskDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      if (!id) return;
      try {
        const [taskData, logsData] = await Promise.all([
          apiClient.getTask(id),
          apiClient.getTaskLogs(id)
        ]);
        setTask(taskData);
        setLogs(logsData);
      } catch (error) {
        console.error('Failed to load task:', error);
        navigate('/tasks');
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [id]);

  const getLogIcon = (level: TaskLog['level']) => {
    switch (level) {
      case 'error':
        return <AlertCircle className="h-4 w-4 text-destructive" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case 'info':
        return <Info className="h-4 w-4 text-primary" />;
      case 'debug':
        return <Info className="h-4 w-4 text-muted-foreground" />;
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-8 space-y-6">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-96" />
        </div>
      </DashboardLayout>
    );
  }

  if (!task) return null;

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/tasks')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-semibold">{task.title}</h1>
            <p className="text-muted-foreground mt-1">{task.agent_name}</p>
          </div>
          <span className={`status-badge status-${task.status}`}>
            {task.status}
          </span>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Task Logs</CardTitle>
              <CardDescription>Real-time execution logs and events</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[600px] pr-4">
                <div className="space-y-3">
                  {logs.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No logs available yet
                    </p>
                  ) : (
                    logs.map(log => (
                      <div key={log.id} className="flex gap-3 p-3 rounded-lg border border-border">
                        {getLogIcon(log.level)}
                        <div className="flex-1 space-y-1">
                          <div className="flex items-center justify-between">
                            <span className={`text-xs font-medium uppercase ${
                              log.level === 'error' ? 'text-destructive' :
                              log.level === 'warning' ? 'text-warning' :
                              log.level === 'info' ? 'text-primary' :
                              'text-muted-foreground'
                            }`}>
                              {log.level}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <p className="text-sm">{log.message}</p>
                          {log.metadata && (
                            <pre className="text-xs bg-muted p-2 rounded mt-2 overflow-x-auto">
                              {JSON.stringify(log.metadata, null, 2)}
                            </pre>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-2">
                  {task.status === 'completed' && <CheckCircle2 className="h-5 w-5 text-success" />}
                  {task.status === 'running' && <Loader2 className="h-5 w-5 text-primary animate-spin" />}
                  {task.status === 'failed' && <AlertCircle className="h-5 w-5 text-destructive" />}
                  {task.status === 'pending' && <Clock className="h-5 w-5 text-warning" />}
                  <span className="font-medium capitalize">{task.status}</span>
                </div>

                {task.progress !== undefined && task.status === 'running' && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Progress</span>
                      <span className="font-medium">{task.progress}%</span>
                    </div>
                    <Progress value={task.progress} />
                  </div>
                )}

                {task.error && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                    <p className="text-sm text-destructive">{task.error}</p>
                  </div>
                )}

                {task.result && (
                  <div className="p-3 bg-success-light border border-success/20 rounded-md">
                    <p className="text-sm">{task.result}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Details</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Priority</p>
                  <Badge variant="outline" className="mt-1 capitalize">
                    {task.priority}
                  </Badge>
                </div>
                <div>
                  <p className="text-muted-foreground">Created</p>
                  <p className="font-medium">
                    {new Date(task.created_at).toLocaleString()}
                  </p>
                </div>
                {task.completed_at && (
                  <div>
                    <p className="text-muted-foreground">Completed</p>
                    <p className="font-medium">
                      {new Date(task.completed_at).toLocaleString()}
                    </p>
                  </div>
                )}
                <div>
                  <p className="text-muted-foreground">Task ID</p>
                  <p className="font-mono text-xs">{task.id}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default TaskDetail;