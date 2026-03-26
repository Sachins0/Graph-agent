import { useState, useEffect, useRef, useCallback } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import axios from 'axios'
import {
  Box, Paper, TextField, Button, Typography, Chip,
  IconButton, Drawer, List, ListItem, ListItemText,
  Divider, Accordion, AccordionSummary, AccordionDetails,
  CircularProgress, Grid, Tooltip, Switch, FormControlLabel,
  Dialog, DialogTitle, DialogContent, DialogActions, Alert
} from '@mui/material'
import {
  Send, Refresh, ExpandMore, Close, Search, Chat,
  Analytics, Settings, Visibility, VisibilityOff,
  ZoomIn, ZoomOut, CenterFocusStrong, Timeline, BarChart
} from '@mui/icons-material'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const NODE_TYPES = {
  SalesOrderHeader: { color: '#2196f3', icon: '📋' },
  SalesOrderItem:   { color: '#64b5f6', icon: '📦' },
  DeliveryHeader:   { color: '#4caf50', icon: '🚚' },
  DeliveryItem:     { color: '#81c784', icon: '📦' },
  BillingHeader:    { color: '#ff9800', icon: '🧾' },
  BillingItem:      { color: '#ffb74d', icon: '💰' },
  JournalEntry:     { color: '#9c27b0', icon: '📊' },
  Payment:          { color: '#e91e63', icon: '💳' },
  Customer:         { color: '#00bcd4', icon: '👤' },
  Product:          { color: '#8bc34a', icon: '🏷️' },
}

const NODE_SIZES = {
  SalesOrderHeader: 8, SalesOrderItem: 5,
  DeliveryHeader: 7,   DeliveryItem: 4,
  BillingHeader: 7,    BillingItem: 5,
  JournalEntry: 5,     Payment: 6,
  Customer: 9,         Product: 4,
}

