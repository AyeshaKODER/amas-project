import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { MessageCircle, Zap } from 'lucide-react';

export interface AgentCardAgent {
  id: string;
  name: string;
  description: string;
  agent_type: string;
  model_name?: string;
  is_active?: boolean;
}

interface AgentCardProps {
  agent: AgentCardAgent;
  isSelected: boolean;
  onClick: () => void;
}

const getAgentIcon = (agentType: string) => {
  switch (agentType) {
    case 'research': return '🔬';
    case 'content': return '✍️';
    case 'analyst': return '📊';
    case 'planner': return '📋';
    case 'executor': return '⚙️';
    case 'memory': return '💾';
    case 'automation': return '🤖';
    case 'coding': return '💻';
    default: return '🤖';
  }
};

const getAgentColor = (agentType: string) => {
  switch (agentType) {
    case 'research': return 'bg-blue-500/10 text-blue-600';
    case 'content': return 'bg-purple-500/10 text-purple-600';
    case 'analyst': return 'bg-green-500/10 text-green-600';
    case 'planner': return 'bg-amber-500/10 text-amber-600';
    case 'executor': return 'bg-orange-500/10 text-orange-600';
    case 'memory': return 'bg-cyan-500/10 text-cyan-600';
    case 'automation': return 'bg-orange-500/10 text-orange-600';
    case 'coding': return 'bg-red-500/10 text-red-600';
    default: return 'bg-gray-500/10 text-gray-600';
  }
};

export const AgentCard = ({ agent, isSelected, onClick }: AgentCardProps) => {
  const modelName = agent.model_name ?? agent.agent_type;
  const isActive = agent.is_active ?? true;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
    >
      <Card
        className={`cursor-pointer transition-all duration-200 hover:shadow-md ${
          isSelected ? 'ring-2 ring-primary shadow-lg bg-primary/5' : 'hover:bg-muted/50'
        }`}
        onClick={onClick}
      >
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12">
                <AvatarFallback className={`text-xl ${getAgentColor(agent.agent_type)}`}>
                  {getAgentIcon(agent.agent_type)}
                </AvatarFallback>
              </Avatar>
              <div>
                <h3 className="font-semibold text-foreground">{agent.name}</h3>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="secondary" className={`text-xs ${getAgentColor(agent.agent_type)}`}>
                    {agent.agent_type}
                  </Badge>
                  {isActive && (
                    <div className="flex items-center gap-1">
                      <div className="h-2 w-2 bg-green-500 rounded-full animate-pulse" />
                      <span className="text-xs text-green-600">Online</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
            {isSelected && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="h-8 w-8 bg-primary rounded-full flex items-center justify-center"
              >
                <MessageCircle className="h-4 w-4 text-primary-foreground" />
              </motion.div>
            )}
          </div>
        </CardHeader>
        <CardContent className="pt-0">
          <p className="text-sm text-muted-foreground mb-4 line-clamp-2">{agent.description}</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 text-xs text-muted-foreground">
              <Zap className="h-3 w-3" />
              {modelName}
            </div>
            <Button variant={isSelected ? 'default' : 'outline'} size="sm" className="text-xs">
              {isSelected ? 'Active' : 'Select'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
};
