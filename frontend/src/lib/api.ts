import { redirect } from 'next/navigation';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export const fetchWithAuth = async (endpoint: string, options: RequestInit = {}) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

    // Ensure HEADERS object exists
    const headers: Record<string, string> = {
        ...options.headers as Record<string, string>,
    };

    // Only set application/json if not sending FormData
    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        ...options,
        headers,
    };

    // Clean endpoint (handle leading slash)
    const url = `${API_URL}${endpoint.startsWith('/') ? endpoint : '/' + endpoint}`;

    const response = await fetch(url, config);

    // Global Error Handling
    if (response.status === 401) {
        // Token expired or invalid
        if (typeof window !== 'undefined') {
            const currentPath = window.location.pathname;
            if (currentPath !== '/login') {
                localStorage.removeItem('access_token');
                window.location.href = '/login';
            }
        }
    }

    return response;
};
