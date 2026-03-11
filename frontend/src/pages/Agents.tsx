import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '@/lib/api/client';
import { Agent } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Bot, Play, Square, Circle } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { toast } from '@/hooks/use-toast';

const Agents = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadAgents = async () => {
    try {
      const data = await apiClient.getAgents();
      setAgents(data);
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to load agents',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAgents();
  }, []);

  const handleStart = async (id: string) => {
    setActionLoading(id);
    try {
      await apiClient.startAgent(id);
      await loadAgents();
      toast({
        title: 'Agent Started',
        description: 'Agent is now running'
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to start agent',
        variant: 'destructive'
      });
    } finally {
      setActionLoading(null);
    }
  };

  const handleStop = async (id: string) => {
    setActionLoading(id);
    try {
      await apiClient.stopAgent(id);
      await loadAgents();
      toast({
        title: 'Agent Stopped',
        description: 'Agent has been stopped'
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to stop agent',
        variant: 'destructive'
      });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="p-8 space-y-6">
          <Skeleton className="h-10 w-64" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-64" />)}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold">Agents</h1>
            <p className="text-muted-foreground mt-1">Manage your autonomous agents</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {agents.map(agent => (
            <Card key={agent.id} className="card-hover">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-primary-light">
                      <Bot className="h-5 w-5 text-primary" />
                    </div>
                    <div>
                      <CardTitle className="text-lg">{agent.name}</CardTitle>
                      <CardDescription className="capitalize">{agent.type} Agent</CardDescription>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Circle 
                      className={`h-2 w-2 fill-current ${
                        agent.status === 'running' ? 'text-success animate-pulse-subtle' : 'text-muted-foreground'
                      }`} 
                    />
                    <span className={`text-sm capitalize ${
                      agent.status === 'running' ? 'text-success font-medium' : 'text-muted-foreground'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-muted-foreground">{agent.description}</p>
                
                <div className="flex flex-wrap gap-1.5">
                  {agent.capabilities.map(cap => (
                    <Badge key={cap} variant="secondary" className="text-xs">
                      {cap.replace(/_/g, ' ')}
                    </Badge>
                  ))}
                </div>

                <div className="flex items-center gap-2 pt-2">
                  <Link to={`/agents/${agent.id}`} className="flex-1">
                    <Button variant="outline" className="w-full">
                      View Details
                    </Button>
                  </Link>
                  {agent.status === 'running' ? (
                    <Button
                      variant="destructive"
                      size="icon"
                      onClick={() => handleStop(agent.id)}
                      disabled={actionLoading === agent.id}
                    >
                      <Square className="h-4 w-4" />
                    </Button>
                  ) : (
                    <Button
                      variant="default"
                      size="icon"
                      onClick={() => handleStart(agent.id)}
                      disabled={actionLoading === agent.id}
                    >
                      <Play className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
};

export default Agents;