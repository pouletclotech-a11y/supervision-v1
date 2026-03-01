'use client';

import React, { useState } from 'react';
import {
    Box,
    Drawer,
    AppBar,
    Toolbar,
    Typography,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    IconButton,
    Avatar,
    Badge,
    useTheme
} from '@mui/material';
import {
    LayoutDashboard,
    FileText,
    ShieldAlert,
    Settings,
    Menu,
    Bell,
    Search,
    ChevronLeft,
    Users,
    Database,
    Zap
} from 'lucide-react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '../context/AuthContext';
import { API_ORIGIN } from '@/lib/api';
import ClientReportPanel from './ClientReportPanel';
import { InputBase, Paper } from '@mui/material';

const DRAWER_WIDTH = 240;
const COLLAPSED_WIDTH = 72;

interface LayoutProps {
    children?: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
    const [open, setOpen] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [reportOpen, setReportOpen] = useState(false);
    const [reportSiteCode, setReportSiteCode] = useState<string | null>(null);
    const router = useRouter();
    const pathname = usePathname();
    const theme = useTheme();
    const { user, logout } = useAuth();

    const toggleDrawer = () => setOpen(!open);

    const menuItems = [
        { text: 'Dashboard', icon: <LayoutDashboard size={20} />, path: '/' },
        { text: 'Validations', icon: <FileText size={20} />, path: '/admin/data-validation' },
        { text: 'Alerts', icon: <ShieldAlert size={20} />, path: '/admin/alerts' },
        { text: 'Providers', icon: <Zap size={20} />, path: '/admin/providers', roles: ['ADMIN'] },
        { text: 'Calibration', icon: <Database size={20} />, path: '/admin/calibration', roles: ['ADMIN'] },
        { text: 'Imports', icon: <Database size={20} />, path: '/admin/imports', roles: ['ADMIN', 'OPERATOR'] },
        { text: 'Users', icon: <Users size={20} />, path: '/admin/users', roles: ['ADMIN'] },
        { text: 'Settings', icon: <Settings size={20} />, path: '/settings', roles: ['ADMIN', 'OPERATOR'] },
    ];

    const filteredMenuItems = menuItems.filter(item => !item.roles || (user && item.roles.includes(user.role)));

