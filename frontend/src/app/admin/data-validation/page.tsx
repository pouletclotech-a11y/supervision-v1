'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
    Box,
    Typography,
    Button,
    Chip,
    IconButton,
    Paper,
    TextField,
    InputAdornment,
    Alert,
    CircularProgress,
    Divider,
    Tooltip,
    FormControlLabel,
    Switch,
    Drawer,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions
} from '@mui/material';
import { DataGrid, GridColDef, GridRenderCellParams, GridValueFormatterParams } from '@mui/x-data-grid';
import { FileText, AlertTriangle, CheckCircle, Search, RefreshCw, XCircle, Filter, Zap } from 'lucide-react';
import Layout from '../../../components/Layout';

import { fetchWithAuth } from '../../../lib/api';
import RuleTester from '../../../components/RuleTester';

// Phase 3: Connection Stats Types
interface ProviderStats {
    code: string;
    label: string;
    count: number;
    provider_id: number;
    ui_color?: string;
}

interface SiteConnectionItem {
    id: number;
    code_site: string;
    client_name: string | null;
    first_seen_at: string;
    provider_code: string;
    provider_label: string;
}

function DataValidationInner() {
    const searchParams = useSearchParams();
    const router = useRouter();

    // STATE
    const [imports, setImports] = useState<any[]>([]);
    const [loadingImports, setLoadingImports] = useState(false);
    const [importTotal, setImportTotal] = useState(0);
    const [importPaginationModel, setImportPaginationModel] = useState({ page: 0, pageSize: 20 });
    // Import filter STAGED state (not yet applied)
    const [stagedStatus, setStagedStatus] = useState<string>(() => searchParams.get('status') || '');
    const [stagedDateFrom, setStagedDateFrom] = useState<string>(() => searchParams.get('date_from') || '');
    const [stagedDateTo, setStagedDateTo] = useState<string>(() => searchParams.get('date_to') || '');

    // Applied import filters (trigger fetches)
    const [importStatusFilter, setImportStatusFilter] = useState<string>(() => searchParams.get('status') || '');
    const [importDateFrom, setImportDateFrom] = useState<string>(() => searchParams.get('date_from') || '');
    const [importDateTo, setImportDateTo] = useState<string>(() => searchParams.get('date_to') || '');

    const [selectedImportId, setSelectedImportId] = useState<number | null>(null);
    const [events, setEvents] = useState<any[]>([]);
    const [loadingEvents, setLoadingEvents] = useState(false);

    // Column Visibility State
    const [importColumnVisibility, setImportColumnVisibility] = useState<any>(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('import_cols_visibility');
            return saved ? JSON.parse(saved) : {};
        }
        return {};
    });

    const [eventColumnVisibility, setEventColumnVisibility] = useState<any>(() => {
        if (typeof window !== 'undefined') {
            const saved = localStorage.getItem('event_cols_visibility');
            return saved ? JSON.parse(saved) : {};
        }
        return {};
    });

    // Phase 8.3: Manual Widths (Resizable not supported in Community)
    // Removed state-based persistence for widths as it depends on onColumnWidthChange

    // Pagination State
    const [paginationModel, setPaginationModel] = useState({ page: 0, pageSize: 100 });
    const [sortModel, setSortModel] = useState<any[]>([{ field: 'time', sort: 'asc' }]);
    const [totalEvents, setTotalEvents] = useState(0);

    const [unmatchedOnly, setUnmatchedOnly] = useState(false);
    const [criticalOnly, setCriticalOnly] = useState(false);
    const [ruleFilter, setRuleFilter] = useState('');
    const [actionFilter, setActionFilter] = useState('');
    const [codeFilter, setCodeFilter] = useState('');
    const [error, setError] = useState<string | null>(null);

    const [testerOpen, setTesterOpen] = useState(false);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [loadingPdf, setLoadingPdf] = useState(false);

    // INSPECTION STATE
    const [inspectEvent, setInspectEvent] = useState<any | null>(null);

    // Phase 3: CONNECTIONS STATE
    const [providerStats, setProviderStats] = useState<ProviderStats[]>([]);
    const [connectionsDrillOpen, setConnectionsDrillOpen] = useState(false);
    const [selectedProviderCode, setSelectedProviderCode] = useState<string | null>(null);
    const [connections, setConnections] = useState<SiteConnectionItem[]>([]);
    const [connectionsTotal, setConnectionsTotal] = useState(0);
    const [loadingConnections, setLoadingConnections] = useState(false);
    const [connectionsSearch, setConnectionsSearch] = useState('');

    // Apply filters: push to URL and trigger fetch
    const applyFilters = useCallback(() => {
        setImportStatusFilter(stagedStatus);
        setImportDateFrom(stagedDateFrom);
        setImportDateTo(stagedDateTo);
        setImportPaginationModel({ page: 0, pageSize: importPaginationModel.pageSize });

        // Sync URL querystring
        const params = new URLSearchParams();
        if (stagedStatus) params.set('status', stagedStatus);
        if (stagedDateFrom) params.set('date_from', stagedDateFrom);
        if (stagedDateTo) params.set('date_to', stagedDateTo);
        router.replace(`?${params.toString()}`, { scroll: false });
    }, [stagedStatus, stagedDateFrom, stagedDateTo, importPaginationModel.pageSize]);

    const clearFilters = useCallback(() => {
        setStagedStatus('');
        setStagedDateFrom('');
        setStagedDateTo('');
        setImportStatusFilter('');
        setImportDateFrom('');
        setImportDateTo('');
        router.replace('?', { scroll: false });
    }, []);

    // Enter key to apply
    const handleFilterKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') applyFilters();
    };

    // FETCH IMPORTS
    const fetchImports = async () => {
        setLoadingImports(true);
        try {
            const skip = importPaginationModel.page * importPaginationModel.pageSize;
            let queryParams = `?skip=${skip}&limit=${importPaginationModel.pageSize}`;

            if (importStatusFilter) queryParams += `&status=${importStatusFilter}`;
            if (importDateFrom) queryParams += `&date_from=${importDateFrom}`;
            if (importDateTo) queryParams += `&date_to=${importDateTo}`;

            const res = await fetchWithAuth(`/imports${queryParams}`);
            if (!res.ok) throw new Error('Failed to fetch imports');
            const data = await res.json();

            setImports(data.imports || []);
            setImportTotal(data.total || 0);
            setError(null);
        } catch (err: any) {
            console.error(err);
            setError(err.message);
        } finally {
            setLoadingImports(false);
        }
    };

    // FETCH EVENTS
    const fetchEvents = async (importId: number) => {
        setLoadingEvents(true);
        try {
            const skip = paginationModel.page * paginationModel.pageSize;
            const sortField = sortModel[0]?.field || 'time';
            const sortOrder = sortModel[0]?.sort || 'asc';

            let queryParams = `?skip=${skip}&limit=${paginationModel.pageSize}&unmatched_only=${unmatchedOnly}&critical_only=${criticalOnly}&sort_by=${sortField}&order=${sortOrder}`;
            if (ruleFilter) queryParams += `&rule_name=${encodeURIComponent(ruleFilter)}`;
            if (actionFilter) queryParams += `&action_filter=${encodeURIComponent(actionFilter)}`;
            if (codeFilter) queryParams += `&code_filter=${encodeURIComponent(codeFilter)}`;

            const res = await fetchWithAuth(`/imports/${importId}/events${queryParams}`);
            if (!res.ok) throw new Error('Failed to fetch events');
            const data = await res.json();

            // Process events for Zebra Striping (Block-based)
            const rawEvents = data.events || [];
            let isZebra = false;
            const processedEvents = rawEvents.map((evt: any, index: number) => {
                // If site_code changes from previous row, toggle zebra state
                if (index > 0 && evt.site_code !== rawEvents[index - 1].site_code) {
                    isZebra = !isZebra;
                }
                return { ...evt, zebra_class: isZebra ? 'row-theme-b' : 'row-theme-a' };
            });

            setEvents(processedEvents);
            setTotalEvents(data.total || 0);
            setError(null);
        } catch (err: any) {
            console.error(err);
            setEvents([]);
            setTotalEvents(0);
        } finally {
            setLoadingEvents(false);
        }
    };

    // EFFECTS: only fetch when APPLIED filters change, not staged
    useEffect(() => { fetchImports(); fetchConnectionStats(); }, [importPaginationModel, importStatusFilter, importDateFrom, importDateTo]);

    // Phase 3: FETCH CONNECTION STATS
    const fetchConnectionStats = async () => {
        try {
            const res = await fetchWithAuth('/connections/stats');
            if (res.ok) {
                const data = await res.json();
                setProviderStats(data.providers || []);
            }
        } catch (err) {
            console.error('Failed to fetch connection stats', err);
        }
    };

    // Phase 3: FETCH CONNECTIONS DRILL-DOWN
    const fetchConnectionsDrillDown = async (providerCode: string | null, search: string = '') => {
        setLoadingConnections(true);
        try {
            let url = '/connections/list?limit=100';
            if (providerCode) url += `&provider_code=${providerCode}`;
            if (search) url += `&search=${encodeURIComponent(search)}`;
            const res = await fetchWithAuth(url);
            if (res.ok) {
                const data = await res.json();
                setConnections(data.connections || []);
                setConnectionsTotal(data.total || 0);
            }
        } catch (err) {
            console.error('Failed to fetch connections', err);
        } finally {
            setLoadingConnections(false);
        }
    };

    const openConnectionsDrill = (providerCode: string | null) => {
        setSelectedProviderCode(providerCode);
        setConnectionsSearch('');
        setConnectionsDrillOpen(true);
        fetchConnectionsDrillDown(providerCode, '');
    };

    useEffect(() => {
        if (selectedImportId) fetchEvents(selectedImportId);
        else { setEvents([]); setTotalEvents(0); }
    }, [selectedImportId, unmatchedOnly, criticalOnly, ruleFilter, actionFilter, codeFilter, paginationModel, sortModel]);

    // DEBUG: Monitor events data
    useEffect(() => {
        if (events.length > 0) {
            console.log("DEBUG: Keys in first event", Object.keys(events[0]));
            // console.log("DEBUG: First event sample", events[0]);
        }
    }, [events]);

    const [pdfType, setPdfType] = useState<'source' | 'pdf'>('source');

    // PDF LOADING
    useEffect(() => {
        if (inspectEvent) {
            // Determine if we should load the PDF or the source
            // If the row has a pdf_support_path AND we are in "PDF Mode" (from column click)
            // Or default to 'source' for event inspection
            loadPdf(inspectEvent.import_id, pdfType);
        } else {
            if (pdfUrl) URL.revokeObjectURL(pdfUrl);
            setPdfUrl(null);
        }
    }, [inspectEvent, pdfType]);

    const loadPdf = async (importId: number, type: 'source' | 'pdf' = 'source') => {
        setLoadingPdf(true);
        try {
            const res = await fetchWithAuth(`/imports/${importId}/download?file_type=${type}`);
            if (res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                setPdfUrl(url);
            } else {
                const errorData = await res.json().catch(() => ({}));
                const msg = errorData.detail || `Failed to load ${type} file`;
                setError(msg);
                setPdfUrl(null);
            }
        } catch (err) {
            console.error("Failed to load PDF", err);
            setError(`Network error loading ${type}`);
        } finally {
            setLoadingPdf(false);
        }
    };


    // Persistence Handlers
    const handleImportVisibilityChange = (newModel: any) => {
        setImportColumnVisibility(newModel);
        localStorage.setItem('import_cols_visibility', JSON.stringify(newModel));
    };

    const handleEventVisibilityChange = (newModel: any) => {
        setEventColumnVisibility(newModel);
        localStorage.setItem('event_cols_visibility', JSON.stringify(newModel));
    };

    // Removed Width change handlers

    // COLUMNS
    const importColumns: GridColDef[] = useMemo(() => [
        { field: 'id', headerName: 'ID', width: 70 },
        { field: 'created_at', headerName: 'Date', width: 170, valueFormatter: (params: any) => params.value ? new Date(params.value).toLocaleString() : '' },
        { field: 'filename', headerName: 'File', minWidth: 200, width: 350 },
        {
            field: 'pdf_support_path', headerName: 'PDF', width: 60,
            renderCell: (params: GridRenderCellParams) => {
                if (!params.value) return null;
                return (
                    <Tooltip title={params.row.pdf_support_filename || "View PDF Support"}>
                        <IconButton
                            size="small"
                            color="error"
                            onClick={(e) => {
                                e.stopPropagation();
                                setPdfType('pdf');
                                setInspectEvent({ ...params.row, import_id: params.row.id });
                            }}
                        >
                            <FileText size={18} />
                        </IconButton>
                    </Tooltip>
                );
            }
        },
        {
            field: 'status', headerName: 'Status', width: 90,
            renderCell: (params: GridRenderCellParams) => {
                let status = params.value;
                let color: "success" | "error" | "warning" = 'warning';

                if (status === 'SUCCESS' || status === 'DONE') {
                    if (params.row.match_pct !== undefined && params.row.match_pct < 95) {
                        status = 'WARNING';
                        color = 'warning';
                    } else {
                        color = 'success';
                    }
                } else if (status === 'ERROR') {
                    color = 'error';
                }

                return <Chip label={status} color={color} size="small" variant="filled" sx={{ height: 20, fontSize: 10 }} />;
            }
        },
        {
            field: 'match_pct', headerName: 'Integrity', width: 80, align: 'center',
            renderCell: (params: GridRenderCellParams) => {
                if (params.value === undefined || params.value === null) return <Typography variant="caption" color="text.disabled">—</Typography>;
                const color = params.value >= 95 ? 'success.main' : params.value >= 80 ? 'warning.main' : 'error.main';
                return <Typography variant="body2" sx={{ fontWeight: 'bold', color }}>{params.value.toFixed(1)}%</Typography>;
            }
        },
        { field: 'events_count', headerName: 'Evts', width: 70, align: 'right' },
        { field: 'unmatched_count', headerName: 'Unm', width: 70, align: 'right' },
    ], []);


    const eventColumns: GridColDef[] = useMemo(() => [
        { field: 'id', headerName: 'ID', width: 80 },
        {
            field: 'weekday_label', headerName: 'Jour', width: 70,
            renderCell: (params: GridRenderCellParams) => <Typography sx={{ fontSize: 11, fontWeight: 'bold', color: 'text.secondary' }}>{params.value}</Typography>
        },
        { field: 'time', headerName: 'Time', width: 170, valueFormatter: (params: GridValueFormatterParams) => params.value ? new Date(params.value).toLocaleString() : '' },
        {
            field: 'site_code', headerName: 'Site', width: 90,
            renderCell: (params: GridRenderCellParams) => (
                <Chip
                    label={params.value || '?'}
                    size="small"
                    variant="outlined"
                    sx={{
                        height: 20,
                        fontSize: 11,
                        bgcolor: 'rgba(255,255,255,0.1)',
                        borderColor: 'rgba(255,255,255,0.2)',
                        color: 'text.primary',
                        fontWeight: 'bold'
                    }}
                />
            )
        },
        {
            field: 'client_name', headerName: 'Client', width: 250,
            renderCell: (params: GridRenderCellParams) => <Typography variant="body2" sx={{ fontSize: 12, color: 'text.primary' }}>{params.value}</Typography>
        },
        {
            field: 'severity', headerName: 'Severity', width: 100,
            renderCell: (params: GridRenderCellParams) => {
                const s = (params.value || 'INFO').toUpperCase() as string;
                let color: "default" | "primary" | "secondary" | "error" | "info" | "success" | "warning" = "default";
                if (s === 'CRITICAL' || s === 'ALARM') color = "error";
                else if (s === 'WARNING') color = "warning";
                else if (s === 'SUCCESS') color = "success";
                return <Chip label={s} color={color} size="small" variant="outlined" sx={{ height: 18, fontSize: 9 }} />;
            }
        },
        {
            field: 'triggered_rules', headerName: 'Règle(s)', width: 350,
            renderCell: (params: GridRenderCellParams) => {
                const rules = params.value || [];
                if (rules.length === 0) return <Typography variant="caption" sx={{ color: 'text.disabled' }}>—</Typography>;

                const visibleRules = rules.slice(0, 2);
                const remainingCount = rules.length - 2;

                const fullListTooltip = (
                    <Box sx={{ p: 0.5 }}>
                        {rules.map((r: any) => (
                            <Typography key={r.id} variant="caption" display="block" sx={{ fontSize: 10 }}>
                                • {r.name} ({new Date(r.matched_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})
                            </Typography>
                        ))}
                    </Box>
                );

                return (
                    <Tooltip title={fullListTooltip} arrow>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                            {visibleRules.map((r: any) => (
                                <Chip key={r.id} label={r.name} size="small" variant="filled" color="secondary" sx={{ height: 16, fontSize: 8, fontWeight: 'bold' }} />
                            ))}
                            {remainingCount > 0 && (
                                <Chip label={`+${remainingCount}`} size="small" variant="outlined" color="secondary" sx={{ height: 16, fontSize: 8, fontWeight: 'bold' }} />
                            )}
                        </Box>
                    </Tooltip>
                );
            }
        },
        {
            field: 'normalized_type', headerName: 'Action', width: 120,
            renderCell: (params: GridRenderCellParams) => {
                const val = (params.value || '').toUpperCase();
                let color: "default" | "error" | "success" | "primary" | "secondary" | "info" | "warning" = "default";
                let customSx = {};

                if (val === 'APPARITION') color = 'error';
                else if (val === 'DISPARITION') color = 'success';
                else if (val.includes('TEST ROUTINE') || val.includes('TEST_ROUTINE')) {
                    color = 'warning'; // Yellow-ish
                } else if (val.includes('BROUILLAGE')) {
                    // Purple is not a standard MUI color in this version's theme, use custom sx
                    customSx = {
                        bgcolor: '#9c27b0', // Material Purple
                        color: '#fff',
                        '&:hover': { bgcolor: '#7b1fa2' }
                    };
                }

                return (
                    <Chip
                        label={val || '—'}
                        color={color !== 'default' ? color : undefined}
                        size="small"
                        variant="filled"
                        sx={{
                            height: 20,
                            fontSize: 10,
                            fontWeight: 'bold',
                            minWidth: 80,
                            ...customSx
                        }}
                    />
                );
            }
        },
        {
            field: 'raw_code', headerName: 'Code', width: 110,
            renderCell: (params: GridRenderCellParams) => (
                <Typography variant="body2" sx={{ fontSize: 11, fontFamily: 'monospace', color: 'text.secondary' }}>
                    {params.value || '—'}
                </Typography>
            )
        },
        {
            field: 'raw_message', headerName: 'Message / Details', minWidth: 200, width: 600,
            renderCell: (params: GridRenderCellParams) => (
                <Box sx={{ py: 0.5, lineHeight: 1.2 }}>
                    <Typography variant="body2" sx={{ fontSize: 11, fontFamily: 'monospace' }}>{params.value}</Typography>
                    {params.row.zone_label && (
                        <Typography variant="caption" sx={{ color: 'primary.main', fontSize: 10 }}>Zone: {params.row.zone_label}</Typography>
                    )}
                </Box>
            )
        },
        {
            field: 'actions', headerName: 'Actions', width: 80, align: 'right',
            renderCell: (params: GridRenderCellParams) => (
                <Button size="small" onClick={() => setInspectEvent(params.row)}>Inspect</Button>
            )
        }
    ], []);

    return (
        <Layout>
            <Box sx={{ display: 'flex', height: '100%', width: '100%', overflow: 'hidden' }}>
                {/* LEFT PANEL: IMPORTS */}
                <Paper square sx={{ width: '30%', minWidth: 300, display: 'flex', flexDirection: 'column', borderRight: '1px solid', borderColor: 'divider', zIndex: 1 }}>
                    <Box sx={{ p: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between', bgcolor: 'background.paper', borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: 1 }}>
                            <FileText size={16} /> IMPORT LOGS
                        </Typography>
                        <IconButton onClick={fetchImports} color="primary" size="small"><RefreshCw size={14} /></IconButton>
                    </Box>

                    {/* Phase 3: KPI CARDS */}
                    <Box sx={{ px: 2, py: 1.5, display: 'flex', gap: 1.5, flexWrap: 'wrap', borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'rgba(0,0,0,0.2)' }}>
                        {providerStats.map((p) => {
                            const customColor = p.ui_color || '#1976d2';
                            return (
                                <Paper
                                    key={p.code}
                                    onClick={() => openConnectionsDrill(p.code)}
                                    sx={{
                                        p: 1.5,
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        '&:hover': { transform: 'scale(1.02)', boxShadow: 3, bgcolor: `${customColor}22` },
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        minWidth: 90,
                                        flex: '1 1 auto',
                                        bgcolor: `${customColor}14`,
                                        border: '1px solid',
                                        borderColor: customColor
                                    }}
                                >
                                    <Typography variant="h5" sx={{ fontWeight: 'bold', color: customColor }}>
                                        {p.count}
                                    </Typography>
                                    <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 10, fontWeight: 600, textAlign: 'center' }}>
                                        {p.label}
                                    </Typography>
                                </Paper>
                            );
                        })}
                        <Paper
                            onClick={() => openConnectionsDrill(null)}
                            sx={{
                                p: 1.5,
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                '&:hover': { transform: 'scale(1.02)', boxShadow: 3 },
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                minWidth: 90,
                                bgcolor: 'rgba(255,255,255,0.05)',
                                border: '1px solid',
                                borderColor: 'divider'
                            }}
                        >
                            <Typography variant="h5" sx={{ fontWeight: 'bold' }}>
                                {providerStats.reduce((sum: number, p: ProviderStats) => sum + p.count, 0)}
                            </Typography>
                            <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: 10 }}>
                                TOTAL
                            </Typography>
                        </Paper>
                    </Box>

                    {/* FILTERS FOR IMPORTS */}
                    <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', gap: 1, borderBottom: '1px solid', borderColor: 'divider', bgcolor: 'rgba(255,255,255,0.02)' }}>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <TextField
                                select
                                size="small"
                                label="Status"
                                value={stagedStatus}
                                onChange={(e) => setStagedStatus(e.target.value)}
                                onKeyDown={handleFilterKeyDown}
                                SelectProps={{ native: true }}
                                sx={{ flex: 1, '& .MuiInputBase-root': { fontSize: 11 } }}
                                InputLabelProps={{ shrink: true }}
                            >
                                <option value="">All</option>
                                <option value="SUCCESS">SUCCESS</option>
                                <option value="ERROR">ERROR</option>
                                <option value="DONE">DONE</option>
                            </TextField>
                            <Button
                                size="small"
                                variant={stagedStatus === 'ERROR' ? 'contained' : 'outlined'}
                                color="error"
                                onClick={() => { setStagedStatus(stagedStatus === 'ERROR' ? '' : 'ERROR'); }}
                                sx={{ fontSize: 9, minWidth: 60 }}
                            >
                                Errors
                            </Button>
                            <Button size="small" variant="outlined" onClick={clearFilters} sx={{ fontSize: 9 }}>Clear</Button>
                        </Box>
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            <TextField
                                type="date"
                                size="small"
                                label="From"
                                value={stagedDateFrom}
                                onChange={(e) => setStagedDateFrom(e.target.value)}
                                onKeyDown={handleFilterKeyDown}
                                sx={{ flex: 1, '& .MuiInputBase-root': { fontSize: 10 } }}
                                InputLabelProps={{ shrink: true }}
                            />
                            <TextField
                                type="date"
                                size="small"
                                label="To"
                                value={stagedDateTo}
                                onChange={(e) => setStagedDateTo(e.target.value)}
                                onKeyDown={handleFilterKeyDown}
                                sx={{ flex: 1, '& .MuiInputBase-root': { fontSize: 10 } }}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Box>
                        <Button
                            fullWidth
                            variant="contained"
                            size="small"
                            onClick={applyFilters}
                            sx={{ fontSize: 10, py: 0.5 }}
                        >
                            Appliquer
                        </Button>
                    </Box>

                    <Box sx={{ flex: 1, width: '100%', overflow: 'hidden' }}>
                        <DataGrid
                            rows={imports}
                            columns={importColumns}
                            loading={loadingImports}
                            rowCount={importTotal}
                            paginationMode="server"
                            pageSizeOptions={[20, 50, 100]}
                            paginationModel={importPaginationModel}
                            onPaginationModelChange={setImportPaginationModel}
                            rowHeight={40}
                            density="compact"
                            onRowClick={(params) => setSelectedImportId(params.row.id)}
                            disableRowSelectionOnClick
                            columnVisibilityModel={importColumnVisibility}
                            onColumnVisibilityModelChange={handleImportVisibilityChange}
                            sx={{ border: 0 }}
                        />
                    </Box>
                </Paper>

                {/* RIGHT PANEL: EVENTS */}
                <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: 'background.default', overflow: 'hidden' }}>

                    {/* TOOLBAR */}
                    <Paper square elevation={0} sx={{ p: 1.5, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: 'background.paper' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                            <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                {selectedImportId ? `Job #${selectedImportId}` : 'Select a Job'}
                            </Typography>
                            {selectedImportId && (
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.2, bgcolor: 'action.hover', borderRadius: 1, border: '1px solid', borderColor: 'divider' }}>
                                    <AlertTriangle size={12} color="#ed6c02" />
                                    <Typography variant="caption" sx={{ fontSize: 10, color: 'text.secondary' }}>
                                        Hits en mode <strong>Replace</strong>. Relancez le Replay si vous changez les règles.
                                    </Typography>
                                </Box>
                            )}
                            {selectedImportId && (
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    <Chip label={`${totalEvents} Events`} size="small" variant="outlined" sx={{ borderColor: 'divider', color: 'text.secondary', fontWeight: 500 }} />
                                </Box>
                            )}
                        </Box>

                        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                            {/* SEARCH GROUP */}
                            <Box sx={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 1,
                                bgcolor: 'rgba(255,255,255,0.03)',
                                p: 0.5,
                                pr: 1.5,
                                borderRadius: 2,
                                border: '1px solid',
                                borderColor: 'divider',
                                '&:focus-within': {
                                    borderColor: 'primary.main',
                                    bgcolor: 'rgba(255,255,255,0.05)'
                                }
                            }}>
                                <TextField
                                    size="small"
                                    placeholder="Rule name..."
                                    variant="standard"
                                    value={ruleFilter}
                                    onChange={(e: React.ChangeEvent<HTMLInputElement>) => setRuleFilter(e.target.value)}
                                    sx={{ width: 140, ml: 1, '& .MuiInput-root': { fontSize: 12 } }}
                                    InputProps={{
                                        disableUnderline: true,
                                        startAdornment: <Search size={14} style={{ marginRight: 8, opacity: 0.6 }} />
                                    }}
                                />
                                <Box sx={{ width: '1px', height: 20, bgcolor: 'divider', mx: 0.5 }} />
                                <TextField
                                    size="small"
                                    placeholder="Action..."
                                    variant="standard"
                                    value={actionFilter}
                                    onChange={(e) => setActionFilter(e.target.value)}
                                    sx={{ width: 100, '& .MuiInput-root': { fontSize: 12 } }}
                                    InputProps={{
                                        disableUnderline: true,
                                        startAdornment: <Filter size={12} style={{ marginRight: 6, opacity: 0.6 }} />
                                    }}
                                />
                                <Box sx={{ width: '1px', height: 20, bgcolor: 'divider', mx: 0.5 }} />
                                <TextField
                                    size="small"
                                    placeholder="Code..."
                                    variant="standard"
                                    value={codeFilter}
                                    onChange={(e) => setCodeFilter(e.target.value)}
                                    sx={{ width: 80, '& .MuiInput-root': { fontSize: 12 } }}
                                    InputProps={{
                                        disableUnderline: true,
                                        startAdornment: <Zap size={12} style={{ marginRight: 6, opacity: 0.6 }} />
                                    }}
                                />
                                {(ruleFilter || actionFilter || codeFilter) && (
                                    <IconButton size="small" onClick={() => { setRuleFilter(''); setActionFilter(''); setCodeFilter(''); }} sx={{ ml: 0.5, opacity: 0.7 }}>
                                        <XCircle size={14} />
                                    </IconButton>
                                )}
                            </Box>

                            {/* TOGGLE GROUP */}
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, bgcolor: 'rgba(255,255,255,0.03)', px: 1, py: 0.5, borderRadius: 2, border: '1px solid', borderColor: 'divider' }}>
                                <Tooltip title="Toggle Unmatched Events">
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <Switch size="small" checked={unmatchedOnly} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setUnmatchedOnly(e.target.checked)} />
                                        <Typography variant="caption" sx={{ fontSize: 10, color: unmatchedOnly ? 'primary.main' : 'text.disabled', fontWeight: unmatchedOnly ? 700 : 400 }}>UNM</Typography>
                                    </Box>
                                </Tooltip>
                                <Box sx={{ width: '1px', height: 16, bgcolor: 'divider', mx: 1 }} />
                                <Tooltip title="Toggle Critical/Alarm Severity">
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                        <Switch size="small" color="error" checked={criticalOnly} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCriticalOnly(e.target.checked)} />
                                        <Typography variant="caption" sx={{ fontSize: 10, color: criticalOnly ? 'error.main' : 'text.disabled', fontWeight: criticalOnly ? 700 : 400 }}>CRIT</Typography>
                                    </Box>
                                </Tooltip>
                            </Box>

                            <Button
                                variant="outlined"
                                color="secondary"
                                size="small"
                                startIcon={<Search size={14} />}
                                onClick={() => setTesterOpen(true)}
                                sx={{ borderRadius: 2, textTransform: 'none', px: 2 }}
                            >
                                Rule Tester
                            </Button>

                            <IconButton onClick={() => selectedImportId && fetchEvents(selectedImportId)} disabled={!selectedImportId} size="small" sx={{ color: 'text.secondary' }}>
                                <RefreshCw size={16} />
                            </IconButton>
                        </Box>
                    </Paper>

                    {/* CONTENT AREA */}
                    <Box sx={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                        {!selectedImportId ? (
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'text.secondary', gap: 2 }}>
                                <FileText size={48} opacity={0.2} />
                                <Typography>Select an import file on the left to inspect events</Typography>
                            </Box>
                        ) : (
                            <Box sx={{ height: '100%', width: '100%', display: 'flex', flexDirection: 'column' }}>
                                <DataGrid
                                    rows={events}
                                    columns={eventColumns}
                                    loading={loadingEvents}
                                    rowCount={totalEvents}
                                    paginationMode="server"
                                    pageSizeOptions={[20, 50, 100]}
                                    paginationModel={paginationModel}
                                    onPaginationModelChange={setPaginationModel}
                                    sortingMode="server"
                                    sortModel={sortModel}
                                    onSortModelChange={setSortModel}
                                    rowHeight={40}
                                    density="compact"
                                    disableRowSelectionOnClick
                                    columnVisibilityModel={eventColumnVisibility}
                                    onColumnVisibilityModelChange={handleEventVisibilityChange}
                                    getRowClassName={(params) => params.row.zebra_class || 'row-theme-a'}
                                    sx={{
                                        border: 0,
                                        '& .MuiDataGrid-row:hover': { bgcolor: 'rgba(255, 255, 255, 0.08)' }, // Hover slightly lighter
                                        '& .row-theme-a': { bgcolor: 'transparent' }, // Standard Dark
                                        '& .row-theme-b': { bgcolor: 'rgba(255, 255, 255, 0.04)' }, // Subtle Zebra (4% White)
                                        '& .MuiDataGrid-cell': { borderBottom: '1px solid rgba(255, 255, 255, 0.05)' } // Minimal borders
                                    }}
                                />
                            </Box>
                        )}
                    </Box>
                </Box>
            </Box>

            {/* RULE TESTER DRAWER */}
            <Drawer anchor="right" open={testerOpen} onClose={() => setTesterOpen(false)}>
                <Box sx={{ width: 400, p: 0 }}>
                    <Box sx={{ p: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
                        <Typography variant="subtitle1" fontWeight="bold">Rule Tester</Typography>
                        <IconButton onClick={() => setTesterOpen(false)}><XCircle size={18} /></IconButton>
                    </Box>
                    <RuleTester />
                </Box>
            </Drawer>

            {/* INSPECTION DRAWER */}
            <Drawer anchor="bottom" open={!!inspectEvent} onClose={() => setInspectEvent(null)} PaperProps={{ sx: { height: '85vh' } }}>
                {inspectEvent && (
                    <Box sx={{ display: 'flex', height: '100%', flexDirection: 'column' }}>
                        {/* HEADER */}
                        <Box sx={{ p: 1.5, bgcolor: '#333', color: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                                <Typography variant="h6" sx={{ color: 'white' }}>INSPECTION MODE</Typography>
                                <Chip label={`Event #${inspectEvent.id}`} size="small" sx={{ bgcolor: 'white', color: 'black' }} />
                                <Typography variant="body2" sx={{ opacity: 0.8 }}>{inspectEvent.raw_message}</Typography>
                            </Box>
                            <IconButton onClick={() => setInspectEvent(null)} sx={{ color: 'white' }}><XCircle /></IconButton>
                        </Box>

                        {/* SPLIT VIEW */}
                        <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                            {/* LEFT: PDF VIEWER */}
                            <Box sx={{ flex: 1, bgcolor: '#525659', display: 'flex', flexDirection: 'column', position: 'relative' }}>
                                {loadingPdf && (
                                    <Box sx={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 10 }}>
                                        <Typography sx={{ color: 'white' }}>Loading PDF...</Typography>
                                    </Box>
                                )}
                                {pdfUrl && (
                                    <iframe
                                        src={pdfUrl}
                                        width="100%"
                                        height="100%"
                                        style={{ border: 'none' }}
                                        title="PDF Viewer"
                                    />
                                )}
                            </Box>

                            {/* RIGHT: DETAILS */}
                            <Box sx={{ width: 400, bgcolor: 'background.paper', borderLeft: '1px solid', borderColor: 'divider', overflowY: 'auto', p: 3 }}>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>EVENT DETAILS</Typography>

                                <Box sx={{ mb: 3 }}>
                                    <Typography variant="caption" display="block" color="text.secondary">Message</Typography>
                                    <Paper variant="outlined" sx={{ p: 1.5, bgcolor: 'background.default', fontFamily: 'monospace', fontSize: 13 }}>
                                        {inspectEvent.raw_message}
                                    </Paper>
                                </Box>

                                <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2, mb: 3 }}>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Severity</Typography>
                                        <Box sx={{ mt: 0.5 }}>
                                            <Chip label={inspectEvent.severity || 'INFO'} color={inspectEvent.severity === 'CRITICAL' ? 'error' : 'default'} size="small" />
                                        </Box>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Time</Typography>
                                        <Typography variant="body2">{new Date(inspectEvent.time).toLocaleTimeString()}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Site</Typography>
                                        <Typography variant="body2">{inspectEvent.site_code || '-'}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Client</Typography>
                                        <Typography variant="body2">{inspectEvent.client_name || '-'}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Jour</Typography>
                                        <Typography variant="body2">{inspectEvent.weekday_label || '-'}</Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="caption" color="text.secondary">Type</Typography>
                                        <Typography variant="body2">{inspectEvent.normalized_type || 'UNKNOWN'}</Typography>
                                    </Box>
                                </Box>

                                <Alert severity="info" sx={{ fontSize: 12 }}>
                                    Comparison with PDF: Verify if the line in the PDF matches the extracted event above.
                                </Alert>
                            </Box>
                        </Box>
                    </Box>
                )}
            </Drawer>

            {/* Phase 3: CONNECTIONS DRILL-DOWN DIALOG */}
            <Dialog
                open={connectionsDrillOpen}
                onClose={() => setConnectionsDrillOpen(false)}
                maxWidth="md"
                fullWidth
                PaperProps={{ sx: { height: '70vh' } }}
            >
                <DialogTitle sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid', borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Typography variant="h6">
                            {selectedProviderCode ? `Raccordements ${selectedProviderCode}` : 'Tous les Raccordements'}
                        </Typography>
                        <Chip label={`${connectionsTotal} sites`} size="small" color="primary" />
                    </Box>
                    <IconButton onClick={() => setConnectionsDrillOpen(false)}><XCircle size={20} /></IconButton>
                </DialogTitle>
                <DialogContent sx={{ display: 'flex', flexDirection: 'column', p: 0 }}>
                    <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
                        <TextField
                            size="small"
                            placeholder="Rechercher code_site ou client..."
                            fullWidth
                            value={connectionsSearch}
                            onChange={(e) => {
                                setConnectionsSearch(e.target.value);
                                fetchConnectionsDrillDown(selectedProviderCode, e.target.value);
                            }}
                            InputProps={{
                                startAdornment: <InputAdornment position="start"><Search size={16} /></InputAdornment>
                            }}
                        />
                    </Box>
                    <Box sx={{ flex: 1, overflow: 'auto' }}>
                        {loadingConnections ? (
                            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
                                <CircularProgress />
                            </Box>
                        ) : (
                            <DataGrid
                                rows={connections}
                                columns={[
                                    { field: 'code_site', headerName: 'Code Site', width: 120 },
                                    { field: 'client_name', headerName: 'Client', flex: 1 },
                                    { field: 'provider_label', headerName: 'Télésurveilleur', width: 130 },
                                    {
                                        field: 'first_seen_at',
                                        headerName: 'Première détection',
                                        width: 160,
                                        valueFormatter: (params: any) => new Date(params.value).toLocaleString()
                                    }
                                ]}
                                density="compact"
                                rowHeight={36}
                                hideFooter
                                disableRowSelectionOnClick
                                sx={{ border: 0 }}
                            />
                        )}
                    </Box>
                </DialogContent>
            </Dialog>

            <Box sx={{ position: 'fixed', bottom: 5, right: 10, opacity: 0.5, pointerEvents: 'none', zIndex: 9999 }}>
                <Chip label={`Build: ${new Date().toISOString().split('T')[0]}`} size="small" variant="outlined" sx={{ fontSize: 10, bgcolor: 'background.paper' }} />
            </Box>
        </Layout>
    );
}

// Suspense wrapper required by Next.js 14 when using useSearchParams()
export default function DataValidationPage() {
    return (
        <React.Suspense fallback={null}>
            <DataValidationInner />
        </React.Suspense>
    );
}
