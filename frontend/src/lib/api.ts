import { redirect } from 'next/navigation';

const getBaseUrl = (): string => {
    let url = process.env.NEXT_PUBLIC_API_URL;

    // Cas où la variable est absente ou littéralement "undefined"/"null" (bug JS fréquent)
    if (!url || url === 'undefined' || url === 'null' || url === '') {
        return 'http://localhost:8000';
    }

    // Si l'URL commence par localhost sans protocole, on ajoute http://
    if (url.startsWith('localhost')) {
        url = `http://${url}`;
    }

    // Nettoyage : suppression de /api/v1 final s'il a été mis par erreur dans l'env
    url = url.replace(/\/api\/v1\/?$/, '');

    // Nettoyage : suppression du trailing slash
    url = url.replace(/\/$/, '');

    // Sécurité ultime : si après tous les nettoyages l'URL est vide ou juste "/", on force localhost:8000
    if (!url || url === '/') {
        return 'http://localhost:8000';
    }

    return url;
};

const API_BASE_URL = getBaseUrl();
export const API_ORIGIN = API_BASE_URL; // Pour les avatars et assets statiques
const API_V1_PREFIX = '/api/v1';

/**
 * Construit l'URL complète avec protection contre les double slashes.
 */
const buildUrl = (endpoint: string) => {
    let cleanEndpoint = endpoint.trim();
    if (!cleanEndpoint.startsWith('/')) cleanEndpoint = '/' + cleanEndpoint;

    const url = `${API_BASE_URL}${API_V1_PREFIX}${cleanEndpoint}`;

    // En développement, on loggue pour débogage
    if (process.env.NODE_ENV === 'development') {
        console.debug(`[API Call] ${url}`);
    }

    return url;
};

/**
 * Appel API public (ex: Login).
 * Garanti SANS headers d'autorisation et SANS logique de refresh automatique.
 */
export const fetchPublic = async (endpoint: string, options: RequestInit = {}) => {
    const url = buildUrl(endpoint);
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...options.headers as Record<string, string>,
    };
    // Sécurité : suppression explicite de Authorization si présent par erreur dans options
    delete headers['Authorization'];

    return fetch(url, { ...options, headers });
};

export const fetchWithAuth = async (endpoint: string, options: RequestInit = {}) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

    const headers: Record<string, string> = {
        ...options.headers as Record<string, string>,
    };

    if (!(options.body instanceof FormData) && !headers['Content-Type']) {
        headers['Content-Type'] = 'application/json';
    }

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const url = buildUrl(endpoint);
    const response = await fetch(url, { ...options, headers });

    if (response.status === 401) {
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
