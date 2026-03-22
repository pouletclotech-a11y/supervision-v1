'use client';

import React from 'react';
import Layout from '@/components/Layout';
import CodeCatalogPanel from '@/components/CodeCatalogPanel';
import { Box, Container } from '@mui/material';

export default function CatalogPage() {
    return (
        <Layout>
            <Box 
                sx={{ 
                    p: { xs: 2, md: 4 }, 
                    bgcolor: 'background.default', 
                    minHeight: '100%',
                    display: 'flex',
                    flexDirection: 'column'
                }}
            >
                <Container maxWidth="xl" sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
                    <CodeCatalogPanel />
                </Container>
            </Box>
        </Layout>
    );
}
