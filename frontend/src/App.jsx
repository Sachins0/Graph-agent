import { useState, useEffect, useRef, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'
import {
  Box, Paper, TextField, Button, Typography, Chip,
  IconButton, Drawer, List, ListItem, ListItemText,
  Divider, Accordion, AccordionSummary, AccordionDetails,
  CircularProgress, Grid, Tooltip, Switch, FormControlLabel,
  Dialog, DialogTitle, DialogContent, DialogActions, Badge, Alert
} from '@mui/material'
import {
  Send, Refresh, ExpandMore, Close, Search, Chat,
  Analytics, Settings, Visibility, VisibilityOff,
  ZoomIn, ZoomOut, CenterFocusStrong, Timeline, BarChart
} from '@mui/icons-material'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// ── All node types including BillingHeader (was missing before) ───
const NODE_TYPES = {
  SalesOrderHeader: { color: '#1976d2', icon: '📋' },
  SalesOrderItem:   { color: '#42a5f5', icon: '📦' },
  DeliveryHeader:   { color: '#388e3c', icon: '🚚' },
  DeliveryItem:     { color: '#66bb6a', icon: '📦' },
  BillingHeader:    { color: '#f57c00', icon: '🧾' },   // ← was missing
  BillingItem:      { color: '#ffa726', icon: '💰' },
  JournalEntry:     { color: '#7b1fa2', icon: '📊' },
  Payment:          { color: '#c2185b', icon: '💳' },
  Customer:         { color: '#0097a7', icon: '👤' },
  Product:          { color: '#689f38', icon: '🏷️' },
}

const NODE_SIZES = {
  SalesOrderHeader: 8, SalesOrderItem: 6,
  DeliveryHeader: 7,   DeliveryItem: 5,
  BillingHeader: 7,    BillingItem: 6,
  JournalEntry: 5,     Payment: 6,
  Customer: 8,         Product: 5,
}

function App() {
  const [graphData, setGraphData]               = useState({ nodes: [], links: [] })
  const [filteredData, setFilteredData]         = useState({ nodes: [], links: [] })
  const [query, setQuery]                       = useState('')
  const [answer, setAnswer]                     = useState('')
  const [sqlQuery, setSqlQuery]                 = useState('')
  const [loading, setLoading]                   = useState(false)
  const [selectedNode, setSelectedNode]         = useState(null)
  const [nodeDetails, setNodeDetails]           = useState(null)
  const [drawerOpen, setDrawerOpen]             = useState(false)
  const [conversationHistory, setConversationHistory] = useState([])
  const [nodeFilter, setNodeFilter]             = useState({})
  const [relationshipFilter, setRelationshipFilter] = useState({})
  const [highlightMode, setHighlightMode]       = useState(false)
  const [metadataDialog, setMetadataDialog]     = useState(false)
  const [traceDialog, setTraceDialog]           = useState(false)
  const [traceData, setTraceData]               = useState(null)
  const [traceLoading, setTraceLoading]         = useState(false)
  const [searchTerm, setSearchTerm]             = useState('')
  const [graphStats, setGraphStats]             = useState(null)
  const [showSql, setShowSql]                   = useState(false)
  const [errorMsg, setErrorMsg]                 = useState('')

  // Set of node IDs to visually highlight (from hover OR query results)
  const [highlightedNodes, setHighlightedNodes] = useState(new Set())
  const [highlightedLinks, setHighlightedLinks] = useState(new Set())

  const fgRef = useRef()

  useEffect(() => {
    fetchGraph()
    fetchConversationHistory()
  }, [])

  useEffect(() => {
    applyFilters()
  }, [graphData, nodeFilter, relationshipFilter, searchTerm])

  // ── Data fetching ─────────────────────────────────────────────

  const fetchGraph = async () => {
    setLoading(true)
    setErrorMsg('')
    try {
      const res = await axios.get(`${API_URL}/graph/full`)
      const nodes = res.data.nodes.map(n => ({
        id:    n.id,
        name:  n.label,
        type:  n.type,
        ...n.properties,
        val:   NODE_SIZES[n.type] || 5,
        color: NODE_TYPES[n.type]?.color || '#999',
      }))
      const links = res.data.edges.map(e => ({
        source:       e.source,
        target:       e.target,
        relationship: e.relationship,
      }))
      setGraphData({ nodes, links })
    } catch (err) {
      setErrorMsg('Error loading graph from backend. Is the server running?')
    } finally {
      setLoading(false)
    }
  }

  const fetchConversationHistory = async () => {
    try {
      const res = await axios.get(`${API_URL}/conversation/history`)
      setConversationHistory(res.data.messages || [])
    } catch { /* silent */ }
  }

  const fetchGraphStats = async () => {
    try {
      const res = await axios.get(`${API_URL}/graph/stats`)
      setGraphStats(res.data)
    } catch { /* silent */ }
  }

  // ── Filters ───────────────────────────────────────────────────

  const applyFilters = useCallback(() => {
    let nodes = [...graphData.nodes]
    let links = [...graphData.links]

    if (Object.values(nodeFilter).some(Boolean)) {
      nodes = nodes.filter(n => nodeFilter[n.type])
    }
    if (Object.values(relationshipFilter).some(Boolean)) {
      links = links.filter(l => relationshipFilter[l.relationship])
    }
    if (searchTerm) {
      const s = searchTerm.toLowerCase()
      nodes = nodes.filter(n =>
        n.name?.toLowerCase().includes(s) ||
        n.id?.toLowerCase().includes(s)   ||
        n.type?.toLowerCase().includes(s)
      )
      const nodeIds = new Set(nodes.map(n => n.id))
      links = links.filter(l =>
        nodeIds.has(typeof l.source === 'object' ? l.source.id : l.source) &&
        nodeIds.has(typeof l.target === 'object' ? l.target.id : l.target)
      )
    }
    setFilteredData({ nodes, links })
  }, [graphData, nodeFilter, relationshipFilter, searchTerm])

  // ── Query ─────────────────────────────────────────────────────

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true)
    setErrorMsg('')
    setSqlQuery('')
    try {
      const res = await axios.post(`${API_URL}/query`, { prompt: query })

      if (res.data.blocked) {
        setAnswer(res.data.answer || res.data.error)
        setErrorMsg(res.data.hint || '')
        return
      }

      setAnswer(res.data.answer ?? JSON.stringify(res.data, null, 2))
      if (res.data.sql) setSqlQuery(res.data.sql)

      // ── Wire highlight_ids from backend → graph highlight ────
      if (res.data.highlight_ids?.length) {
        const ids = new Set(res.data.highlight_ids)
        setHighlightedNodes(ids)
        // Also highlight edges connected to these nodes
        const hLinks = new Set()
        filteredData.links.forEach(l => {
          const src = typeof l.source === 'object' ? l.source.id : l.source
          const tgt = typeof l.target === 'object' ? l.target.id : l.target
          if (ids.has(src) || ids.has(tgt)) hLinks.add(l)
        })
        setHighlightedLinks(hLinks)
        // Auto-center on first highlighted node
        const firstNode = filteredData.nodes.find(n => ids.has(n.id))
        if (firstNode?.x != null) {
          fgRef.current?.centerAt(firstNode.x, firstNode.y, 800)
          fgRef.current?.zoom(2.5, 800)
        }
      } else {
        setHighlightedNodes(new Set())
        setHighlightedLinks(new Set())
      }

      fetchConversationHistory()
    } catch (err) {
      setErrorMsg('Error: ' + (err.response?.data?.detail || err.message))
    } finally {
      setLoading(false)
    }
  }

  const clearHighlights = () => {
    setHighlightedNodes(new Set())
    setHighlightedLinks(new Set())
  }

  // ── Node interaction ──────────────────────────────────────────

  const handleNodeClick = async (node) => {
    setSelectedNode(node)
    setNodeDetails(null)
    try {
      const res = await axios.get(`${API_URL}/graph/entity/${encodeURIComponent(node.id)}`)
      setNodeDetails(res.data)
      setMetadataDialog(true)
    } catch {
      setErrorMsg('Error loading node details')
    }
  }

  const handleNodeHover = useCallback((node) => {
    if (!highlightMode) return

    if (!node) {
      // Clear hover highlights (but keep query highlights)
      setHighlightedNodes(new Set())
      setHighlightedLinks(new Set())
      return
    }

    const connectedNodeIds = new Set([node.id])
    const connectedLinks   = new Set()

    filteredData.links.forEach(link => {
      const srcId = typeof link.source === 'object' ? link.source.id : link.source
      const tgtId = typeof link.target === 'object' ? link.target.id : link.target
      if (srcId === node.id || tgtId === node.id) {
        connectedNodeIds.add(srcId)
        connectedNodeIds.add(tgtId)
        connectedLinks.add(link)
      }
    })

    setHighlightedNodes(connectedNodeIds)
    setHighlightedLinks(connectedLinks)
  }, [highlightMode, filteredData.links])

  // ── Trace O2C flow ────────────────────────────────────────────

  const handleTraceFlow = async (billingDoc) => {
    setTraceLoading(true)
    try {
      const res = await axios.get(`${API_URL}/graph/trace/${billingDoc}`)
      setTraceData(res.data)
      setMetadataDialog(false)
      setTraceDialog(true)
    } catch (err) {
      setErrorMsg('Flow trace failed: ' + (err.response?.data?.detail || err.message))
    } finally {
      setTraceLoading(false)
    }
  }

  // ── Graph controls ────────────────────────────────────────────

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

  // ── Canvas drawing ────────────────────────────────────────────

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const isHighlighted = highlightedNodes.size === 0 || highlightedNodes.has(node.id)
    const fontSize = Math.max(12 / globalScale, 4)
    ctx.font = `${fontSize}px Sans-Serif`

    const radius = node.val || 5
    const alpha  = isHighlighted ? 1 : 0.15   // dim non-highlighted nodes

    ctx.globalAlpha = alpha

    // Highlight ring for highlighted nodes
    if (highlightedNodes.has(node.id) && highlightedNodes.size > 0) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, radius + 3, 0, 2 * Math.PI)
      ctx.fillStyle = 'rgba(255, 215, 0, 0.4)'
      ctx.fill()
      ctx.strokeStyle = '#FFD700'
      ctx.lineWidth = 2
      ctx.stroke()
    }

    // Main circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI)
    ctx.fillStyle = node.color || '#999'
    ctx.fill()
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 1.5
    ctx.stroke()

    // Label — only show when zoomed in enough or highlighted
    if (globalScale >= 1 || highlightedNodes.has(node.id)) {
      const label      = node.name || node.id
      const textWidth  = ctx.measureText(label).width
      const bgW        = textWidth + fontSize * 0.4
      const bgH        = fontSize + fontSize * 0.4
      ctx.fillStyle    = 'rgba(255,255,255,0.92)'
      ctx.fillRect(node.x - bgW / 2, node.y + radius + 2, bgW, bgH)
      ctx.fillStyle    = '#111'
      ctx.textAlign    = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(label, node.x, node.y + radius + 2 + fontSize * 0.2)
    }

    ctx.globalAlpha = 1
  }, [highlightedNodes])

  const linkCanvasObject = useCallback((link, ctx) => {
    const isHighlighted = highlightedLinks.size === 0 || highlightedLinks.has(link)
    ctx.globalAlpha = isHighlighted ? 1 : 0.08
  }, [highlightedLinks])

  // ── Derived values ─────────────────────────────────────────────
  const uniqueNodeTypes     = [...new Set(graphData.nodes.map(n => n.type))]
  const uniqueRelationships = [...new Set(graphData.links.map(l => l.relationship))]

  // ── Render ────────────────────────────────────────────────────

  return (
    <Box sx={{ display: 'flex', height: '100vh', bgcolor: '#f5f5f5', overflow: 'hidden' }}>

      {/* ── Graph Area ────────────────────────────────────── */}
      <Box sx={{ flex: 2, position: 'relative', bgcolor: '#ffffff' }} className="graph-container">

        {/* Controls */}
        <Box className="graph-controls">
          <Tooltip title="Refresh Graph">
            <span>
              <IconButton className="control-button" onClick={fetchGraph} disabled={loading}>
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>
          <Tooltip title="Center">
            <IconButton className="control-button" onClick={handleCenter}>
              <CenterFocusStrong />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom In">
            <IconButton className="control-button" onClick={handleZoomIn}>
              <ZoomIn />
            </IconButton>
          </Tooltip>
          <Tooltip title="Zoom Out">
            <IconButton className="control-button" onClick={handleZoomOut}>
              <ZoomOut />
            </IconButton>
          </Tooltip>
          <Tooltip title={highlightMode ? 'Highlight Mode ON' : 'Highlight Mode OFF'}>
            <IconButton
              className="control-button"
              onClick={() => { setHighlightMode(h => !h); clearHighlights() }}
              sx={{ bgcolor: highlightMode ? '#1976d2 !important': {color: highlightMode ? 'white !important' : 'inherit'} }}
            >
              {highlightMode ? <Visibility /> : <VisibilityOff />}
            </IconButton>
          </Tooltip>
          {highlightedNodes.size > 0 && (
            <Tooltip title="Clear Highlights">
              <IconButton className="control-button" onClick={clearHighlights}>
                <Close fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Stats badge */}
        <Box className="stats-panel">
          <Typography variant="caption" sx={{ display: 'block', fontWeight: 600 }}>
            {filteredData.nodes.length} nodes · {filteredData.links.length} links
          </Typography>
          {highlightedNodes.size > 0 && (
            <Typography variant="caption" sx={{ color: '#f57c00', display: 'block' }}>
              🔆 {highlightedNodes.size} highlighted
            </Typography>
          )}
        </Box>

        {/* Loading overlay */}
        {loading && (
          <Box className="loading-overlay">
            <CircularProgress size={40} />
            <Typography variant="body2" sx={{ mt: 2, color: '#555' }}>Loading graph...</Typography>
          </Box>
        )}

        {/* Force Graph */}
        {filteredData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            graphData={filteredData}
            nodeLabel={node => `${NODE_TYPES[node.type]?.icon || '📄'} ${node.name} (${node.type})`}
            nodeVal={node => node.val}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            linkDirectionalArrowLength={4}
            linkDirectionalArrowRelPos={1}
            linkLabel={link => link.relationship}
            linkColor={link => highlightedLinks.has(link) ? '#f57c00' : '#bbb'}
            linkWidth={link => highlightedLinks.has(link) ? 2.5 : 1}
            nodeCanvasObject={nodeCanvasObject}
            nodeCanvasObjectMode={() => 'replace'}
            onLinkHover={link => {
              if (!link) { setHighlightedLinks(new Set()); return }
            }}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            warmupTicks={50}
          />
        ) : !loading ? (
          <Box className="empty-state">
            <Typography className="empty-state-icon">🔗</Typography>
            <Typography className="empty-state-title" variant="h6">No graph data</Typography>
            <Typography className="empty-state-subtitle" variant="body2">
              Make sure the backend is running and the database is populated
            </Typography>
            <Button sx={{ mt: 2 }} variant="contained" onClick={fetchGraph} startIcon={<Refresh />}>
              Load Graph
            </Button>
          </Box>
        ) : null}
      </Box>

      {/* ── Sidebar ───────────────────────────────────────── */}
      <Box sx={{ flex: 1, minWidth: 340, maxWidth: 400, display: 'flex', flexDirection: 'column', borderLeft: 1, borderColor: 'divider', overflow: 'hidden' }} className="sidebar">

        {/* Header + Query */}
        <Box className="query-section">
          <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 1, color: 'white' }}>
            <Chat /> SAP O2C Assistant
          </Typography>

          {errorMsg && (
            <Alert severity="warning" sx={{ mb: 1, fontSize: '0.75rem' }} onClose={() => setErrorMsg('')}>
              {errorMsg}
            </Alert>
          )}

          <TextField
            fullWidth multiline rows={3}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() } }}
            placeholder="Ask: 'Which products appear in the most billing documents?'"
            variant="outlined" size="small"
            className="query-textarea"
            sx={{
              mb: 1,
              '& .MuiOutlinedInput-root': { color: 'white', borderColor: 'rgba(255,255,255,0.4)' },
              '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.4)' },
              '& .MuiInputBase-input::placeholder': { color: 'rgba(255,255,255,0.6)' },
            }}
          />

          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              fullWidth variant="contained"
              onClick={handleQuery}
              disabled={loading || !query.trim()}
              className="send-button"
              startIcon={loading ? <CircularProgress size={16} sx={{ color: 'white' }} /> : <Send />}
              sx={{ bgcolor: 'rgba(255,255,255,0.2)', '&:hover': { bgcolor: 'rgba(255,255,255,0.3)' } }}
            >
              {loading ? 'Processing...' : 'Ask'}
            </Button>
            <Tooltip title="Settings">
              <IconButton
                onClick={() => { setDrawerOpen(true); fetchGraphStats() }}
                sx={{ color: 'white' }}
              >
                <Settings />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Filters */}
        <Box className="filters-section">
          <TextField
            fullWidth size="small"
            placeholder="Search nodes by name, ID or type..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="search-input"
            InputProps={{ startAdornment: <Search sx={{ mr: 1, color: 'action.active', fontSize: 18 }} /> }}
          />

          <Accordion disableGutters elevation={0} sx={{ bgcolor: 'transparent' }}>
            <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0, minHeight: 36 }}>
              <Typography variant="body2" fontWeight={600}>
                Node Types ({uniqueNodeTypes.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <Box className="chip-container">
                {uniqueNodeTypes.map(type => (
                  <Chip
                    key={type}
                    label={`${NODE_TYPES[type]?.icon || '📄'} ${type}`}
                    size="small"
                    className="node-type-chip"
                    variant={nodeFilter[type] ? 'filled' : 'outlined'}
                    onClick={() => toggleFilter(type, 'node')}
                    sx={{
                      bgcolor:     nodeFilter[type] ? NODE_TYPES[type]?.color : 'transparent',
                      color:       nodeFilter[type] ? 'white' : 'inherit',
                      borderColor: NODE_TYPES[type]?.color || '#999',
                    }}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>

          <Accordion disableGutters elevation={0} sx={{ bgcolor: 'transparent' }}>
            <AccordionSummary expandIcon={<ExpandMore />} sx={{ px: 0, minHeight: 36 }}>
              <Typography variant="body2" fontWeight={600}>
                Relationships ({uniqueRelationships.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0 }}>
              <Box className="chip-container">
                {uniqueRelationships.map(rel => (
                  <Chip
                    key={rel} label={rel} size="small"
                    className="relationship-chip"
                    variant={relationshipFilter[rel] ? 'filled' : 'outlined'}
                    onClick={() => toggleFilter(rel, 'relationship')}
                    color={relationshipFilter[rel] ? 'primary' : 'default'}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
        </Box>

        {/* Results */}
        <Box className="results-section">
          <Typography variant="subtitle2" fontWeight={600} sx={{ mb: 1 }}>Results</Typography>

          {answer && (
            <Paper className="result-card" elevation={0}>
              <Typography variant="body2" component="pre" sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.78rem' }}>
                {answer}
              </Typography>
              {sqlQuery && (
                <Box sx={{ mt: 1, borderTop: 1, borderColor: 'divider', pt: 1 }}>
                  <Typography
                    variant="caption"
                    sx={{ cursor: 'pointer', color: '#1976d2', userSelect: 'none' }}
                    onClick={() => setShowSql(s => !s)}
                  >
                    {showSql ? '▾ Hide SQL' : '▸ Show SQL'}
                  </Typography>
                  {showSql && (
                    <Typography variant="body2" component="pre" sx={{ mt: 1, fontSize: '0.72rem', fontFamily: 'monospace', color: '#555', whiteSpace: 'pre-wrap' }}>
                      {sqlQuery}
                    </Typography>
                  )}
                </Box>
              )}
            </Paper>
          )}

          {conversationHistory.length > 0 && (
            <Accordion disableGutters elevation={0}>
              <AccordionSummary expandIcon={<ExpandMore />}>
                <Typography variant="body2" fontWeight={600}>
                  History ({conversationHistory.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ p: 0 }}>
                <List dense disablePadding>
                  {conversationHistory.slice(-6).reverse().map((msg, idx) => (
                    <ListItem
                      key={idx} divider sx={{ px: 1, cursor: 'pointer', '&:hover': { bgcolor: '#f5f5f5' } }}
                      onClick={() => setQuery(msg.query || '')}
                    >
                      <ListItemText
                        primary={msg.query}
                        secondary={msg.timestamp}
                        primaryTypographyProps={{ variant: 'body2', noWrap: true }}
                        secondaryTypographyProps={{ variant: 'caption' }}
                      />
                    </ListItem>
                  ))}
                </List>
                <Button
                  size="small" fullWidth
                  onClick={async () => {
                    await axios.post(`${API_URL}/conversation/clear`)
                    setConversationHistory([])
                  }}
                  sx={{ mt: 0.5, color: 'error.main', fontSize: '0.72rem' }}
                >
                  Clear History
                </Button>
              </AccordionDetails>
            </Accordion>
          )}
        </Box>
      </Box>

      {/* ── Settings Drawer ───────────────────────────────── */}
      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}
        className="settings-drawer" PaperProps={{ className: 'settings-drawer' }}>
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6" fontWeight={600}>Settings</Typography>
            <IconButton onClick={() => setDrawerOpen(false)}><Close /></IconButton>
          </Box>

          <FormControlLabel
            control={<Switch checked={highlightMode} onChange={e => { setHighlightMode(e.target.checked); clearHighlights() }} />}
            label="Hover Highlight Mode"
          />
          <FormControlLabel
            control={<Switch checked={showSql} onChange={e => setShowSql(e.target.checked)} />}
            label="Always Show SQL"
          />

          <Divider sx={{ my: 2 }} />

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <BarChart fontSize="small" />
            <Typography variant="subtitle2" fontWeight={600}>Graph Statistics</Typography>
          </Box>

          {graphStats ? (
            <>
              <Typography variant="body2">Total Nodes: <strong>{graphStats.total_nodes?.toLocaleString()}</strong></Typography>
              <Typography variant="body2">Total Edges: <strong>{graphStats.total_edges?.toLocaleString()}</strong></Typography>
              <Divider sx={{ my: 1 }} />
              <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 0.5 }}>
                By Node Type
              </Typography>
              {Object.entries(graphStats.node_type_counts || {}).map(([type, count]) => (
                <Box key={type} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                  <Typography variant="caption">{NODE_TYPES[type]?.icon} {type}</Typography>
                  <Typography variant="caption" fontWeight={600}>{count}</Typography>
                </Box>
              ))}
              <Divider sx={{ my: 1 }} />
              <Typography variant="caption" fontWeight={600} sx={{ display: 'block', mb: 0.5 }}>
                By Edge Type
              </Typography>
              {Object.entries(graphStats.edge_type_counts || {}).map(([rel, count]) => (
                <Box key={rel} sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.25 }}>
                  <Typography variant="caption">{rel}</Typography>
                  <Typography variant="caption" fontWeight={600}>{count}</Typography>
                </Box>
              ))}
            </>
          ) : (
            <>
              <Typography variant="body2">Total Nodes: {graphData.nodes.length.toLocaleString()}</Typography>
              <Typography variant="body2">Total Links: {graphData.links.length.toLocaleString()}</Typography>
              <Typography variant="body2">Node Types: {uniqueNodeTypes.length}</Typography>
              <Typography variant="body2">Rel Types: {uniqueRelationships.length}</Typography>
            </>
          )}

          <Divider sx={{ my: 2 }} />
          <Button fullWidth variant="outlined" size="small" startIcon={<Refresh />} onClick={fetchGraph}>
            Rebuild Graph
          </Button>
        </Box>
      </Drawer>

      {/* ── Node Metadata Dialog ──────────────────────────── */}
      <Dialog open={metadataDialog} onClose={() => setMetadataDialog(false)} maxWidth="md" fullWidth className="metadata-dialog">
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6">
              {selectedNode && `${NODE_TYPES[selectedNode.type]?.icon || '📄'} ${selectedNode.name}`}
            </Typography>
            {selectedNode?.type && (
              <Chip label={selectedNode.type} size="small"
                sx={{ bgcolor: NODE_TYPES[selectedNode.type]?.color, color: 'white' }} />
            )}
          </Box>
          <IconButton onClick={() => setMetadataDialog(false)}><Close /></IconButton>
        </DialogTitle>

        <DialogContent>
          {nodeDetails && (
            <Grid container spacing={1.5} className="property-grid">
              {Object.entries(nodeDetails)
                .filter(([k]) => !['connections', 'id', 'type', 'label'].includes(k))
                .map(([key, value]) => (
                <Grid item xs={6} key={key}>
                  <Box className="property-item">
                    <Typography className="property-key">{key}</Typography>
                    <Typography className="property-value">{String(value ?? '—')}</Typography>
                  </Box>
                </Grid>
              ))}
              {/* Connections count */}
              {nodeDetails.connections?.length > 0 && (
                <Grid item xs={12}>
                  <Box className="property-item">
                    <Typography className="property-key">Connections</Typography>
                    <Typography className="property-value">{nodeDetails.connections.length} edges</Typography>
                  </Box>
                </Grid>
              )}
            </Grid>
          )}
        </DialogContent>

        <DialogActions>
          {/* Trace Flow button — only for BillingHeader nodes */}
          {selectedNode?.type === 'BillingHeader' && (
            <Button
              variant="contained" color="warning"
              startIcon={traceLoading ? <CircularProgress size={16} /> : <Timeline />}
              onClick={() => handleTraceFlow(selectedNode.billingDocument || selectedNode.id.replace('BH:', ''))}
              disabled={traceLoading}
            >
              Trace O2C Flow
            </Button>
          )}
          <Button onClick={() => {
            setMetadataDialog(false)
            // Highlight this node on the graph
            setHighlightedNodes(new Set([selectedNode.id]))
            fgRef.current?.centerAt(selectedNode.x, selectedNode.y, 800)
            fgRef.current?.zoom(3, 800)
          }}>
            Focus on Graph
          </Button>
          <Button onClick={() => setMetadataDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* ── O2C Flow Trace Dialog ─────────────────────────── */}
      <Dialog open={traceDialog} onClose={() => setTraceDialog(false)} maxWidth="lg" fullWidth>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Timeline />
            <Typography variant="h6">O2C Flow Trace</Typography>
          </Box>
          <IconButton onClick={() => setTraceDialog(false)}><Close /></IconButton>
        </DialogTitle>

        <DialogContent>
          {traceData && (
            <>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {traceData.nodes?.length} nodes · {traceData.edges?.length} edges in this flow
              </Typography>
              {/* Flow stages summary */}
              {['SalesOrderHeader', 'DeliveryHeader', 'BillingHeader', 'JournalEntry', 'Payment'].map(type => {
                const count = traceData.nodes?.filter(n => n.type === type).length || 0
                return count > 0 ? (
                  <Chip
                    key={type}
                    label={`${NODE_TYPES[type]?.icon} ${type} (${count})`}
                    sx={{ mr: 1, mb: 1, bgcolor: NODE_TYPES[type]?.color, color: 'white' }}
                  />
                ) : null
              })}
              <Divider sx={{ my: 2 }} />
              <Typography variant="caption" color="text.secondary">
                Tip: Close this dialog — the traced flow is now highlighted on the main graph.
              </Typography>
            </>
          )}
        </DialogContent>

        <DialogActions>
          <Button
            variant="contained"
            onClick={() => {
              if (traceData?.nodes?.length) {
                const ids = new Set(traceData.nodes.map(n => n.id))
                setHighlightedNodes(ids)
              }
              setTraceDialog(false)
            }}
          >
            Highlight on Graph
          </Button>
          <Button onClick={() => setTraceDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>

    </Box>
  )
}

export default App
