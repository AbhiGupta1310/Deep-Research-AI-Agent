import { useState } from 'react';
import { Download, Search, Loader2 } from 'lucide-react';
import './App.css';

function App() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [reportUrl, setReportUrl] = useState(null);
  const [error, setError] = useState(null);
  const [statusMessage, setStatusMessage] = useState('Thinking...');

  const handleResearch = async () => {
    if (!topic.trim()) return;

    setLoading(true);
    setError(null);
    setReportUrl(null);
    setStatusMessage('Initializing research...');
    
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

    try {
      const response = await fetch(`${API_URL}/api/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ topic: topic }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        
        if (done) break;
        
        const text = decoder.decode(value, { stream: true });
        buffer += text;
        
        const lines = buffer.split('\n');
        // Process all complete lines
        buffer = lines.pop() || ''; // Keep the last incomplete line in buffer
        
        for (const line of lines) {
          if (!line.trim()) continue;
          
          try {
            const data = JSON.parse(line);
            console.log('Stream data:', data);
            
            if (data.status === 'started') {
              setStatusMessage('Research functionality initialized...');
            } else if (data.status === 'progress') {
              setStatusMessage(`Working on: ${data.data}`);
            } else if (data.status === 'completed') {
              setReportUrl(`${API_URL}${data.report_url}`);
              setLoading(false);
            } else if (data.status === 'error') {
              throw new Error(data.message);
            }
          } catch (e) {
            console.error('Error parsing JSON from stream:', e);
            // Don't throw here, just log invalid JSON and continue
          }
        }
      }

    } catch (err) {
      console.error(err);
      setError(`Error: ${err.message}`);
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (reportUrl) {
      window.open(reportUrl, '_blank');
    }
  };

  return (
    <div className="container">
      <header className="header">
        <h1>Deep Research Agent</h1>
        <p>Discover deep insights with AI-powered research.</p>
      </header>

      <div className="card">
        <div className="input-group">
          <input
            type="text"
            placeholder="What would you like to research?"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleResearch()}
          />
          <button onClick={handleResearch} disabled={loading}>
            {loading ? <Loader2 className="spinner" /> : <Search size={20} />}
            {loading ? 'Thinking...' : 'Research'}
          </button>
        </div>
      </div>
      
      {error && (
        <div style={{ color: '#ef4444', fontWeight: '500', marginTop: '1rem', textAlign: 'center' }}>
          {error}
        </div>
      )}

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
          <p>{statusMessage}</p>
        </div>
      )}

      {reportUrl && (
        <div className="pdf-viewer-container">
          <div className="pdf-header">
            <h2><Search size={18} /> Research Report: {topic}</h2>
            <a href={reportUrl} target="_blank" rel="noopener noreferrer" className="download-link">
              <Download size={18} /> Download PDF
            </a>
          </div>
          
          <div className="pdf-viewer">
            <iframe src={reportUrl} title="Research Report"></iframe>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