export default function App() {
  const [graphData, setGraphData]         = useState({ nodes: [], links: [] })
  const [filteredData, setFilteredData]   = useState({ nodes: [], links: [] })
  const [query, setQuery]                 = useState('')
  const [answer, setAnswer]               = useState('')
  const [sqlQuery, setSqlQuery]           = useState('')
  const [loading, setLoading]             = useState(false)
  const [selectedNode, setSelectedNode]   = useState(null)
  const [nodeDetails, setNodeDetails]     = useState(null)
  const [drawerOpen, setDrawerOpen]       = useState(false)
  const [history, setHistory]             = useState([])
  const [nodeFilter, setNodeFilter]       = useState({})
  const [relFilter, setRelFilter]         = useState({})
  const [highlightMode, setHighlightMode] = useState(false)
  const [metaDialog, setMetaDialog]       = useState(false)
  const [traceDialog, setTraceDialog]     = useState(false)
  const [traceData, setTraceData]         = useState(null)
  const [searchTerm, setSearchTerm]       = useState('')
  const [graphStats, setGraphStats]       = useState(null)
  const [showSql, setShowSql]             = useState(false)
  const [errorMsg, setErrorMsg]           = useState('')
  const [graphDims, setGraphDims]         = useState({ w: 0, h: 0 })

  // ── Use refs for highlights — avoids stale closure in canvas callbacks ──
  const highlightedNodesRef = useRef(new Set())
  const highlightedLinksRef = useRef(new Set())
  const highlightTick       = useRef(0)           // increment to force canvas redraw
  const [, forceRender]     = useState(0)         // only used to trigger re-render when needed

  const fgRef        = useRef()
  const graphBoxRef  = useRef()

  // ── Measure graph container for explicit ForceGraph2D dimensions ──
  useEffect(() => {
    const obs = new ResizeObserver(entries => {
      for (const e of entries) {
        setGraphDims({ w: e.contentRect.width, h: e.contentRect.height })
      }
    })
    if (graphBoxRef.current) obs.observe(graphBoxRef.current)
    return () => obs.disconnect()
  }, [])

  useEffect(() => { fetchGraph(); fetchHistory() }, [])

  useEffect(() => { applyFilters() }, [graphData, nodeFilter, relFilter, searchTerm])

  // ── Data fetching ───────────────────────────────────────────────────────

  const fetchGraph = async () => {
    setLoading(true); setErrorMsg('')
    try {
      const res = await axios.get(`${API_URL}/graph/full`, { timeout: 60000 })
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
      setErrorMsg('Could not load graph. Is the backend running?')
    } finally { setLoading(false) }
  }

  const fetchHistory = async () => {
    try {
      const res = await axios.get(`${API_URL}/conversation/history`)
      setHistory(res.data.messages || [])
    } catch { /* silent */ }
  }

  // ── Filters ─────────────────────────────────────────────────────────────

  const applyFilters = useCallback(() => {
    let nodes = [...graphData.nodes]
    let links = [...graphData.links]
    if (Object.values(nodeFilter).some(Boolean))
      nodes = nodes.filter(n => nodeFilter[n.type])
    if (Object.values(relFilter).some(Boolean))
      links = links.filter(l => relFilter[l.relationship])
    if (searchTerm) {
      const s = searchTerm.toLowerCase()
      nodes = nodes.filter(n =>
        n.name?.toLowerCase().includes(s) ||
        n.id?.toLowerCase().includes(s)   ||
        n.type?.toLowerCase().includes(s)
      )
      const ids = new Set(nodes.map(n => n.id))
      links = links.filter(l => {
        const src = typeof l.source === 'object' ? l.source.id : l.source
        const tgt = typeof l.target === 'object' ? l.target.id : l.target
        return ids.has(src) && ids.has(tgt)
      })
    }
    setFilteredData({ nodes, links })
  }, [graphData, nodeFilter, relFilter, searchTerm])

  // ── Highlight helpers (ref-based, no stale closure) ─────────────────────

  const setHighlights = (nodeIds, links = new Set()) => {
    highlightedNodesRef.current = nodeIds
    highlightedLinksRef.current = links
    highlightTick.current += 1
    forceRender(t => t + 1)       // trigger one re-render so React re-passes callbacks
    fgRef.current?.refresh?.()    // tell ForceGraph to redraw canvas immediately
  }

  const clearHighlights = () => setHighlights(new Set(), new Set())

  // ── Query ────────────────────────────────────────────────────────────────

  const handleQuery = async () => {
    if (!query.trim()) return
    setLoading(true); setErrorMsg(''); setSqlQuery('')
    try {
      const res = await axios.post(`${API_URL}/query`, { prompt: query })
      if (res.data.blocked) {
        setAnswer(res.data.answer || res.data.error || 'Blocked.')
        setErrorMsg(res.data.hint || '')
        return
      }
      setAnswer(res.data.answer ?? JSON.stringify(res.data, null, 2))
      if (res.data.sql) setSqlQuery(res.data.sql)

      // ── Apply highlights from backend highlight_ids ──────────────
      if (res.data.highlight_ids?.length) {
        const ids   = new Set(res.data.highlight_ids)
        const hLinks = new Set()
        filteredData.links.forEach(l => {
          const src = typeof l.source === 'object' ? l.source.id : l.source
          const tgt = typeof l.target === 'object' ? l.target.id : l.target
          if (ids.has(src) || ids.has(tgt)) hLinks.add(l)
        })
        setHighlights(ids, hLinks)
        const first = filteredData.nodes.find(n => ids.has(n.id))
        if (first?.x != null) {
          fgRef.current?.centerAt(first.x, first.y, 800)
          fgRef.current?.zoom(3, 800)
        }
      } else {
        clearHighlights()
      }
      fetchHistory()
    } catch (err) {
      setErrorMsg('Error: ' + (err.response?.data?.detail || err.message))
    } finally { setLoading(false) }
  }

  // ── Node interaction ─────────────────────────────────────────────────────

  const handleNodeClick = async (node) => {
    setSelectedNode(node); setNodeDetails(null)
    try {
      const res = await axios.get(`${API_URL}/graph/entity/${encodeURIComponent(node.id)}`)
      setNodeDetails(res.data); setMetaDialog(true)
    } catch { setErrorMsg('Error loading node details') }
  }

  const handleNodeHover = useCallback((node) => {
    if (!highlightMode) return
    if (!node) { clearHighlights(); return }

    const ids   = new Set([node.id])
    const hLinks = new Set()
    filteredData.links.forEach(l => {
      const src = typeof l.source === 'object' ? l.source.id : l.source
      const tgt = typeof l.target === 'object' ? l.target.id : l.target
      if (src === node.id || tgt === node.id) {
        ids.add(src); ids.add(tgt); hLinks.add(l)
      }
    })
    setHighlights(ids, hLinks)
  }, [highlightMode, filteredData.links])

  const handleTraceFlow = async (billingDoc) => {
    try {
      const res = await axios.get(`${API_URL}/graph/trace/${billingDoc}`)
      setTraceData(res.data); setMetaDialog(false); setTraceDialog(true)
    } catch (err) {
      setErrorMsg('Trace failed: ' + (err.response?.data?.detail || err.message))
    }
  }

  // ── Graph controls ───────────────────────────────────────────────────────

  const zoomIn  = () => fgRef.current?.zoom(fgRef.current.zoom() * 1.3, 200)
  const zoomOut = () => fgRef.current?.zoom(fgRef.current.zoom() * 0.7, 200)
  const center  = () => { fgRef.current?.centerAt(0, 0, 800); fgRef.current?.zoom(1, 800) }

  const toggleFilter = (val, type) => {
    if (type === 'node') setNodeFilter(p => ({ ...p, [val]: !p[val] }))
    else setRelFilter(p => ({ ...p, [val]: !p[val] }))
  }

  // ── Canvas drawing — reads from refs, never stale ────────────────────────

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const hnodes   = highlightedNodesRef.current
    const hasHL    = hnodes.size > 0
    const isHL     = hnodes.has(node.id)
    const dimmed   = hasHL && !isHL
    const fontSize = Math.max(10 / globalScale, 3)

    ctx.globalAlpha = dimmed ? 0.12 : 1

    // Gold ring for highlighted node
    if (isHL) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, node.val + 4, 0, 2 * Math.PI)
      ctx.fillStyle = 'rgba(255,215,0,0.35)'
      ctx.fill()
      ctx.strokeStyle = '#FFD700'
      ctx.lineWidth   = 2.5 / globalScale
      ctx.stroke()
    }

    // Main circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI)
    ctx.fillStyle = node.color || '#999'
    ctx.fill()
    ctx.strokeStyle = isHL ? '#fff' : 'rgba(255,255,255,0.6)'
    ctx.lineWidth   = isHL ? 2 / globalScale : 1 / globalScale
    ctx.stroke()

    // Label — show when zoomed in or highlighted
    if (globalScale > 1.2 || isHL) {
      ctx.font      = `${fontSize}px Sans-Serif`
      const label   = node.name || node.id
      const tw      = ctx.measureText(label).width
      const pad     = fontSize * 0.3
      const bw      = tw + pad * 2
      const bh      = fontSize + pad * 2
      const by      = node.y + node.val + 2 / globalScale

      ctx.fillStyle = 'rgba(10,10,10,0.75)'
      ctx.beginPath()
      ctx.roundRect?.(node.x - bw / 2, by, bw, bh, 2) ?? ctx.fillRect(node.x - bw / 2, by, bw, bh)
      ctx.fill()

      ctx.fillStyle    = '#fff'
      ctx.textAlign    = 'center'
      ctx.textBaseline = 'top'
      ctx.fillText(label, node.x, by + pad)
    }

    ctx.globalAlpha = 1
  }, [highlightTick.current])   // re-creates when tick changes → ForceGraph picks it up

  const getLinkColor = useCallback((link) => {
    const hlinks = highlightedLinksRef.current
    const hnodes = highlightedNodesRef.current
    if (hlinks.size === 0 && hnodes.size === 0) return 'rgba(180,180,180,0.4)'
    if (hlinks.has(link)) return '#FF9800'
    const src = typeof link.source === 'object' ? link.source.id : link.source
    const tgt = typeof link.target === 'object' ? link.target.id : link.target
    if (hnodes.has(src) && hnodes.has(tgt)) return '#FF9800'
    return 'rgba(180,180,180,0.07)'
  }, [highlightTick.current])

  const getLinkWidth = useCallback((link) => {
    if (highlightedLinksRef.current.has(link)) return 2.5
    return 0.8
  }, [highlightTick.current])

  // ── Derived ──────────────────────────────────────────────────────────────

  const uniqueTypes = [...new Set(graphData.nodes.map(n => n.type))]
  const uniqueRels  = [...new Set(graphData.links.map(l => l.relationship))]

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <Box sx={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden', bgcolor: '#111' }}>

      {/* ════ Graph canvas ════════════════════════════════════════ */}
      <Box ref={graphBoxRef} sx={{ flex: 1, position: 'relative', minWidth: 0, overflow: 'hidden' }}>

        {/* Top-left controls */}
        <Box sx={{ position: 'absolute', top: 12, left: 12, zIndex: 10, display: 'flex', gap: 1 }}>
          {[
            { title: 'Refresh',         icon: <Refresh />,          fn: fetchGraph,   disabled: loading },
            { title: 'Center',          icon: <CenterFocusStrong />, fn: center },
            { title: 'Zoom In',         icon: <ZoomIn />,            fn: zoomIn },
            { title: 'Zoom Out',        icon: <ZoomOut />,           fn: zoomOut },
          ].map(({ title, icon, fn, disabled }) => (
            <Tooltip title={title} key={title}>
              <span>
                <IconButton size="small" onClick={fn} disabled={!!disabled}
                  sx={{ bgcolor: 'rgba(255,255,255,0.1)', color: '#fff', backdropFilter: 'blur(4px)',
                        '&:hover': { bgcolor: 'rgba(255,255,255,0.2)' }, border: '1px solid rgba(255,255,255,0.15)' }}>
                  {icon}
                </IconButton>
              </span>
            </Tooltip>
          ))}
          <Tooltip title={highlightMode ? 'Hover Highlight ON' : 'Hover Highlight OFF'}>
            <IconButton size="small"
              onClick={() => { setHighlightMode(h => !h); clearHighlights() }}
              sx={{ bgcolor: highlightMode ? '#1976d2' : 'rgba(255,255,255,0.1)',
                    color: '#fff', backdropFilter: 'blur(4px)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    '&:hover': { bgcolor: highlightMode ? '#1565c0' : 'rgba(255,255,255,0.2)' } }}>
              {highlightMode ? <Visibility /> : <VisibilityOff />}
            </IconButton>
          </Tooltip>
          {highlightedNodesRef.current.size > 0 && (
            <Tooltip title="Clear highlights">
              <IconButton size="small" onClick={clearHighlights}
                sx={{ bgcolor: 'rgba(255,152,0,0.3)', color: '#FF9800', border: '1px solid #FF9800' }}>
                <Close fontSize="small" />
              </IconButton>
            </Tooltip>
          )}
        </Box>

        {/* Top-right stats */}
        <Box sx={{ position: 'absolute', top: 12, right: 12, zIndex: 10,
                   bgcolor: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(8px)',
                   borderRadius: 2, px: 1.5, py: 0.75, border: '1px solid rgba(255,255,255,0.1)' }}>
          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.8)', fontFamily: 'monospace' }}>
            {filteredData.nodes.length.toLocaleString()} nodes · {filteredData.links.length.toLocaleString()} links
          </Typography>
          {highlightedNodesRef.current.size > 0 && (
            <Typography variant="caption" sx={{ color: '#FF9800', display: 'block' }}>
              🔆 {highlightedNodesRef.current.size} highlighted
            </Typography>
          )}
        </Box>

        {/* Loading overlay */}
        {loading && (
          <Box sx={{ position: 'absolute', inset: 0, bgcolor: 'rgba(0,0,0,0.6)',
                     display: 'flex', flexDirection: 'column', alignItems: 'center',
                     justifyContent: 'center', zIndex: 20 }}>
            <CircularProgress sx={{ color: '#fff' }} />
            <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.7)', mt: 2 }}>
              Loading graph...
            </Typography>
          </Box>
        )}

        {graphDims.w > 0 && filteredData.nodes.length > 0 ? (
          <ForceGraph2D
            ref={fgRef}
            width={graphDims.w}
            height={graphDims.h}
            graphData={filteredData}
            backgroundColor="#111111"
            nodeLabel={n => `${NODE_TYPES[n.type]?.icon || '●'} ${n.name} (${n.type})`}
            nodeVal={n => n.val}
            onNodeClick={handleNodeClick}
            onNodeHover={handleNodeHover}
            nodeCanvasObject={nodeCanvasObject}
            nodeCanvasObjectMode={() => 'replace'}
            linkColor={getLinkColor}
            linkWidth={getLinkWidth}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            linkLabel={l => l.relationship}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
            warmupTicks={60}
          />
        ) : !loading && (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
                     justifyContent: 'center', height: '100%', color: 'rgba(255,255,255,0.4)' }}>
            <Analytics sx={{ fontSize: 56, mb: 2, opacity: 0.4 }} />
            <Typography variant="h6" sx={{ mb: 1 }}>No graph data</Typography>
            <Button variant="outlined" onClick={fetchGraph} startIcon={<Refresh />}
              sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.3)' }}>
              Load Graph
            </Button>
          </Box>
        )}
      </Box>

      {/* ════ Sidebar ═════════════════════════════════════════════ */}
      <Box sx={{
        width: 360, minWidth: 360, maxWidth: 360,
        height: '100vh', display: 'flex', flexDirection: 'column',
        bgcolor: '#1a1a2e', borderLeft: '1px solid rgba(255,255,255,0.08)',
        overflow: 'hidden', flexShrink: 0,
      }}>

        {/* ── Header ─────────────────────────────────────────── */}
        <Box sx={{ p: 2, pb: 1.5, background: 'linear-gradient(135deg, #1976d2, #7b1fa2)',
                   flexShrink: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chat sx={{ color: '#fff', fontSize: 20 }} />
              <Typography variant="subtitle1" fontWeight={700} sx={{ color: '#fff' }}>
                SAP O2C Assistant
              </Typography>
            </Box>
            <Tooltip title="Settings">
              <IconButton size="small" onClick={() => { setDrawerOpen(true); axios.get(`${API_URL}/graph/stats`).then(r => setGraphStats(r.data)).catch(() => {}) }}
                sx={{ color: 'rgba(255,255,255,0.8)' }}>
                <Settings fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          {errorMsg && (
            <Alert severity="warning" onClose={() => setErrorMsg('')}
              sx={{ mb: 1, py: 0, fontSize: '0.72rem', bgcolor: 'rgba(255,152,0,0.15)', color: '#ffcc80',
                    '& .MuiAlert-icon': { color: '#ffcc80' } }}>
              {errorMsg}
            </Alert>
          )}

          <TextField
            fullWidth multiline minRows={2} maxRows={4}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleQuery() } }}
            placeholder="Ask about orders, deliveries, billing..."
            size="small"
            sx={{
              mb: 1,
              '& .MuiInputBase-root': {
                bgcolor: 'rgba(255,255,255,0.1)',
                color: '#fff',
                borderRadius: 2,
                fontSize: '0.875rem',
              },
              '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.2)' },
              '& .MuiInputBase-root:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.5)' },
              '& .MuiInputBase-root.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: '#fff' },
              '& textarea::placeholder': { color: 'rgba(255,255,255,0.45)', opacity: 1 },
            }}
          />
          <Button fullWidth variant="contained" onClick={handleQuery}
            disabled={loading || !query.trim()}
            startIcon={loading ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <Send />}
            sx={{ bgcolor: 'rgba(255,255,255,0.18)', color: '#fff', fontWeight: 600,
                  textTransform: 'none', borderRadius: 2,
                  '&:hover': { bgcolor: 'rgba(255,255,255,0.28)' },
                  '&.Mui-disabled': { bgcolor: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.3)' } }}>
            {loading ? 'Processing...' : 'Ask'}
          </Button>
        </Box>

        {/* ── Filters ────────────────────────────────────────── */}
        <Box sx={{ px: 2, py: 1.5, borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
          <TextField fullWidth size="small" placeholder="Search nodes..."
            value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
            InputProps={{ startAdornment: <Search sx={{ mr: 1, color: 'rgba(255,255,255,0.4)', fontSize: 18 }} /> }}
            sx={{
              mb: 1,
              '& .MuiInputBase-root': { bgcolor: 'rgba(255,255,255,0.06)', color: '#fff', borderRadius: 2, fontSize: '0.8rem' },
              '& .MuiOutlinedInput-notchedOutline': { borderColor: 'rgba(255,255,255,0.1)' },
              '& input::placeholder': { color: 'rgba(255,255,255,0.3)', opacity: 1 },
            }}
          />

          <Accordion disableGutters elevation={0}
            sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMore sx={{ color: 'rgba(255,255,255,0.5)', fontSize: 18 }} />}
              sx={{ px: 0, minHeight: 32, '& .MuiAccordionSummary-content': { my: 0 } }}>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Node Types ({uniqueTypes.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0, pb: 1 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {uniqueTypes.map(t => (
                  <Chip key={t} size="small"
                    label={`${NODE_TYPES[t]?.icon || '●'} ${t}`}
                    onClick={() => toggleFilter(t, 'node')}
                    sx={{
                      bgcolor:     nodeFilter[t] ? NODE_TYPES[t]?.color : 'rgba(255,255,255,0.07)',
                      color:       '#fff',
                      border:      `1px solid ${nodeFilter[t] ? NODE_TYPES[t]?.color : 'rgba(255,255,255,0.15)'}`,
                      fontSize:    '0.7rem',
                      height:      24,
                      cursor:      'pointer',
                      '&:hover':   { opacity: 0.85 },
                    }}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>

          <Accordion disableGutters elevation={0}
            sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}>
            <AccordionSummary expandIcon={<ExpandMore sx={{ color: 'rgba(255,255,255,0.5)', fontSize: 18 }} />}
              sx={{ px: 0, minHeight: 32, '& .MuiAccordionSummary-content': { my: 0 } }}>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.6)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                Relationships ({uniqueRels.length})
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 0, pb: 1 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {uniqueRels.map(r => (
                  <Chip key={r} size="small" label={r}
                    onClick={() => toggleFilter(r, 'rel')}
                    sx={{
                      bgcolor:  relFilter[r] ? '#1976d2' : 'rgba(255,255,255,0.07)',
                      color:    '#fff', border: '1px solid rgba(255,255,255,0.15)',
                      fontSize: '0.7rem', height: 22, cursor: 'pointer',
                    }}
                  />
                ))}
              </Box>
            </AccordionDetails>
          </Accordion>
        </Box>

        {/* ── Results ────────────────────────────────────────── */}
        <Box sx={{ flex: 1, overflow: 'auto', px: 2, py: 1.5,
                   '&::-webkit-scrollbar': { width: 4 },
                   '&::-webkit-scrollbar-thumb': { bgcolor: 'rgba(255,255,255,0.15)', borderRadius: 2 } }}>

          <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', fontWeight: 600,
                                               textTransform: 'uppercase', letterSpacing: 0.5, display: 'block', mb: 1 }}>
            Results
          </Typography>

          {answer && (
            <Paper elevation={0} sx={{ bgcolor: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
                                        borderRadius: 2, p: 1.5, mb: 1.5 }}>
              <Typography variant="body2" component="pre"
                sx={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: '0.78rem',
                      color: 'rgba(255,255,255,0.85)', lineHeight: 1.6, m: 0 }}>
                {answer}
              </Typography>
              {sqlQuery && (
                <Box sx={{ mt: 1, pt: 1, borderTop: '1px solid rgba(255,255,255,0.08)' }}>
                  <Typography variant="caption"
                    sx={{ color: '#64b5f6', cursor: 'pointer', userSelect: 'none' }}
                    onClick={() => setShowSql(s => !s)}>
                    {showSql ? '▾ Hide SQL' : '▸ Show SQL'}
                  </Typography>
                  {showSql && (
                    <Box component="pre" sx={{ mt: 1, p: 1, bgcolor: 'rgba(0,0,0,0.4)', borderRadius: 1,
                                               fontSize: '0.7rem', fontFamily: 'monospace',
                                               color: '#a5d6a7', whiteSpace: 'pre-wrap', m: 0, overflowX: 'auto' }}>
                      {sqlQuery}
                    </Box>
                  )}
                </Box>
              )}
            </Paper>
          )}

          {history.length > 0 && (
            <Accordion disableGutters elevation={0}
              sx={{ bgcolor: 'transparent', '&:before': { display: 'none' } }}>
              <AccordionSummary expandIcon={<ExpandMore sx={{ color: 'rgba(255,255,255,0.5)', fontSize: 18 }} />}
                sx={{ px: 0, minHeight: 32 }}>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600,
                                                     textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  History ({history.length})
                </Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ p: 0 }}>
                {history.slice(-6).reverse().map((msg, i) => (
                  <Box key={i} onClick={() => setQuery(msg.query || '')}
                    sx={{ p: 1, mb: 0.5, bgcolor: 'rgba(255,255,255,0.04)', borderRadius: 1,
                          cursor: 'pointer', '&:hover': { bgcolor: 'rgba(255,255,255,0.08)' } }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', display: 'block' }} noWrap>
                      {msg.query}
                    </Typography>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.65rem' }}>
                      {msg.timestamp}
                    </Typography>
                  </Box>
                ))}
                <Button size="small" fullWidth
                  onClick={async () => { await axios.post(`${API_URL}/conversation/clear`); setHistory([]) }}
                  sx={{ color: '#ef9a9a', fontSize: '0.7rem', mt: 0.5 }}>
                  Clear History
                </Button>
              </AccordionDetails>
            </Accordion>
          )}
        </Box>
      </Box>

      {/* ════ Settings Drawer ═════════════════════════════════════ */}
      <Drawer anchor="right" open={drawerOpen} onClose={() => setDrawerOpen(false)}
        PaperProps={{ sx: { width: 300, bgcolor: '#1a1a2e', color: '#fff', borderLeft: '1px solid rgba(255,255,255,0.08)' } }}>
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" fontWeight={700}>Settings</Typography>
            <IconButton onClick={() => setDrawerOpen(false)} sx={{ color: '#fff' }}><Close /></IconButton>
          </Box>
          <FormControlLabel
            control={<Switch checked={highlightMode} onChange={e => { setHighlightMode(e.target.checked); clearHighlights() }}
                       sx={{ '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.2)' } }} />}
            label={<Typography variant="body2" sx={{ color: '#fff' }}>Hover Highlight</Typography>}
          />
          <FormControlLabel
            control={<Switch checked={showSql} onChange={e => setShowSql(e.target.checked)}
                       sx={{ '& .MuiSwitch-track': { bgcolor: 'rgba(255,255,255,0.2)' } }} />}
            label={<Typography variant="body2" sx={{ color: '#fff' }}>Always Show SQL</Typography>}
          />
          <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.1)' }} />
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <BarChart sx={{ color: 'rgba(255,255,255,0.5)', fontSize: 18 }} />
            <Typography variant="body2" fontWeight={600} sx={{ color: 'rgba(255,255,255,0.7)' }}>Graph Stats</Typography>
          </Box>
          {(graphStats || graphData.nodes.length > 0) && (
            <>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                Nodes: <strong style={{ color: '#fff' }}>{(graphStats?.total_nodes || graphData.nodes.length).toLocaleString()}</strong>
              </Typography>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.6)' }}>
                Edges: <strong style={{ color: '#fff' }}>{(graphStats?.total_edges || graphData.links.length).toLocaleString()}</strong>
              </Typography>
              {graphStats?.node_type_counts && Object.entries(graphStats.node_type_counts).map(([t, c]) => (
                <Box key={t} sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.25 }}>
                  <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.5)' }}>
                    {NODE_TYPES[t]?.icon} {t}
                  </Typography>
                  <Typography variant="caption" sx={{ color: '#fff', fontWeight: 600 }}>{c}</Typography>
                </Box>
              ))}
            </>
          )}
          <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.1)' }} />
          <Button fullWidth variant="outlined" startIcon={<Refresh />} onClick={fetchGraph}
            sx={{ color: '#fff', borderColor: 'rgba(255,255,255,0.3)', textTransform: 'none' }}>
            Rebuild Graph
          </Button>
        </Box>
      </Drawer>

      {/* ════ Node Metadata Dialog ════════════════════════════════ */}
      <Dialog open={metaDialog} onClose={() => setMetaDialog(false)} maxWidth="sm" fullWidth
        PaperProps={{ sx: { bgcolor: '#1e1e2e', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', pb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="h6" sx={{ fontSize: '1rem' }}>
              {selectedNode && `${NODE_TYPES[selectedNode.type]?.icon} ${selectedNode.name}`}
            </Typography>
            {selectedNode?.type && (
              <Chip size="small" label={selectedNode.type}
                sx={{ bgcolor: NODE_TYPES[selectedNode.type]?.color, color: '#fff', fontSize: '0.7rem' }} />
            )}
          </Box>
          <IconButton onClick={() => setMetaDialog(false)} sx={{ color: 'rgba(255,255,255,0.6)' }}>
            <Close fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ pt: 0 }}>
          {nodeDetails && (
            <Grid container spacing={1}>
              {Object.entries(nodeDetails)
                .filter(([k]) => !['connections', 'id', 'type', 'label'].includes(k))
                .map(([k, v]) => (
                <Grid item xs={6} key={k}>
                  <Box sx={{ p: 1, bgcolor: 'rgba(255,255,255,0.05)', borderRadius: 1,
                              border: '1px solid rgba(255,255,255,0.08)' }}>
                    <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase',
                                                         letterSpacing: 0.5, fontSize: '0.65rem', display: 'block' }}>
                      {k}
                    </Typography>
                    <Typography variant="body2" sx={{ color: '#fff', fontSize: '0.8rem', wordBreak: 'break-word' }}>
                      {String(v ?? '—')}
                    </Typography>
                  </Box>
                </Grid>
              ))}
            </Grid>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          {selectedNode?.type === 'BillingHeader' && (
            <Button variant="contained" color="warning" startIcon={<Timeline />}
              onClick={() => handleTraceFlow(selectedNode.billingDocument || selectedNode.id.replace('BH:', ''))}>
              Trace O2C Flow
            </Button>
          )}
          <Button onClick={() => {
            if (selectedNode) {
              setHighlights(new Set([selectedNode.id]))
              fgRef.current?.centerAt(selectedNode.x, selectedNode.y, 800)
              fgRef.current?.zoom(4, 800)
            }
            setMetaDialog(false)
          }} sx={{ color: '#64b5f6' }}>Focus</Button>
          <Button onClick={() => setMetaDialog(false)} sx={{ color: 'rgba(255,255,255,0.6)' }}>Close</Button>
        </DialogActions>
      </Dialog>

      {/* ════ Trace Dialog ════════════════════════════════════════ */}
      <Dialog open={traceDialog} onClose={() => setTraceDialog(false)} maxWidth="sm" fullWidth
        PaperProps={{ sx: { bgcolor: '#1e1e2e', color: '#fff', border: '1px solid rgba(255,255,255,0.1)' } }}>
        <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Timeline sx={{ color: '#FF9800' }} />
            <Typography variant="h6">O2C Flow Trace</Typography>
          </Box>
          <IconButton onClick={() => setTraceDialog(false)} sx={{ color: 'rgba(255,255,255,0.6)' }}><Close /></IconButton>
        </DialogTitle>
        <DialogContent>
          {traceData && (
            <>
              <Typography variant="body2" sx={{ color: 'rgba(255,255,255,0.5)', mb: 2 }}>
                {traceData.nodes?.length} nodes · {traceData.edges?.length} edges in this flow
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {['SalesOrderHeader','DeliveryHeader','BillingHeader','JournalEntry','Payment'].map(t => {
                  const c = traceData.nodes?.filter(n => n.type === t).length || 0
                  return c > 0 ? (
                    <Chip key={t} label={`${NODE_TYPES[t]?.icon} ${t} (${c})`}
                      sx={{ bgcolor: NODE_TYPES[t]?.color, color: '#fff' }} />
                  ) : null
                })}
              </Box>
            </>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 2, pb: 2 }}>
          <Button variant="contained" color="warning"
            onClick={() => {
              if (traceData?.nodes?.length) setHighlights(new Set(traceData.nodes.map(n => n.id)))
              setTraceDialog(false)
            }}>
            Highlight on Graph
          </Button>
          <Button onClick={() => setTraceDialog(false)} sx={{ color: 'rgba(255,255,255,0.6)' }}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
