import { motion, useInView } from 'framer-motion';
import { useRef } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowRight, UserPlus, MessageSquare, Bot, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';

const steps = [
  { icon: UserPlus, title: 'Sign Up & Login', description: 'Create your account and access your personal AI agent dashboard instantly.', color: 'from-blue-500 to-cyan-500' },
  { icon: MessageSquare, title: 'Choose Your Agent', description: 'Select from specialized AI agents: Research, Content, Analysis, Automation, and more.', color: 'from-purple-500 to-pink-500' },
  { icon: Bot, title: 'Start Conversing', description: 'Begin chatting with your chosen agent. Ask questions, request tasks, and get intelligent responses.', color: 'from-green-500 to-emerald-500' },
  { icon: TrendingUp, title: 'Scale & Optimize', description: 'Switch between agents as needed, track your productivity, and let AI handle complex workflows.', color: 'from-orange-500 to-red-500' },
];

const HowItWorks = () => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: '-100px' });

  return (
    <section id="how-it-works" className="py-24 bg-background relative overflow-hidden">
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/2 w-96 h-96 bg-secondary/5 rounded-full blur-3xl -translate-x-1/2" />
        <div className="absolute bottom-0 right-1/4 w-80 h-80 bg-accent/5 rounded-full blur-3xl" />
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
            <span className="bg-gradient-to-r from-foreground to-secondary bg-clip-text text-transparent">Get Started in</span>
            <br />
            <span className="bg-secondary-gradient bg-clip-text text-transparent">Four Simple Steps</span>
          </h2>
          <p className="text-xl text-muted-foreground max-w-3xl mx-auto">
            Deploy your AI workforce in minutes. No technical expertise required.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
          {steps.map((step, index) => (
            <motion.div
              key={step.title}
              initial={{ opacity: 0, y: 30 }}
              animate={isInView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.8, delay: index * 0.15 }}
              className="relative"
            >
              <div className="flex justify-center mb-6">
                <div className="relative">
                  <div className={`w-20 h-20 rounded-full bg-gradient-to-br ${step.color} p-0.5 shadow-soft-lg flex items-center justify-center`}>
                    <step.icon className="w-8 h-8 text-white" />
                  </div>
                  <div className="absolute -top-2 -right-2 w-8 h-8 bg-primary rounded-full flex items-center justify-center text-sm font-bold text-primary-foreground">
                    {index + 1}
                  </div>
                </div>
              </div>
              <Card className="h-full bg-card/90 border-border hover:border-primary/30 hover:shadow-soft-lg transition-all text-center">
                <CardContent className="p-6">
                  <h3 className="text-xl font-bold mb-4">{step.title}</h3>
                  <p className="text-muted-foreground leading-relaxed text-sm">{step.description}</p>
                </CardContent>
              </Card>
              {index < steps.length - 1 && (
                <div className="hidden lg:block absolute top-12 -right-4 z-10">
                  <div className="w-8 h-8 bg-background border-2 border-primary/20 rounded-full flex items-center justify-center">
                    <ArrowRight className="w-4 h-4 text-primary" />
                  </div>
                </div>
              )}
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={isInView ? { opacity: 1, y: 0 } : {}}
          transition={{ duration: 0.8, delay: 0.8 }}
          className="text-center mt-20"
        >
          <div className="bg-card/80 border border-border rounded-2xl p-8 max-w-2xl mx-auto shadow-soft-lg">
            <h3 className="text-2xl font-bold mb-4">Ready to meet your AI workforce?</h3>
            <p className="text-muted-foreground mb-8">
              Join professionals using autonomous AI agents to boost productivity.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link to="/dashboard">
                <Button variant="modern" size="xl" className="group">
                  Go to Dashboard
                  <ArrowRight className="w-5 h-5 ml-1 group-hover:translate-x-1 transition-transform" />
                </Button>
              </Link>
              <Link to="/builder">
                <Button variant="soft" size="xl">
                  Try Agent Builder
                </Button>
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
};

export default HowItWorks;
