import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Bot, Brain, Zap, Shield, BarChart3, MessageSquare } from 'lucide-react';

const features = [
  { icon: Bot, title: 'Specialized Agents', description: 'Research, Content, Analysis, Automation, and more - each optimized for specific tasks.', gradient: 'from-blue-500 to-cyan-500' },
  { icon: Brain, title: 'Advanced AI Models', description: 'Powered by state-of-the-art language models with domain-specific training.', gradient: 'from-purple-500 to-pink-500' },
  { icon: MessageSquare, title: 'Natural Conversations', description: 'Engage with agents through intuitive chat interfaces with context-aware responses.', gradient: 'from-green-500 to-emerald-500' },
  { icon: Zap, title: 'Instant Responses', description: 'Get immediate feedback and results with optimized processing.', gradient: 'from-orange-500 to-red-500' },
  { icon: Shield, title: 'Enterprise Security', description: 'Secure data handling and compliance with industry standards.', gradient: 'from-indigo-500 to-blue-500' },
  { icon: BarChart3, title: 'Performance Analytics', description: 'Track agent usage, measure productivity gains, and optimize workflows.', gradient: 'from-teal-500 to-cyan-500' },
];

const Features = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="features" className="py-24 bg-subtle-gradient relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-1/4 left-0 w-96 h-96 bg-primary/5 rounded-full blur-3xl -translate-x-1/2" />
        <div className="absolute bottom-1/4 right-0 w-80 h-80 bg-secondary/5 rounded-full blur-3xl translate-x-1/2" />
      </div>

      <div className="container mx-auto px-4 relative z-10">
        <motion.div
          ref={ref}
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl md:text-5xl font-bold mb-6">
            <span className="bg-gradient-to-r from-foreground to-primary bg-clip-text text-transparent">Enterprise-Grade</span>
            <br />
            <span className="bg-primary-gradient bg-clip-text text-transparent">AI Capabilities</span>
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Everything you need to deploy, manage, and scale autonomous AI agents in your organization.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {features.map((feature, index) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.8, delay: index * 0.1 }}
            >
              <Card className="h-full bg-card/90 border-border hover:border-primary/30 hover:shadow-soft-lg transition-all">
                <CardHeader className="pb-4">
                  <div className={`inline-flex p-4 rounded-2xl bg-gradient-to-br ${feature.gradient} mb-4 shadow-soft`}>
                    <feature.icon className="w-8 h-8 text-white" />
                  </div>
                  <CardTitle className="text-xl font-bold">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-muted-foreground leading-relaxed">
                    {feature.description}
                  </CardDescription>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Features;
