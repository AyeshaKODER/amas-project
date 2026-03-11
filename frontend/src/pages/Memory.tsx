import { useState } from 'react';
import { apiClient } from '@/lib/api/client';
import { MemoryEntry } from '@/lib/api/types';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Database, ExternalLink } from 'lucide-react';
import DashboardLayout from '@/components/DashboardLayout';
import { toast } from '@/hooks/use-toast';

const Memory = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MemoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setSearched(true);
    try {
      const data = await apiClient.searchMemory(query);
      setResults(data);
      if (data.length === 0) {
        toast({
          title: 'No Results',
          description: 'No matching memory entries found'
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to search memory',
        variant: 'destructive'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">Memory Explorer</h1>
          <p className="text-muted-foreground mt-1">Search and explore agent memory (vector database)</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-5 w-5" />
              Vector Search
            </CardTitle>
            <CardDescription>
              Search through stored memories using semantic similarity
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSearch} className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search memory entries..."
                  className="pl-10"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
              </div>
              <Button type="submit" disabled={loading}>
                {loading ? 'Searching...' : 'Search'}
              </Button>
            </form>
          </CardContent>
        </Card>

        {searched && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                {results.length} {results.length === 1 ? 'Result' : 'Results'}
              </h2>
            </div>

            {results.length === 0 ? (
              <Card>
                <CardContent className="p-12 text-center">
                  <p className="text-muted-foreground">
                    No matching entries found. Try a different search query.
                  </p>
                </CardContent>
              </Card>
            ) : (
              results.map(entry => (
                <Card key={entry.id} className="card-hover">
                  <CardContent className="p-6 space-y-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <p className="text-sm leading-relaxed">{entry.content}</p>
                      </div>
                      {entry.score && (
                        <div className="flex items-center gap-2 px-3 py-1 bg-primary-light rounded-full">
                          <span className="text-xs font-medium text-primary">
                            {(entry.score * 100).toFixed(0)}% match
                          </span>
                        </div>
                      )}
                    </div>

                    {entry.tags && entry.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {entry.tags.map(tag => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-3 border-t border-border">
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        {entry.agent_id && (
                          <span>Agent: {entry.agent_id}</span>
                        )}
                        <span>
                          {new Date(entry.timestamp).toLocaleDateString()}
                        </span>
                        {entry.metadata?.category && (
                          <span className="capitalize">
                            {entry.metadata.category}
                          </span>
                        )}
                      </div>
                      
                      {entry.metadata?.url && (
                        <a 
                          href={entry.metadata.url} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <ExternalLink className="h-3 w-3" />
                          Source
                        </a>
                      )}
                    </div>

                    {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                      <details className="text-xs">
                        <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
                          View metadata
                        </summary>
                        <pre className="mt-2 p-3 bg-muted rounded text-xs overflow-x-auto">
                          {JSON.stringify(entry.metadata, null, 2)}
                        </pre>
                      </details>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
};

export default Memory;