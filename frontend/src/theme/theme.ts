'use client';

import { createTheme } from '@mui/material/styles';
import { Inter } from 'next/font/google';

// Use Next.js font optimization
const inter = Inter({
    weight: ['300', '400', '500', '600', '700'],
    subsets: ['latin'],
    display: 'swap',
});

// STITCH DESIGN TOKENS
export const stitchColors = {
    primary: '#197fe6',      // Blue Azure (from reference)
    background: '#0B0F14',   // Deep Black/Blue
    card: '#161B22',         // Dark Card Surface
    border: '#1f2937',       // Gray 800
    textPrimary: '#f3f4f6',  // Gray 100
    textSecondary: '#9ca3af', // Gray 400
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#0ea5e9',
};

const theme = createTheme({
    palette: {
        mode: 'dark',
        primary: {
            main: stitchColors.primary,
        },
        background: {
            default: stitchColors.background,
            paper: stitchColors.card,
        },
        text: {
            primary: stitchColors.textPrimary,
            secondary: stitchColors.textSecondary,
        },
        divider: stitchColors.border,
        success: { main: stitchColors.success },
        warning: { main: stitchColors.warning },
        error: { main: stitchColors.error },
        info: { main: stitchColors.info },
    },
    typography: {
        fontFamily: inter.style.fontFamily,
        fontSize: 12, // High density base
        h1: { fontSize: '1.5rem', fontWeight: 600, letterSpacing: '-0.02em' }, // 24px
        h2: { fontSize: '1.25rem', fontWeight: 600, letterSpacing: '-0.01em' }, // 20px
        h6: { fontSize: '1rem', fontWeight: 600 }, // 16px
        subtitle1: { fontSize: '0.875rem', fontWeight: 600 }, // 14px
        button: { textTransform: 'none', fontWeight: 500 },
    },
    shape: {
        borderRadius: 8, // Rounded-lg/xl look
    },
    components: {
        MuiCssBaseline: {
            styleOverrides: {
                body: {
                    backgroundColor: stitchColors.background,
                    scrollbarWidth: 'thin',
                    '&::-webkit-scrollbar': {
                        width: '6px',
                        height: '6px',
                    },
                    '&::-webkit-scrollbar-track': {
                        background: stitchColors.background,
                    },
                    '&::-webkit-scrollbar-thumb': {
                        backgroundColor: '#374151',
                        borderRadius: '10px',
                    },
                },
            },
        },
        // Customize Paper to look like Stitch Cards
        MuiPaper: {
            styleOverrides: {
                root: {
                    backgroundImage: 'none',
                    backgroundColor: stitchColors.card,
                    border: `1px solid ${stitchColors.border}`,
                    borderRadius: 12, // rounded-xl usually
                },
                rounded: {
                    borderRadius: 12,
                },
            },
            defaultProps: {
                elevation: 0,
            }
        },
        // DataGrid customizations for "High Density" look
        MuiDataGrid: {
            styleOverrides: {
                root: {
                    border: 'none',
                    '--DataGrid-rowBorderColor': stitchColors.border,
                },
                columnHeaders: {
                    backgroundColor: '#1f2937', // Slightly lighter than card
                    borderBottom: `1px solid ${stitchColors.border}`,
                    textTransform: 'uppercase',
                    fontSize: '0.65rem',
                    fontWeight: 700,
                    color: stitchColors.textSecondary,
                    letterSpacing: '0.05em',
                },
                row: {
                    fontSize: '0.75rem', // 12px
                    '&:hover': {
                        backgroundColor: 'rgba(25, 127, 230, 0.08)', // Primary tint
                    },
                },
                cell: {
                    borderBottom: `1px solid ${stitchColors.border}`,
                },
                footerContainer: {
                    borderTop: `1px solid ${stitchColors.border}`,
                },
            },
        },
        // Chips like "Status Pills"
        MuiChip: {
            styleOverrides: {
                root: {
                    fontWeight: 600,
                    fontSize: '0.7rem',
                    height: 24,
                },
                filled: {
                    border: '1px solid transparent',
                },
                sizeSmall: {
                    height: 20,
                    fontSize: '0.65rem',
                }
            },
        },
        // Buttons
        MuiButton: {
            styleOverrides: {
                root: {
                    borderRadius: 8,
                    boxShadow: 'none',
                },
                containedPrimary: {
                    background: `linear-gradient(135deg, ${stitchColors.primary} 0%, #1d4ed8 100%)`, // Subtle gradient
                    '&:hover': {
                        boxShadow: '0 4px 12px rgba(25, 127, 230, 0.3)',
                    }
                }
            }
        }
    },
});

export default theme;
