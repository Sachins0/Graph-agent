import { useState } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'

function App() {
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState('')

  const handleQuery = async () => {
    try {
      const res = await axios.post('/api/query', { prompt: query })
      setAnswer(res.data.answer ?? JSON.stringify(res.data))
    } catch (err) {
      console.error(err)
      setAnswer('Error querying backend')
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', height: '100vh' }}>
      <div style={{ borderRight: '1px solid #ddd' }}>
        <h3>O2C Graph Visualization</h3>
        <ForceGraph2D
          graphData={{ nodes, links }}
          nodeLabel={node => `${node.id} (${node.type})`}
          nodeAutoColorBy='type'
          linkDirectionalArrowLength={4}
          linkDirectionalArrowRelPos={1}
        />
      </div>
      <div style={{ padding: '1rem' }}>
        <h3>NL Query</h3>
        <textarea value={query} onChange={e => setQuery(e.target.value)} rows={6} style={{ width: '100%' }} />
        <button onClick={handleQuery} style={{ marginTop: 10 }}>Ask</button>
        <h4>Answer</h4>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{answer}</pre>
      </div>
    </div>
  )
}

export default App
