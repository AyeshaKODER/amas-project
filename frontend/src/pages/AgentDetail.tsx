import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '@/lib/api/client';
import { Agent } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, Bot, Play, Square, Circle, Clock, Settings } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { toast } from '@/hooks/use-toast';

const AgentDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  const loadAgent = async () => {
    if (!id) return;
    try {
      const data = await apiClient.getAgent(id);
      setAgent(data);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load agent details',
        variant: 'destructive'
      });
      navigate('/agents');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgent();
  }, [id]);

  const handleStart = async () => {
    if (!agent) return;
    setActionLoading(true);
    try {
      await apiClient.startAgent(agent.id);
      await loadAgent();
      toast({
        title: 'Agent Started',
        description: `${agent.name} is now running`
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to start agent',
        variant: 'destructive'
      });
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    if (!agent) return;
    setActionLoading(true);
    try {
      await apiClient.stopAgent(agent.id);
      await loadAgent();
      toast({
        title: 'Agent Stopped',
        description: `${agent.name} has been stopped`
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to stop agent',
        variant: 'destructive'
      });
    } finally {
      setActionLoading(false);
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

  if (!agent) return null;

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => navigate('/agents')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-semibold">{agent.name}</h1>
            <p className="text-muted-foreground mt-1 capitalize">{agent.type} Agent</p>
          </div>
          <div className="flex items-center gap-2">
            <Circle 
              className={`h-2.5 w-2.5 fill-current ${
                agent.status === 'running' ? 'text-success animate-pulse-subtle' : 'text-muted-foreground'
              }`} 
            />
            <span className={`text-sm font-medium capitalize ${
              agent.status === 'running' ? 'text-success' : 'text-muted-foreground'
            }`}>
              {agent.status}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Agent Information</CardTitle>
              <CardDescription>Details and configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Description</h3>
                <p className="text-sm">{agent.description}</p>
              </div>

              <div>
                <h3 className="text-sm font-medium text-muted-foreground mb-2">Capabilities</h3>
                <div className="flex flex-wrap gap-2">
                  {agent.capabilities.map(cap => (
                    <Badge key={cap} variant="secondary">
                      {cap.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>
              </div>

              {agent.config && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">Configuration</h3>
                  <div className="bg-muted rounded-md p-4">
                    <pre className="text-xs font-mono">
                      {JSON.stringify(agent.config, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Control</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {agent.status === 'running' ? (
                  <Button
                    variant="destructive"
                    className="w-full"
                    onClick={handleStop}
                    disabled={actionLoading}
                  >
                    <Square className="h-4 w-4 mr-2" />
                    Stop Agent
                  </Button>
                ) : (
                  <Button
                    variant="default"
                    className="w-full"
                    onClick={handleStart}
                    disabled={actionLoading}
                  >
                    <Play className="h-4 w-4 mr-2" />
                    Start Agent
                  </Button>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Timeline
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Created</p>
                  <p className="font-medium">
                    {new Date(agent.created_at).toLocaleDateString()}
                  </p>
                </div>
                {agent.last_active && (
                  <div>
                    <p className="text-muted-foreground">Last Active</p>
                    <p className="font-medium">
                      {new Date(agent.last_active).toLocaleString()}
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Settings className="h-4 w-4" />
                  Metadata
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Agent ID</p>
                  <p className="font-mono text-xs">{agent.id}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Type</p>
                  <p className="capitalize">{agent.type}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
};

export default AgentDetail;