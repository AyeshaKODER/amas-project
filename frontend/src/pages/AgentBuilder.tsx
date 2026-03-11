import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import {
  Brain,
  MessageCircle,
  Search,
  Users,
  Zap,
  Grid3X3,
  List,
} from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import type { Agent as ApiAgent } from '@/lib/api/types';
import { ChatInterface } from '@/components/ChatInterface';
import { AgentCard, type AgentCardAgent } from '@/components/AgentCard';
import AppNavbar from '@/components/AppNavbar';

function mapApiAgentToCardAgent(a: ApiAgent): AgentCardAgent {
  return {
    id: a.id,
    name: a.name,
    description: a.description,
    agent_type: a.type,
    model_name: (a.config as { llm_model?: string })?.llm_model ?? a.type,
    is_active: a.status === 'running',
  };
}

const AgentBuilder = () => {
  const [agents, setAgents] = useState<AgentCardAgent[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<AgentCardAgent | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      setError(null);
      const data = await apiClient.getAgents();
      const mapped = data.map(mapApiAgentToCardAgent);
      setAgents(mapped);
      if (mapped.length > 0 && !selectedAgent) {
        setSelectedAgent(mapped[0]);
      }
    } catch (err) {
      console.error('Error loading agents:', err);
      setError('Failed to load agents. Please try refreshing the page.');
    } finally {
      setLoading(false);
    }
  };

  const filteredAgents = agents.filter(
    (agent) =>
      agent.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      agent.agent_type.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleAgentSelect = (agent: AgentCardAgent) => {
    setSelectedAgent(agent);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
        <AppNavbar />
        <main className="pt-4">
          <div className="flex justify-center items-center min-h-[60vh]">
            <div className="text-center">
              <div className="animate-spin h-12 w-12 border-4 border-primary border-t-transparent rounded-full mx-auto mb-4" />
              <p className="text-muted-foreground">Loading agents...</p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/20">
      <AppNavbar />
      <main className="pt-4">
        <section className="py-8 px-4">
          <div className="container mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
            >
              <h1 className="text-3xl md:text-5xl font-bold mb-4 text-foreground">
                AI Agent Builder
              </h1>
              <p className="text-lg text-muted-foreground mb-6 max-w-2xl mx-auto">
                Interact with specialized AI agents. Each agent is designed for specific tasks and
                maintains separate conversation contexts.
              </p>
              <div className="flex justify-center gap-4 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4" />
                  <span>{agents.length} Agents</span>
                </div>
                <div className="flex items-center gap-2">
                  <Zap className="h-4 w-4" />
                  <span>Real-time Chat</span>
                </div>
                <div className="flex items-center gap-2">
                  <Brain className="h-4 w-4" />
                  <span>Powered by AMAS API</span>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        <section className="px-4 pb-16">
          <div className="container mx-auto">
            {error && (
              <div className="mb-4 p-4 rounded-lg bg-destructive/10 text-destructive text-sm">
                {error}
              </div>
            )}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 min-h-[600px]">
              <div className="lg:col-span-1 space-y-4">
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <MessageCircle className="h-5 w-5" />
                      Available Agents
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="relative">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                      <Input
                        placeholder="Search agents..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-10"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant={viewMode === 'grid' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setViewMode('grid')}
                      >
                        <Grid3X3 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant={viewMode === 'list' ? 'default' : 'ghost'}
                        size="sm"
                        onClick={() => setViewMode('list')}
                      >
                        <List className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                <ScrollArea className="h-[450px]">
                  <div className={`space-y-3 ${viewMode === 'grid' ? 'grid grid-cols-1 gap-3' : ''}`}>
                    <AnimatePresence>
                      {filteredAgents.map((agent) => (
                        <AgentCard
                          key={agent.id}
                          agent={agent}
                          isSelected={selectedAgent?.id === agent.id}
                          onClick={() => handleAgentSelect(agent)}
                        />
                      ))}
                    </AnimatePresence>
                    {filteredAgents.length === 0 && (
                      <div className="text-center py-12 text-muted-foreground">
                        <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>No agents found.</p>
                      </div>
                    )}
                  </div>
                </ScrollArea>
              </div>

              <div className="lg:col-span-2">
                <AnimatePresence mode="wait">
                  {selectedAgent ? (
                    <motion.div
                      key={selectedAgent.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      transition={{ duration: 0.3 }}
                      className="h-full min-h-[500px]"
                    >
                      <ChatInterface agent={selectedAgent} />
                    </motion.div>
                  ) : (
                    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="h-full">
                      <Card className="h-full min-h-[500px] flex items-center justify-center">
                        <div className="text-center space-y-4 p-8">
                          <div className="h-24 w-24 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
                            <MessageCircle className="h-12 w-12 text-primary" />
                          </div>
                          <div>
                            <h3 className="text-xl font-semibold text-foreground mb-2">
                              Select an Agent to Start Chatting
                            </h3>
                            <p className="text-muted-foreground max-w-md">
                              Choose from our specialized AI agents to get help with research,
                              content creation, data analysis, and more.
                            </p>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
};

export default AgentBuilder;
