import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Settings as SettingsIcon, Database, Save } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { toast } from '@/hooks/use-toast';
import { getApiConfig, saveApiConfig, loadApiConfig } from '@/lib/api/client';

const Settings = () => {
  // Default = BACKEND mode (IMPORTANT FIX)
  const [useMockData, setUseMockData] = useState(false);
  const [backendUrl, setBackendUrl] = useState('');

  useEffect(() => {
    // Load config from localStorage
    const config = loadApiConfig();

    setUseMockData(config.useMockData ?? false); // default = backend
    setBackendUrl(config.baseURL || 'http://localhost:8000/api/v1');
  }, []);

  const handleSave = () => {
    saveApiConfig(useMockData, backendUrl);

    toast({
      title: 'Settings Saved',
      description: 'Your configuration has been updated. Refresh to apply changes.',
    });
  };

  const currentConfig = getApiConfig();

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Settings</h1>
          <p className="text-muted-foreground mt-1">Configure your AMAS dashboard</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Backend Configuration
            </CardTitle>
            <CardDescription>
              Toggle between mock data and real FastAPI backend connection
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">

            {/* TOGGLE */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div className="space-y-0.5">
                <Label htmlFor="mock-mode" className="text-base">Use Mock Data</Label>
                <p className="text-sm text-muted-foreground">
                  Enable this to simulate data without connecting to backend
                </p>
              </div>
              <Switch
                id="mock-mode"
                checked={useMockData}
                onCheckedChange={setUseMockData}
              />
            </div>

            {/* Only show backend URL when mock is OFF */}
            {!useMockData && (
              <div className="space-y-2">
                <Label htmlFor="backend-url">Backend API URL</Label>
                <Input
                  id="backend-url"
                  placeholder="http://localhost:8000/api/v1"
                  value={backendUrl}
                  onChange={(e) => setBackendUrl(e.target.value)}
                />
                <p className="text-xs text-muted-foreground">
                  Example: http://localhost:8000/api/v1
                </p>
              </div>
            )}

            {/* CURRENT CONFIG DISPLAY */}
            <div className="p-4 bg-muted rounded-lg space-y-2">
              <p className="text-sm font-medium">Current Configuration</p>
              <div className="text-sm text-muted-foreground space-y-1">
                <p>Mode: <span className="font-medium text-foreground">
                  {currentConfig.useMockData ? 'Mock Data' : 'Real Backend'}
                </span></p>

                {!currentConfig.useMockData && (
                  <p>Backend URL: <span className="font-mono text-xs text-foreground">
                    {currentConfig.baseURL}
                  </span></p>
                )}
              </div>
            </div>

            <Button onClick={handleSave}>
              <Save className="h-4 w-4 mr-2" />
              Save Settings
            </Button>

          </CardContent>
        </Card>

        {/* INSTRUCTIONS CARD (same as your code) */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <SettingsIcon className="h-5 w-5" />
              Integration Instructions
            </CardTitle>
            <CardDescription>
              How to connect to your FastAPI backend
            </CardDescription>
          </CardHeader>

          <CardContent className="space-y-4 text-sm">
            {/* Your original instructions remain unchanged */}
            <div>
              <h3 className="font-semibold mb-2">1. Ensure your backend is running</h3>
              <pre className="bg-muted p-3 rounded text-xs overflow-x-auto">
                docker compose up --build
              </pre>
            </div>

            <div>
              <h3 className="font-semibold mb-2">2. Configure CORS</h3>
              <p className="text-muted-foreground">Add CORS to FastAPI:</p>
              <pre className="bg-muted p-3 rounded text-xs overflow-x-auto mt-2">
{`from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)`}
              </pre>
            </div>

            <div>
              <h3 className="font-semibold mb-2">3. Expected Endpoints</h3>
              <ul className="list-disc list-inside text-muted-foreground space-y-1">
                <li>GET /agents</li>
                <li>GET /agents/{'{id}'}</li>
                <li>POST /agents/{'{id}'}/start</li>
                <li>POST /agents/{'{id}'}/stop</li>
                <li>GET /tasks</li>
                <li>GET /tasks/{'{id}'}</li>
                <li>POST /tasks</li>
                <li>GET /tasks/{'{id}'}/logs</li>
                <li>POST /memory/search</li>
                <li>GET /metrics</li>
              </ul>
            </div>
          </CardContent>

        </Card>
      </div>
    </DashboardLayout>
  );
};

export default Settings;
