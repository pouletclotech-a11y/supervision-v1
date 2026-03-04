'use client';

import React, { useState } from 'react';
import Layout from '../../../components/Layout';
import { fetchWithAuth, API_ORIGIN } from '@/lib/api';
import {
    Box,
    Paper,
    Typography,
    Stepper,
    Step,
    StepLabel,
    Button,
    Card,
    CardContent,
    Stack,
    Divider,
    Alert,
    CircularProgress,
    TextField,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    LinearProgress,
    Chip,
    Unstable_Grid2 as Grid
} from '@mui/material';
import {
    Upload,
    Search,
    CheckCircle2,
    AlertTriangle,
    FileCode,
    ArrowRight,
    ArrowLeft,
    Database,
    Clock,
    CheckCircle
} from 'lucide-react';

const steps = ['Upload Sample', 'Auto-Detection', 'Preview Quality', 'Finalize'];

export default function OnboardingWizard() {
    const [activeStep, setActiveStep] = useState(0);
    const [file, setFile] = useState<File | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [previewData, setPreviewData] = useState<any>(null);

    // Final Setup State
    const [providerCode, setProviderCode] = useState('');
    const [providerLabel, setProviderLabel] = useState('');

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setError(null);
        }
    };

    const handleNext = async () => {
        if (activeStep === 0 && !file) {
            setError('Please select a file first.');
            return;
        }

        if (activeStep === 0) {
            // Move to detection
            setLoading(true);
            const formData = new FormData();
            formData.append('file', file!);

            try {
                const res = await fetch(`${API_ORIGIN}/admin/config/onboarding/preview`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('token')}`
                    },
                    body: formData
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Detection failed');
                }

                const data = await res.json();
                setPreviewData(data);

                // Pre-fill labels if possible
                if (data.filename.includes('SPGO')) {
                    setProviderCode('SPGO');
                    setProviderLabel('SPGO Telemonitoring');
                } else if (data.filename.includes('CORS')) {
                    setProviderCode('CORS');
                    setProviderLabel('CORS Security');
                }

                setActiveStep(2); // Skip Step 1 (Detection is instant) to Preview
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        } else if (activeStep === 2) {
            setActiveStep(3);
        } else if (activeStep === 3) {
            handleFinalize();
        }
    };

    const handleBack = () => {
        setActiveStep((prev) => prev - 1);
    };

    const handleFinalize = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_ORIGIN}/admin/config/onboarding/finalize`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('token')}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    provider: {
                        code: providerCode,
                        label: providerLabel,
                        is_active: true
                    },
                    profile: {
                        profile_id: previewData?.profile_matched || `${providerCode.toLowerCase()}_manual`,
                        name: `${providerLabel} Profile`,
                        format_kind: previewData?.detected_kind
                    }
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Finalization failed');
            }

            setActiveStep(4);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    const renderStepContent = (step: number) => {
        switch (step) {
            case 0:
                return (
                    <Box sx={{ py: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <Paper
                            variant="outlined"
                            sx={{
                                p: 6,
                                borderStyle: 'dashed',
                                borderWidth: 2,
                                borderColor: 'divider',
                                width: '100%',
                                maxWidth: 500,
                                textAlign: 'center',
                                bgcolor: 'background.default'
                            }}
                        >
                            <input
                                type="file"
                                id="onboarding-upload"
                                hidden
                                onChange={handleFileChange}
                            />
                            <label htmlFor="onboarding-upload">
                                <Button
                                    variant="contained"
                                    component="span"
                                    startIcon={<Upload size={20} />}
                                    sx={{ mb: 2 }}
                                >
                                    Select Sample File
                                </Button>
                            </label>
                            {file && (
                                <Box sx={{ mt: 2 }}>
                                    <Typography variant="body1" color="primary" fontWeight="bold">
                                        {file.name}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {(file.size / 1024).toFixed(1)} KB
                                    </Typography>
                                </Box>
                            )}
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 3 }}>
                                Accepted: .xls, .xlsx, .pdf (OCR not supported in preview)
                            </Typography>
                        </Paper>
                    </Box>
                );
            case 2:
                const results = previewData?.quality_summary;
                return (
                    <Box sx={{ py: 2 }}>
                        <Grid container spacing={3}>
                            <Grid xs={12} md={4}>
                                <Card sx={{ height: '100%', bgcolor: 'background.paper' }}>
                                    <CardContent>
                                        <Typography variant="h6" gutterBottom>Detection Result</Typography>
                                        <Stack spacing={2}>
                                            <Box>
                                                <Typography variant="caption" color="text.secondary">Kind</Typography>
                                                <Typography variant="body1" sx={{ textTransform: 'uppercase' }}>
                                                    {previewData?.detected_kind}
                                                </Typography>
                                            </Box>
                                            <Box>
                                                <Typography variant="caption" color="text.secondary">Best Profile Match</Typography>
                                                <Typography variant="body1" color="primary">
                                                    {previewData?.profile_matched}
                                                </Typography>
                                            </Box>
                                        </Stack>
                                    </CardContent>
                                </Card>
                            </Grid>
                            <Grid xs={12} md={8}>
                                <Card sx={{ height: '100%' }}>
                                    <CardContent>
                                        <Typography variant="h6" gutterBottom>Quality Indicator</Typography>
                                        <Box sx={{ mt: 2 }}>
                                            <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 1 }}>
                                                <Typography variant="body2">Created Ratio (% Rows Parsed)</Typography>
                                                <Chip
                                                    label={`${(results?.created_ratio * 100).toFixed(0)}%`}
                                                    color={results?.status === 'OK' ? 'success' : results?.status === 'WARN' ? 'warning' : 'error'}
                                                    size="small"
                                                />
                                            </Stack>
                                            <LinearProgress
                                                variant="determinate"
                                                value={results?.created_ratio * 100}
                                                color={results?.status === 'OK' ? 'success' : results?.status === 'WARN' ? 'warning' : 'error'}
                                                sx={{ height: 8, borderRadius: 4 }}
                                            />
                                        </Box>
                                        <Box sx={{ mt: 3 }}>
                                            <Typography variant="caption" color="text.secondary">Skipped Rows: {results?.skipped_count}</Typography>
                                            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                                                {results?.top_reasons?.map((reason: string) => (
                                                    <Chip key={reason} label={reason} size="small" variant="outlined" />
                                                ))}
                                            </Stack>
                                        </Box>
                                    </CardContent>
                                </Card>
                            </Grid>
                            <Grid xs={12}>
                                <TableContainer component={Paper} variant="outlined">
                                    <Table size="small">
                                        <TableHead sx={{ bgcolor: 'action.hover' }}>
                                            <TableRow>
                                                <TableCell>Preview Events (Max 5)</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {previewData?.sample_events?.map((evt: any, idx: number) => (
                                                <TableRow key={idx}>
                                                    <TableCell sx={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                                                        {JSON.stringify(evt)}
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                            {(!previewData?.sample_events || previewData.sample_events.length === 0) && (
                                                <TableRow>
                                                    <TableCell align="center">No events detected</TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Grid>
                        </Grid>
                    </Box>
                );
            case 3:
                return (
                    <Box sx={{ py: 4, maxWidth: 600, mx: 'auto' }}>
                        <Paper variant="outlined" sx={{ p: 4 }}>
                            <Typography variant="h6" gutterBottom>Final Provider Mapping</Typography>
                            <Stack spacing={3} sx={{ mt: 2 }}>
                                <TextField
                                    fullWidth
                                    label="Provider Code"
                                    placeholder="ex: SPGO, CORS, etc."
                                    value={providerCode}
                                    onChange={(e) => setProviderCode(e.target.value.toUpperCase())}
                                    helperText="Unique uppercase identifier"
                                />
                                <TextField
                                    fullWidth
                                    label="Provider Label"
                                    placeholder="Friendly Name"
                                    value={providerLabel}
                                    onChange={(e) => setProviderLabel(e.target.value)}
                                />
                                <Alert icon={<InfoIcon fontSize="inherit" />} severity="info">
                                    Clicking <b>Finish</b> will create this provider and link the matched profile to it.
                                </Alert>
                            </Stack>
                        </Paper>
                    </Box>
                );
            case 4:
                return (
                    <Box sx={{ py: 10, textAlign: 'center' }}>
                        <CheckCircle size={80} color="#2e7d32" style={{ marginBottom: 24 }} />
                        <Typography variant="h4" gutterBottom>Onboarding Complete!</Typography>
                        <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                            The new provider and profile have been successfully configured.
                        </Typography>
                        <Button variant="contained" href="/admin/providers">
                            Go to Providers
                        </Button>
                    </Box>
                );
            default:
                return null;
        }
    };

    return (
        <Layout>
            <Box sx={{ p: 4 }}>
                <Typography variant="h4" gutterBottom fontWeight="bold">
                    Provider Onboarding Wizard
                </Typography>
                <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
                    Guide to add a new monitoring provider by uploading a data sample.
                </Typography>

                <Paper sx={{ p: 4, borderRadius: 3 }}>
                    <Stepper activeStep={activeStep === 4 ? 4 : activeStep} sx={{ mb: 5 }}>
                        {steps.map((label) => (
                            <Step key={label}>
                                <StepLabel>{label}</StepLabel>
                            </Step>
                        ))}
                    </Stepper>

                    {error && (
                        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
                            {error}
                        </Alert>
                    )}

                    {loading ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', py: 10 }}>
                            <CircularProgress sx={{ mb: 2 }} />
                            <Typography variant="body2" color="text.secondary">Analyzing data structure...</Typography>
                        </Box>
                    ) : (
                        renderStepContent(activeStep)
                    )}

                    {activeStep < 4 && !loading && (
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 4, pt: 2, borderTop: '1px solid', borderColor: 'divider' }}>
                            <Button
                                disabled={activeStep === 0}
                                onClick={handleBack}
                                startIcon={<ArrowLeft size={18} />}
                                sx={{ mr: 1 }}
                            >
                                Back
                            </Button>
                            <Button
                                variant="contained"
                                onClick={handleNext}
                                endIcon={activeStep === 3 ? <CheckCircle2 size={18} /> : <ArrowRight size={18} />}
                            >
                                {activeStep === 3 ? 'Finish' : 'Next'}
                            </Button>
                        </Box>
                    )}
                </Paper>
            </Box>
        </Layout>
    );
}

function InfoIcon(props: any) {
    return <AlertTriangle {...props} />;
}