    return (
        <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>

            {/* SIDEBAR */}
            <Drawer
                variant="permanent"
                sx={{
                    width: open ? DRAWER_WIDTH : COLLAPSED_WIDTH,
                    flexShrink: 0,
                    '& .MuiDrawer-paper': {
                        width: open ? DRAWER_WIDTH : COLLAPSED_WIDTH,
                        boxSizing: 'border-box',
                        transition: theme.transitions.create('width', {
                            easing: theme.transitions.easing.sharp,
                            duration: theme.transitions.duration.enteringScreen,
                        }),
                        bgcolor: 'background.paper',
                        borderRight: '1px solid',
                        borderColor: 'divider',
                        overflowX: 'hidden',
                    },
                }}
            >
                {/* LOGO AREA */}
                <Box sx={{
                    height: 64,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: open ? 'space-between' : 'center',
                    px: 2,
                    borderBottom: '1px solid',
                    borderColor: 'divider'
                }}>
                    {open && (
                        <Typography variant="h6" sx={{ fontWeight: 700, background: `-webkit-linear-gradient(45deg, #197fe6, #fff)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                            SUPERVISION
                        </Typography>
                    )}
                    <IconButton onClick={toggleDrawer} size="small" sx={{ color: 'text.secondary' }}>
                        {open ? <ChevronLeft size={18} /> : <Menu size={18} />}
                    </IconButton>
                </Box>

                {/* MENU */}
                <List sx={{ pt: 2 }}>
                    {filteredMenuItems.map((item) => {
                        const isActive = pathname === item.path;
                        return (
                            <ListItem key={item.text} disablePadding sx={{ display: 'block', mb: 0.5 }}>
                                <ListItemButton
                                    onClick={() => router.push(item.path)}
                                    sx={{
                                        minHeight: 48,
                                        justifyContent: open ? 'initial' : 'center',
                                        px: 2.5,
                                        mx: 1,
                                        borderRadius: 2,
                                        bgcolor: isActive ? 'rgba(25, 127, 230, 0.12)' : 'transparent',
                                        color: isActive ? 'primary.main' : 'text.secondary',
                                        '&:hover': {
                                            bgcolor: isActive ? 'rgba(25, 127, 230, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                                            color: 'text.primary',
                                        }
                                    }}
                                >
                                    <ListItemIcon
                                        sx={{
                                            minWidth: 0,
                                            mr: open ? 2 : 'auto',
                                            justifyContent: 'center',
                                            color: 'inherit'
                                        }}
                                    >
                                        {item.icon}
                                    </ListItemIcon>
                                    <ListItemText primary={item.text} sx={{ opacity: open ? 1 : 0 }} />
                                </ListItemButton>
                            </ListItem>
                        );
                    })}
                </List>
            </Drawer>

            {/* MAIN CONTENT WRAPPER */}
            <Box component="main" sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>

                {/* TOPBAR */}
                <Box sx={{
                    height: 64,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    display: 'flex',
                    alignItems: 'center',
                    px: 3,
                    bgcolor: 'background.default',
                    justifyContent: 'space-between'
                }}>
                    {/* Breadcrumb / Search */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 3, flexGrow: 1, ml: 2 }}>
                        <Typography variant="subtitle1" sx={{ color: 'text.primary', fontWeight: 600, display: { xs: 'none', lg: 'block' } }}>
                            {menuItems.find(i => i.path === pathname)?.text || 'Overview'}
                        </Typography>

                        <Paper
                            component="form"
                            onSubmit={(e) => {
                                e.preventDefault();
                                const site = searchQuery.trim();
                                if (!/^\d+$/.test(site)) {
                                    alert("Site Code must be digits only (ex: 69000).");
                                    return;
                                }
                                router.push(`/client/${site}`);
                                setSearchQuery('');
                            }}
                            sx={{
                                p: '2px 4px',
                                display: 'flex',
                                alignItems: 'center',
                                width: 300,
                                bgcolor: 'rgba(255, 255, 255, 0.05)',
                                border: '1px solid',
                                borderColor: 'divider',
                                borderRadius: 2,
                                boxShadow: 'none'
                            }}
                        >
                            <IconButton sx={{ p: '10px' }} aria-label="menu">
                                <Search size={18} />
                            </IconButton>
                            <InputBase
                                sx={{ ml: 1, flex: 1, fontSize: '0.875rem' }}
                                placeholder="Quick Site Search (ex: 69000)"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                            />
                        </Paper>
                    </Box>

                    {/* User / Actions */}
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        {user && (
                            <Box sx={{ textAlign: 'right', mr: 1 }}>
                                <Typography variant="body2" sx={{ fontWeight: 600, color: 'text.primary' }}>{user.email}</Typography>
                                <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 'bold' }}>{user.role}</Typography>
                            </Box>
                        )}
                        <IconButton size="small" sx={{ color: 'text.secondary' }}>
                            <Badge badgeContent={3} color="error" variant="dot">
                                <Bell size={20} />
                            </Badge>
                        </IconButton>
                        <Avatar
                            src={user?.profile_photo ? (
                                user.profile_photo.startsWith('http')
                                    ? user.profile_photo
                                    : `${API_ORIGIN}${user.profile_photo}`
                            ) : undefined}
                            sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: 12, cursor: 'pointer' }}
                            onClick={logout}
                        >
                            {user?.email?.[0]?.toUpperCase() || 'U'}
                        </Avatar>
                    </Box>
                </Box>

                {/* PAGE CONTENT */}
                <Box sx={{ flexGrow: 1, overflow: 'auto', p: 0 }}>
                    {children}
                </Box>
            </Box>

            <ClientReportPanel
                siteCode={reportSiteCode}
                open={reportOpen}
                onClose={() => setReportOpen(false)}
            />
        </Box>
    );
}
