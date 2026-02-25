import React, { useState } from 'react';
import {
    Box,
    TextField,
    Button,
    Typography,
    Alert,
    Chip,
    Divider,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Stack
} from '@mui/material';
import { Play, CheckCircle, XCircle, FileText } from 'lucide-react';
import { fetchWithAuth } from '@/lib/api';

export default function RuleTester() {
    // RULE DEFINITION STATE
    const [conditionType, setConditionType] = useState('KEYWORD');
    const [value, setValue] = useState('');
    const [scopeSite, setScopeSite] = useState('');

    // INPUT STATE
    const [text, setText] = useState('');

    // RESULT STATE
    const [result, setResult] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleLoadSample = (type: string) => {
        if (type === 'valid') {
            setText("2024-03-24 10:00:00 [CRITICAL] Sensor C-69000 failure detected");
        }
    };

    const handleTest = async () => {
        if (!value || !text) return;
        setLoading(true);
        setError(null);
        setResult(null);

        const rulePayload = {
            name: "TEST_RULE",
            condition_type: conditionType,
            value: value,
            scope_site_code: scopeSite || null,
            frequency_count: 1,
            frequency_window: 0,
            email_notify: false,
            is_active: true
        };

        try {
            const res = await fetchWithAuth(`/alerts/rules/test?sample_text=${encodeURIComponent(text)}`, {
                method: 'POST',
                body: JSON.stringify(rulePayload)
            });

            if (!res.ok) throw new Error("API Error");

            const data = await res.json();
            setResult(data);
        } catch (err) {
            console.error(err);
            setError("Test failed. Check inputs or API status.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Box sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box>
                <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
                    DEFINE TEMPORARY RULE
                </Typography>
                <Stack spacing={2}>
                    <FormControl size="small" fullWidth>
                        <InputLabel>Condition Type</InputLabel>
                        <Select
                            value={conditionType}
                            label="Condition Type"
                            onChange={(e) => setConditionType(e.target.value)}
                        >
                            <MenuItem value="KEYWORD">Keyword (Contains)</MenuItem>
                            <MenuItem value="SEVERITY">Severity (Equals)</MenuItem>
                        </Select>
                    </FormControl>

                    <TextField
                        label="Value / Pattern"
                        size="small"
                        fullWidth
                        value={value}
                        onChange={(e) => setValue(e.target.value)}
                        placeholder={conditionType === 'SEVERITY' ? 'e.g. CRITICAL' : 'e.g. Failure'}
                    />

                    <TextField
                        label="Scope Site Code (Optional)"
                        size="small"
                        fullWidth
                        value={scopeSite}
                        onChange={(e) => setScopeSite(e.target.value)}
                        placeholder="e.g. C-69000"
                    />
                </Stack>
            </Box>

            <Divider />

            <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="caption" color="text.secondary">SAMPLE INPUT</Typography>
                    <Button
                        size="small"
                        startIcon={<FileText size={14} />}
                        onClick={() => handleLoadSample('valid')}
                        sx={{ fontSize: 10 }}
                    >
                        Load Sample
                    </Button>
                </Box>
                <TextField
                    label="Log Line or Event Message"
                    variant="outlined"
                    fullWidth
                    multiline
                    rows={3}
                    size="small"
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Paste a raw event line here..."
                    sx={{ fontFamily: 'monospace' }}
                />
            </Box>

            <Button
                variant="contained"
                startIcon={<Play size={16} />}
                onClick={handleTest}
                disabled={loading || !value || !text}
                fullWidth
            >
                {loading ? 'Testing...' : 'Test Match'}
            </Button>

            {error && <Alert severity="error">{error}</Alert>}

            {result && (
                <Box sx={{ mt: 1, p: 2, bgcolor: result.matched ? '#f0fdf4' : '#fef2f2', borderRadius: 1, border: '1px solid', borderColor: result.matched ? 'success.light' : 'error.light' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>RESULT:</Typography>
                        {result.matched ? (
                            <Chip icon={<CheckCircle size={16} />} label="MATCHED" color="success" size="small" variant="filled" />
                        ) : (
                            <Chip icon={<XCircle size={16} />} label="NO MATCH" color="error" size="small" variant="filled" />
                        )}
                    </Box>

                    <Divider sx={{ my: 1 }} />

                    <Stack spacing={0.5}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="caption" color="text.secondary">Site Detected:</Typography>
                            <Typography variant="caption" fontWeight="bold">{result.detected_site || 'N/A'}</Typography>
                        </Box>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                            <Typography variant="caption" color="text.secondary">Rule Name:</Typography>
                            <Typography variant="caption">{result.rule_name}</Typography>
                        </Box>
                    </Stack>
                </Box>
            )}
        </Box>
    );
}
