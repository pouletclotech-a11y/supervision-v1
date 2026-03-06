'use client';

import React, { useState, useEffect } from 'react';
import {
    Box, Typography, Paper, Button, Grid, Select, MenuItem, InputLabel, FormControl,
    CircularProgress, Alert, Card, CardContent, Divider, Chip, FormControlLabel, Checkbox
} from '@mui/material';
import { Upload, FileText, CheckCircle2, AlertCircle, ExternalLink, Activity } from 'lucide-react';
import Layout from '../../../components/Layout';
import { fetchWithAuth } from '../../../lib/api';
import { useRouter } from 'next/navigation';

interface Provider {
    id: number;
    code: string;
    label: string;
}

interface TestIngestResult {
    import_id: number;
    security_count: number;
    operator_count: number;
    total_count: number;
    time_null: number;
    pdf_match_ratio: number;
    status: string;
}

export default function TestIngestPage() {
    const router = useRouter();
    const [providers, setProviders] = useState<Provider[]>([]);
    const [loadingProviders, setLoadingProviders] = useState(true);
    const [selectedProvider, setSelectedProvider] = useState('');
    const [excelFile, setExcelFile] = useState<File | null>(null);
    const [pdfFile, setPdfFile] = useState<File | null>(null);
    const [strictBaseline, setStrictBaseline] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<TestIngestResult | null>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        const loadProviders = async () => {
            try {
                const res = await fetchWithAuth('/admin/providers');
                if (res.ok) {
                    const data = await res.json();
                    setProviders(data.filter((p: any) => p.is_active));
                }
            } catch (err) {
                console.error("Failed to load providers", err);
            } finally {
                setLoadingProviders(false);
            }
        };
        loadProviders();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedProvider || !excelFile) {
            setError('Provider et fichier Excel requis');
            return;
        }

        setSubmitting(true);
        setError('');
        setResult(null);

        const formData = new FormData();
        formData.append('provider_code', selectedProvider);
        formData.append('excel_file', excelFile);
        if (pdfFile) formData.append('pdf_file', pdfFile);
        formData.append('strict_baseline', strictBaseline.toString());

        try {
            const res = await fetchWithAuth('/admin/test-ingest', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || 'Erreur lors de l\'ingestion');
            }

            const data = await res.json();
            setResult(data);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <Layout>
            <Box sx={{ p: 4, maxWidth: 800, mx: 'auto' }}>
                <Typography variant="h4" fontWeight={700} gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Activity size={32} /> Admin Test Ingest
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                    Outil d'ingestion forcée pour valider les parsers et le matching PDF.
                    Les imports créés auront le statut <code>MANUAL_VALIDATION</code>.
                </Typography>

                <Paper sx={{ p: 3, borderRadius: 3, mb: 4 }}>
                    <form onSubmit={handleSubmit}>
                        <Grid container spacing={3}>
                            <Grid item xs={12}>
                                <FormControl fullWidth required>
                                    <InputLabel>Provider</InputLabel>
                                    <Select
                                        value={selectedProvider}
                                        label="Provider"
                                        onChange={(e) => setSelectedProvider(e.target.value)}
                                        disabled={loadingProviders || submitting}
                                    >
                                        {providers.map(p => (
                                            <MenuItem key={p.id} value={p.code}>{p.label} ({p.code})</MenuItem>
                                        ))}
                                    </Select>
                                </FormControl>
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <Typography variant="subtitle2" gutterBottom>Fichier Excel/TSV (Requis)</Typography>
                                <Button
                                    variant="outlined"
                                    component="label"
                                    fullWidth
                                    startIcon={<FileText size={18} />}
                                    color={excelFile ? "success" : "primary"}
                                    disabled={submitting}
                                >
                                    {excelFile ? excelFile.name : 'Choisir Excel'}
                                    <input type="file" hidden accept=".xls,.xlsx,.tsv" onChange={(e) => setExcelFile(e.target.files?.[0] || null)} />
                                </Button>
                            </Grid>

                            <Grid item xs={12} sm={6}>
                                <Typography variant="subtitle2" gutterBottom>Fichier PDF (Optionnel)</Typography>
                                <Button
                                    variant="outlined"
                                    component="label"
                                    fullWidth
                                    startIcon={<FileText size={18} />}
                                    color={pdfFile ? "success" : "primary"}
                                    disabled={submitting}
                                >
                                    {pdfFile ? pdfFile.name : 'Choisir PDF'}
                                    <input type="file" hidden accept=".pdf" onChange={(e) => setPdfFile(e.target.files?.[0] || null)} />
                                </Button>
                            </Grid>

                            <Grid item xs={12}>
                                <FormControlLabel
                                    control={<Checkbox checked={strictBaseline} onChange={(e) => setStrictBaseline(e.target.checked)} />}
                                    label="Strict Baseline (Vérifier 157 sécu / 162 notes)"
                                    disabled={submitting || selectedProvider !== 'SPGO'}
                                />
                            </Grid>

                            <Grid item xs={12}>
                                <Button
                                    type="submit"
                                    variant="contained"
                                    fullWidth
                                    size="large"
                                    disabled={submitting || !selectedProvider || !excelFile}
                                    startIcon={submitting ? <CircularProgress size={20} color="inherit" /> : <Upload size={20} />}
                                >
                                    Lancer l'Ingestion de Test
                                </Button>
                            </Grid>
                        </Grid>
                    </form>
                </Paper>

                {error && <Alert severity="error" sx={{ mb: 4, borderRadius: 2 }}>{error}</Alert>}

                {result && (
                    <Card sx={{ borderRadius: 3, border: '1px solid', borderColor: result.status === 'SUCCESS' ? 'success.main' : 'warning.main' }}>
                        <CardContent>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                <Typography variant="h6" fontWeight={700}>Résultats de l'Import #{result.import_id}</Typography>
                                <Chip
                                    label={result.status}
                                    color={result.status === 'SUCCESS' ? 'success' : 'warning'}
                                    icon={result.status === 'SUCCESS' ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
                                />
                            </Box>

                            <Divider sx={{ my: 2 }} />

                            <Grid container spacing={2}>
                                <Grid item xs={6} sm={3}>
                                    <Typography variant="caption" color="text.secondary">Sécurité</Typography>
                                    <Typography variant="h5" fontWeight={700}>{result.security_count}</Typography>
                                </Grid>
                                <Grid item xs={6} sm={3}>
                                    <Typography variant="caption" color="text.secondary">Opérateur</Typography>
                                    <Typography variant="h5" fontWeight={700}>{result.operator_count}</Typography>
                                </Grid>
                                <Grid item xs={6} sm={3}>
                                    <Typography variant="caption" color="text.secondary">Total</Typography>
                                    <Typography variant="h5" fontWeight={700}>{result.total_count}</Typography>
                                </Grid>
                                <Grid item xs={6} sm={3}>
                                    <Typography variant="caption" color="text.secondary">Time Null</Typography>
                                    <Typography variant="h5" fontWeight={700} color={result.time_null > 0 ? 'error.main' : 'inherit'}>
                                        {result.time_null}
                                    </Typography>
                                </Grid>
                            </Grid>

                            <Box sx={{ mt: 3, p: 2, bgcolor: 'action.hover', borderRadius: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    <FileText size={20} />
                                    <Typography variant="body2" fontWeight={600}>PDF Match Ratio</Typography>
                                </Box>
                                <Typography variant="h6" fontWeight={700}>{(result.pdf_match_ratio * 100).toFixed(2)}%</Typography>
                            </Box>

                            <Button
                                variant="outlined"
                                fullWidth
                                sx={{ mt: 3 }}
                                startIcon={<ExternalLink size={18} />}
                                onClick={() => router.push(`/admin/data-validation?import_id=${result.import_id}`)}
                            >
                                Ouvrir dans Data Validation
                            </Button>
                        </CardContent>
                    </Card>
                )}
            </Box>
        </Layout>
    );
}
