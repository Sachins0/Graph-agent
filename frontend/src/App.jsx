import { useState, useEffect, useRef } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'

const API_URL = 'http://localhost:8000'

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [query, setQuery] = useState('')
  const [answer, setAnswer] = useState('')
  const [loading, setLoading] = useState(false)
  const [selectedNode, setSelectedNode] = useState(null)
  const fgRef = useRef()

  useEffect(() => {
    fetchGraph()
  }, [])

  const fetchGraph = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_URL}/graph/full`)
      // Transform nodes and edges for react-force-graph
      const nodes = res.data.nodes.map(n => ({
        id: n.id,
        name: n.label,
        type: n.type,
        ...n.properties
      }))

      const links = res.data.edges.map(e => ({
        source: e.source,
        target: e.target,
        relationship: e.relationship
      }))

      setGraphData({ nodes, links })
    } catch (err) {
      console.error('Error fetching graph:', err)
      setAnswer('Error loading graph from backend')
    } finally {
      setLoading(false)
    }
  }

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await axios.post(`${API_URL}/query`, { prompt: query })
      setAnswer(res.data.answer ?? JSON.stringify(res.data, null, 2))
    } catch (err) {
      console.error('Error querying backend:', err)
      setAnswer('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const handleNodeClick = async (node) => {
    setSelectedNode(node)
    try {
      const res = await axios.get(`${API_URL}/graph/entity/${node.id}`)
      setAnswer(JSON.stringify(res.data, null, 2))
    } catch (err) {
      setAnswer('Error loading node details')
    }
  }

  const handleRefreshGraph = () => {
    setLoading(true)
    fetchGraph()
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', height: '100vh', fontFamily: 'system-ui' }}>
      <div style={{ borderRight: '1px solid #ddd', position: 'relative', backgroundColor: '#f5f5f5' }}>
        <div style={{ position: 'absolute', top: 10, left: 10, zIndex: 10 }}>
          <button onClick={handleRefreshGraph} disabled={loading} style={{ padding: '8px 16px', cursor: 'pointer' }}>
            {loading ? 'Loading...' : 'Refresh Graph'}
          </button>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            Nodes: {graphData.nodes.length} | Links: {graphData.links.length}
          </div>
        </div>
        {graphData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={graphData}
            nodeLabel={node => `${node.name} (${node.type})`}
            nodeAutoColorBy='type'
            onNodeClick={handleNodeClick}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={link => link.relationship}
            nodeCanvasObject={(node, ctx) => {
              const label = node.name
              const fontSize = 12
              ctx.font = `${fontSize}px Sans-Serif`
              const textWidth = ctx.measureText(label).width
              const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2)

              ctx.fillStyle = 'rgba(255, 255, 255, 0.8)'
              ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y - bckgDimensions[1] / 2, ...bckgDimensions)

              ctx.textAlign = 'center'
              ctx.textBaseline = 'middle'
              ctx.fillStyle = '#000'
              ctx.fillText(label, node.x, node.y)

              return false
            }}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
            {loading ? 'Loading graph...' : 'No graph data. Click Refresh.'}
          </div>
        )}
      </div>

      <div style={{ padding: '1rem', overflowY: 'auto', backgroundColor: '#fafafa' }}>
        <h3 style={{ marginTop: 0 }}>🔍 Search & Query</h3>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleQuery()
            }
          }}
          placeholder="Ask a question about O2C data... (e.g., 'Which products are associated with the highest number of billing documents?')"
          rows={6}
          style={{ width: '100%', padding: '8px', fontFamily: 'monospace', fontSize: '12px', border: '1px solid #ddd' }}
        />
        <button
          onClick={handleQuery}
          disabled={loading || !query.trim()}
          style={{
            marginTop: 10,
            padding: '8px 16px',
            cursor: loading || !query.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !query.trim() ? 0.5 : 1
          }}
        >
          {loading ? 'Asking...' : 'Ask'}
        </button>

        {selectedNode && (
          <div style={{ marginTop: '1rem', padding: '8px', backgroundColor: '#e3f2fd', borderRadius: '4px', fontSize: '12px' }}>
            <strong>Selected:</strong> {selectedNode.name}
          </div>
        )}

        <h4>📊 Answer</h4>
        <pre
          style={{
            backgroundColor: '#fff',
            border: '1px solid #ddd',
            borderRadius: '4px',
            padding: '8px',
            fontSize: '11px',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
            maxHeight: '300px',
            overflowY: 'auto',
            margin: 0
          }}
        >
          {answer || '(Query results will appear here)'}
        </pre>
      </div>
    </div>
  )
}

export default App
