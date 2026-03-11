import AppNavbar from '@/components/AppNavbar';
import Hero from '@/components/Hero';
import Features from '@/components/Features';
import HowItWorks from '@/components/HowItWorks';
import Footer from '@/components/Footer';
import ChatbotWidget from '@/components/ChatbotWidget';

const Landing = () => {
  return (
    <div className="min-h-screen">
      <AppNavbar />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
      </main>
      <Footer />
      <ChatbotWidget />
    </div>
  );
};

export default Landing;
