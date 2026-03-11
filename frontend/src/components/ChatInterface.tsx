import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Bot, User } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: string;
}

export interface ChatInterfaceAgent {
  id: string;
  name: string;
  description: string;
  agent_type: string;
  model_name?: string;
  system_prompt?: string;
}

interface ChatInterfaceProps {
  agent: ChatInterfaceAgent;
}

const getAgentIcon = (agentType: string) => {
  switch (agentType) {
    case 'research': return '🔬';
    case 'content': return '✍️';
    case 'analyst': return '📊';
    case 'planner': return '📋';
    case 'executor': return '⚙️';
    case 'memory': return '💾';
    default: return '🤖';
  }
};

const getAgentColor = (agentType: string) => {
  switch (agentType) {
    case 'research': return 'bg-blue-500/10 text-blue-600 border-blue-500/20';
    case 'content': return 'bg-purple-500/10 text-purple-600 border-purple-500/20';
    case 'analyst': return 'bg-green-500/10 text-green-600 border-green-500/20';
    case 'planner': return 'bg-amber-500/10 text-amber-600 border-amber-500/20';
    case 'executor': return 'bg-orange-500/10 text-orange-600 border-orange-500/20';
    case 'memory': return 'bg-cyan-500/10 text-cyan-600 border-cyan-500/20';
    default: return 'bg-primary/10 text-primary border-primary/20';
  }
};

const mockResponse = (userMessage: string, agentName: string): string => {
  const responses = [
    `I understand you're asking about "${userMessage.slice(0, 50)}${userMessage.length > 50 ? '...' : ''}". As ${agentName}, I'm here to help. In a production environment, this would connect to our AI backend for a full response.`,
    `Thank you for your message. The ${agentName} agent is ready to assist. This is a demo interface - connect your AI backend to enable real conversations.`,
    `Got it! I'll process that. [Demo mode: Responses are simulated. Integrate with your AI service for live chat.]`,
  ];
  return responses[Math.floor(Math.random() * responses.length)];
};

export const ChatInterface = ({ agent }: ChatInterfaceProps) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
  }, [agent.id]);

  useEffect(() => {
    const el = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]');
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, isTyping]);

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);

    const userMsg: Message = {
      id: `user-${Date.now()}`,
      content: userMessage,
      role: 'user',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    setIsTyping(true);
    await new Promise((r) => setTimeout(r, 800 + Math.random() * 400));
    setIsTyping(false);

    const aiMsg: Message = {
      id: `ai-${Date.now()}`,
      content: mockResponse(userMessage, agent.name),
      role: 'assistant',
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, aiMsg]);
    setIsLoading(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <Card className="h-full flex flex-col bg-card border-border">
      <CardHeader className="pb-4 border-b border-border">
        <motion.div
          className="flex items-center gap-4"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
        >
          <Avatar className="h-12 w-12 border-2 border-primary/20">
            <AvatarFallback className={`${getAgentColor(agent.agent_type)} text-xl font-semibold`}>
              {getAgentIcon(agent.agent_type)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-bold text-lg text-foreground">{agent.name}</h3>
              <Badge variant="secondary" className="text-xs font-medium">
                {agent.agent_type}
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{agent.description}</p>
          </div>
        </motion.div>
      </CardHeader>

      <CardContent className="flex-1 flex flex-col p-0 overflow-hidden">
        <ScrollArea className="flex-1 px-4 py-2" ref={scrollAreaRef}>
          <div className="space-y-4 py-2">
            <AnimatePresence mode="popLayout">
              {messages.map((message, index) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -20, scale: 0.95 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <Avatar className="h-8 w-8 mt-1 shrink-0">
                      <AvatarFallback className={`${getAgentColor(agent.agent_type)} text-sm border`}>
                        <Bot className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                  )}
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                      message.role === 'user'
                        ? 'bg-primary text-primary-foreground shadow-md'
                        : 'bg-muted text-foreground border border-border'
                    }`}
                  >
                    <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                      {message.content}
                    </p>
                    <div
                      className={`text-xs mt-2 ${message.role === 'user' ? 'opacity-80' : 'opacity-60'}`}
                    >
                      {new Date(message.timestamp).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </div>
                  </div>
                  {message.role === 'user' && (
                    <Avatar className="h-8 w-8 mt-1 shrink-0">
                      <AvatarFallback className="bg-secondary text-secondary-foreground text-sm border">
                        <User className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>

            {(isLoading || isTyping) && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                className="flex gap-3 justify-start"
              >
                <Avatar className="h-8 w-8 mt-1 shrink-0">
                  <AvatarFallback className={`${getAgentColor(agent.agent_type)} text-sm border`}>
                    <Bot className="h-4 w-4" />
                  </AvatarFallback>
                </Avatar>
                <div className="bg-muted rounded-2xl px-4 py-3 border border-border">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1">
                      {[0, 1, 2].map((i) => (
                        <motion.div
                          key={i}
                          className="w-2 h-2 bg-primary rounded-full"
                          animate={{ scale: [1, 1.2, 1] }}
                          transition={{ duration: 1, repeat: Infinity, delay: i * 0.2 }}
                        />
                      ))}
                    </div>
                    <span className="text-sm text-muted-foreground">{agent.name} is thinking...</span>
                  </div>
                </div>
              </motion.div>
            )}
          </div>
        </ScrollArea>

        <div className="p-4 border-t border-border">
          <div className="flex gap-3">
            <Input
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={`Ask ${agent.name} anything...`}
              className="flex-1"
              disabled={isLoading}
            />
            <Button
              onClick={sendMessage}
              disabled={!inputValue.trim() || isLoading}
              size="icon"
              className="shrink-0"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
