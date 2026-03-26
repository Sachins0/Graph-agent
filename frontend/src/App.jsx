import { useState, useEffect, useRef, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'
import {
  Box,
  Paper,
  TextField,
  Button,
  Typography,
  Chip,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemText,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  CircularProgress,
  Grid,
  Tooltip,
  Switch,
  FormControlLabel,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from '@mui/material'
import {
  Send,
  Refresh,
  ExpandMore,
  Close,
  Search,
  Chat,
  Analytics,
  Settings,
  Visibility,
  VisibilityOff,
  ZoomIn,
  ZoomOut,
  CenterFocusStrong
} from '@mui/icons-material'
import './App.css'

const API_URL = 'http://localhost:8000'

const NODE_TYPES = {
  SalesOrderHeader: { color: '#1976d2', icon: '📋' },
  SalesOrderItem:   { color: '#42a5f5', icon: '📦' },
  DeliveryHeader:   { color: '#388e3c', icon: '🚚' },
  DeliveryItem:     { color: '#66bb6a', icon: '📦' },
  BillingItem:      { color: '#f57c00', icon: '💰' },
  JournalEntry:     { color: '#7b1fa2', icon: '📊' },
  Payment:          { color: '#c2185b', icon: '💳' },
  Customer:         { color: '#0097a7', icon: '👤' },
  Product:          { color: '#689f38', icon: '🏷️' }
}

function App() {
  const [graphData, setGraphData]                 = useState({ nodes: [], links: [] })
  const [filteredData, setFilteredData]           = useState({ nodes: [], links: [] })
  const [query, setQuery]                         = useState('')
  const [answer, setAnswer]                       = useState('')
  const [loading, setLoading]                     = useState(false)
  const [selectedNode, setSelectedNode]           = useState(null)
  const [nodeDetails, setNodeDetails]             = useState(null)
  const [drawerOpen, setDrawerOpen]               = useState(false)
  const [conversationHistory, setConversationHistory] = useState([])
  const [nodeFilter, setNodeFilter]               = useState({})
  const [relationshipFilter, setRelationshipFilter] = useState({})
  const [highlightMode, setHighlightMode]         = useState(false)
  const [metadataDialog, setMetadataDialog]       = useState(false)
  const [searchTerm, setSearchTerm]               = useState('')

  const fgRef = useRef()

  useEffect(() => {
    fetchGraph()
    fetchConversationHistory()
  }, [])

  useEffect(() => {
    applyFilters()
  }, [graphData, nodeFilter, relationshipFilter, searchTerm])

  const fetchGraph = async () => {
    setLoading(true)
    try {
      const res = await axios.get(`${API_URL}/graph/full`)
      const nodes = res.data.nodes.map(n => ({
        id:    n.id,
        name:  n.label,
        type:  n.type,
        ...n.properties,
        val:   getNodeSize(n.type),
        color: NODE_TYPES[n.type]?.color || '#999'
      }))
      const links = res.data.edges.map(e => ({
        source:       e.source,
        target:       e.target,
        relationship: e.relationship,
        value:        1
      }))
      setGraphData({ nodes, links })
    } catch (err) {
      console.error('Error fetching graph:', err)
      setAnswer('Error loading graph from backend')
    } finally {
      setLoading(false)
    }
  }

  const fetchConversationHistory = async () => {
    try {
      const res = await axios.get(`${API_URL}/conversation/history`)
      setConversationHistory(res.data.messages)
    } catch (err) {
      console.error('Error fetching history:', err)
    }
  }

  const getNodeSize = (type) => {
    const sizes = {
      SalesOrderHeader: 8,
      SalesOrderItem:   6,
      DeliveryHeader:   7,
      DeliveryItem:     5,
      BillingItem:      6,
      JournalEntry:     5,
      Payment:          6,
      Customer:         7,
      Product:          6
    }
    return sizes[type] || 5
  }

  const applyFilters = useCallback(() => {
    let filteredNodes = [...graphData.nodes]
    let filteredLinks = [...graphData.links]

    if (Object.values(nodeFilter).some(v => v)) {
      filteredNodes = filteredNodes.filter(node => nodeFilter[node.type])
    }

    if (Object.values(relationshipFilter).some(v => v)) {
      filteredLinks = filteredLinks.filter(link => relationshipFilter[link.relationship])
    }

    if (searchTerm) {
      const searchLower = searchTerm.toLowerCase()
      filteredNodes = filteredNodes.filter(node =>
        node.name?.toLowerCase().includes(searchLower) ||
        node.id?.toLowerCase().includes(searchLower)   ||
        node.type?.toLowerCase().includes(searchLower)
      )
      const nodeIds = new Set(filteredNodes.map(n => n.id))
      filteredLinks = filteredLinks.filter(link =>
        nodeIds.has(link.source) && nodeIds.has(link.target)
      )
    }

    setFilteredData({ nodes: filteredNodes, links: filteredLinks })
  }, [graphData, nodeFilter, relationshipFilter, searchTerm])

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      const res = await axios.post(`${API_URL}/query`, { prompt: query })
      setAnswer(res.data.answer ?? JSON.stringify(res.data, null, 2))
      fetchConversationHistory()
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
      setNodeDetails(res.data)
      setMetadataDialog(true)
    } catch (err) {
      setAnswer('Error loading node details')
    }
  }

  const handleNodeHover = (node) => {
    if (!highlightMode || !node) return
    const connectedNodeIds = new Set()
    const connectedLinks   = new Set()

    filteredData.links.forEach(link => {
      const srcId = link.source?.id ?? link.source
      const tgtId = link.target?.id ?? link.target
      if (srcId === node.id || tgtId === node.id) {
        connectedNodeIds.add(srcId)
        connectedNodeIds.add(tgtId)
        connectedLinks.add(link)
      }
    })
  }

  const handleZoomIn  = () => fgRef.current?.zoom(fgRef.current.zoom() * 1.2, 200)
  const handleZoomOut = () => fgRef.current?.zoom(fgRef.current.zoom() * 0.8, 200)
  const handleCenter  = () => { fgRef.current?.centerAt(0, 0, 1000); fgRef.current?.zoom(1, 1000) }

  const toggleFilter = (type, filterType) => {
    if (filterType === 'node') {
      setNodeFilter(prev => ({ ...prev, [type]: !prev[type] }))
    } else {
      setRelationshipFilter(prev => ({ ...prev, [type]: !prev[type] }))
    }
  }

  const uniqueNodeTypes      = [...new Set(graphData.nodes.map(n => n.type))]
  const uniqueRelationships  = [...new Set(graphData.links.map(l => l.relationship))]

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#f5f5f5' }}>

      {/* ── Graph Area ─────────────────────────────────────────── */}
      <Box sx={{ flex: 2, position: 'relative', bgcolor: '#ffffff' }}>

        {/* Controls */}
        <Box sx={{ position: 'absolute', top: 16, left: 16, zIndex: 10, display: 'flex', gap: 1 }}>
          <Tooltip title="Refresh Graph">
            <IconButton onClick={fetchGraph} disabled={loading} sx={{ bgcolor: 'rgba(255,255,255,0.9)' }}>
              <Refresh />
            </IconButton>
          </Tooltip>
          <Tooltip title="Center Graph">
            <IconButton onClick={handleCenter} sx={{ bgcolor: 'rgba(255,255,255,0.9)' }}>
              <CenterFocusStrong />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom In">
            <IconButton onClick={handleZoomIn} sx={{ bgcolor: 'rgba(255,255,255,0.9)' }}>
              <ZoomIn />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom Out">
            <IconButton onClick={handleZoomOut} sx={{ bgcolor: 'rgba(255,255,255,0.9)' }}>
              <ZoomOut />
            </IconButton>
          </Tooltip>
          <Tooltip title="Toggle Highlight Mode">
            <IconButton
              onClick={() => setHighlightMode(!highlightMode)}
              sx={{ bgcolor: highlightMode ? 'primary.main' : 'rgba(255,255,255,0.9)', color: highlightMode ? 'white' : 'inherit' }}
            >
              {highlightMode ? <Visibility /> : <VisibilityOff />}
            </IconButton>
          </Tooltip>
        </Box>

        {/* Stats badge */}
        <Box sx={{ position: 'absolute', top: 16, right: 16, zIndex: 10 }}>
          <Paper sx={{ p: 1, bgcolor: 'rgba(255,255,255,0.9)' }}>
            <Typography variant="caption">
              Nodes: {filteredData.nodes.length} | Links: {filteredData.links.length}
            </Typography>
          </Paper>
        </Box>

        {/* Force Graph */}
        {filteredData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={filteredData}
            nodeLabel={node => `${NODE_TYPES[node.type]?.icon || '📄'} ${node.name}\n(${node.type})`}
            nodeVal={node => node.val}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={link => link.relationship}
            linkColor={() => '#999'}
            linkWidth={2}
            nodeCanvasObject={(node, ctx, globalScale) => {
              const fontSize = Math.max(12 / globalScale, 4)
              ctx.font = `${fontSize}px Sans-Serif`

              // Draw circle
              ctx.beginPath()
              ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI)
              ctx.fillStyle = node.color
              ctx.fill()
              ctx.strokeStyle = '#fff'
              ctx.lineWidth = 2
              ctx.stroke()

              // Draw label background
              const label         = node.name || node.id
              const textWidth     = ctx.measureText(label).width
              const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2)
              ctx.fillStyle = 'rgba(255,255,255,0.9)'
              ctx.fillRect(
                node.x - bckgDimensions[0] / 2,
                node.y - bckgDimensions[1] / 2,
                ...bckgDimensions
              )

              // Draw label text
              ctx.textAlign    = 'center'
              ctx.textBaseline = 'middle'
              ctx.fillStyle    = '#000'
              ctx.fillText(label, node.x, node.y)
            }}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
          />
        ) : (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#999' }}>
            {loading ? <CircularProgress /> : (
              <>
                <Analytics sx={{ fontSize: 48, mb: 2 }} />
                <Typography variant="h6">No graph data</Typography>
                <Button onClick={fetchGraph} startIcon={<Refresh />}>Load Graph</Button>
              </>
            )}
          </Box>
        )}
      </Box>

      {/* ── Sidebar ────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', borderLeft: 1, borderColor: 'divider' }}>

        {/* Query input */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Chat /> SAP O2C Assistant
          </Typography>
          <TextField
            fullWidth multiline rows={3}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() } }}
            placeholder="Ask about sales orders, deliveries, billing, payments..."
            variant="outlined" size="small" sx={{ mb: 1 }}
          />
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              fullWidth variant="contained"
              onClick={handleQuery}
              disabled={loading || !query.trim()}
              startIcon={loading ? <CircularProgress size={16} /> : <Send />}
            >
              {loading ? 'Processing...' : 'Ask'}
            </Button>
            <IconButton onClick={() => setDrawerOpen(true)}><Settings /></IconButton>
          </Box>
        </Box>

        {/* Filters */}
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Filters</Typography>
          <TextField
            fullWidth size="small" placeholder="Search nodes..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            InputProps={{ startAdornment: <Search sx={{ mr: 1, color: 'action.active' }} /> }}
            sx={{ mb: 2 }}
          />
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="body2">Node Types ({uniqueNodeTypes.length})</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 1 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {uniqueNodeTypes.map(type => (
                  <Chip
                    key={type}
                    label={`${NODE_TYPES[type]?.icon || '📄'} ${type}`}
                    size="small"
                    variant={nodeFilter[type] ? 'filled' : 'outlined'}
                    onClick={() => toggleFilter(type, 'node')}
                    sx={{ bgcolor: nodeFilter[type] ? NODE_TYPES[type]?.color : 'transparent', color: nodeFilter[type] ? 'white' : 'inherit' }}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMore />}>
              <Typography variant="body2">Relationships ({uniqueRelationships.length})</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 1 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {uniqueRelationships.map(rel => (
                  <Chip
                    key={rel} label={rel} size="small"
                    variant={relationshipFilter[rel] ? 'filled' : 'outlined'}
                    onClick={() => toggleFilter(rel, 'relationship')}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
        </Box>

        {/* Results */}
        <Box sx={{ flex: 1, p: 2, overflow: 'auto' }}>
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Results</Typography>
          {answer && (
            <Paper sx={{ p: 2, mb: 2, maxHeight: 300, overflow: 'auto' }}>
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.75rem' }}>
                {answer}
              </Typography>
            </Paper>
          )}
          {conversationHistory.length > 0 && (
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="body2">Conversation History ({conversationHistory.length})</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ p: 1 }}>
                <List dense>
                  {conversationHistory.slice(-5).map((msg, idx) => (
                    <ListItem key={idx} sx={{ px: 0 }}>
                      <ListItemText
                        primary={msg.query}
                        secondary={msg.timestamp}
                        primaryTypographyProps={{ variant: 'body2' }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItem>
                  ))}
                </List>
              </AccordionDetails>
            </Accordion>
          )}
        </Box>
      </Box>

      {/* ── Settings Drawer ────────────────────────────────────── */}
      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <Box sx={{ width: 300, p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">Settings</Typography>
            <IconButton onClick={() => setDrawerOpen(false)}><Close /></IconButton>
          </Box>
          <FormControlLabel
            control={<Switch checked={highlightMode} onChange={e => setHighlightMode(e.target.checked)} />}
            label="Highlight Mode"
          />
          <Divider sx={{ my: 2 }} />
          <Typography variant="subtitle2" sx={{ mb: 1 }}>Graph Statistics</Typography>
          <Typography variant="body2">Total Nodes: {graphData.nodes.length}</Typography>
          <Typography variant="body2">Total Links: {graphData.links.length}</Typography>
          <Typography variant="body2">Node Types: {uniqueNodeTypes.length}</Typography>
          <Typography variant="body2">Relationship Types: {uniqueRelationships.length}</Typography>
        </Box>
      </Drawer>

      {/* ── Node Metadata Dialog ───────────────────────────────── */}
      <Dialog open={metadataDialog} onClose={() => setMetadataDialog(false)} maxWidth="md" fullWidth>
        <DialogTitle>
          {selectedNode && `${NODE_TYPES[selectedNode.type]?.icon || '📄'} ${selectedNode.name}`}
        </DialogTitle>
        <DialogContent>
          {nodeDetails && (
            <Grid container spacing={2} sx={{ mt: 0 }}>
              {Object.entries(nodeDetails).map(([key, value]) => (
                <Grid item xs={6} key={key}>
                  <Paper sx={{ p: 1 }}>
                    <Typography variant="caption" color="text.secondary">{key}</Typography>
                    <Typography variant="body2">{String(value)}</Typography>
                  </Paper>
                </Grid>
              ))}
            </Grid>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setMetadataDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

    </Box>
  )
}

export default App
