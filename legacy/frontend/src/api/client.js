// client.js — unified HTTP client for local FastAPI (:8002)
const BASE_URL = 'http://localhost:8002';
const BASE = BASE_URL;

let _apiKey = null;

export async function getApiKey() {
  if (_apiKey) return _apiKey;
  // Bootstrap: fetch key from the unauthenticated /auth/key endpoint
  try {
    const res = await fetch(`${BASE_URL}/auth/key`);
    if (res.ok) {
      const data = await res.json();
      _apiKey = data.api_key;
      return _apiKey;
    }
  } catch (e) {
    console.warn('Could not fetch API key:', e);
  }
  return _apiKey || '';
}

export async function apiFetch(path, options = {}) {
  const key = await getApiKey();
  const headers = {
    ...(options.headers || {}),
  };
  if (key) {
    headers['X-API-Key'] = key;
  }
  const url = path.startsWith('http') ? path : `${BASE_URL}${path}`;
  return fetch(url, { ...options, headers });
}

export async function apiGet(path, params = {}) {
  const key = await getApiKey();
  const url = new URL(path.startsWith('http') ? path : `${BASE_URL}${path}`);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) {
      url.searchParams.set(k, v);
    }
  });
  return fetch(url.toString(), {
    headers: { 'X-API-Key': key, 'Content-Type': 'application/json' },
  });
}

export async function apiPost(path, body = {}) {
  const key = await getApiKey();
  return fetch(path.startsWith('http') ? path : `${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'X-API-Key': key, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function apiStream(path, body = {}) {
  // For SSE: pass key as query param since EventSource can't set headers
  const key = await getApiKey();
  const url = new URL(path.startsWith('http') ? path : `${BASE_URL}${path}`);
  if (key) {
    url.searchParams.set('api_key', key);
  }
  return fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export const api = {
  // Chat
  sendMessage: async (chatId, message, fileIds = []) => {
    const res = await apiPost('/chat/send', {
      message,
      chat_id: chatId,
      file_ids: fileIds,
      use_rag: true,
      collection: 'sources',
      stream: false,
    });
    return res.json();
  },

  getSources: async () => {
    try {
      const res = await apiGet('/chat/sources');
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : data.sources || [];
    } catch (err) {
      console.warn('api.getSources failed, returning empty:', err);
      return [];
    }
  },

  uploadSource: async (file) => {
    const key = await getApiKey();
    const fd = new FormData();
    fd.append('file', file);
    const headers = {};
    if (key) headers['X-API-Key'] = key;
    const res = await fetch(`${BASE_URL}/chat/upload-source`, {
      method: 'POST',
      headers,
      body: fd,
    });
    if (!res.ok) {
      throw new Error(`Upload failed with status ${res.status}`);
    }
    return res.json();
  },

  deleteSource: async (sourceId) => {
    try {
      const key = await getApiKey();
      const res = await fetch(`${BASE_URL}/chat/sources/${sourceId}`, {
        method: 'DELETE',
        headers: key ? { 'X-API-Key': key } : {},
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('api.deleteSource backend call failed:', err);
    }
    return { status: 'ok', deleted: sourceId };
  },

  getChatHistory: async (chatId) => {
    try {
      const res = await apiGet(`/chat/history/${chatId}`);
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : data.messages || [];
    } catch (err) {
      console.warn('api.getChatHistory failed:', err);
      return [];
    }
  },

  createNewChat: async () => {
    try {
      const res = await apiPost('/chat/new');
      if (res.ok) {
        const data = await res.json();
        if (data && (data.chat_id || data.id)) {
          return data.chat_id || data.id;
        }
      }
    } catch (_) {}
    return 'chat-' + Date.now() + '-' + Math.random().toString(36).substring(2, 7);
  },

  getChats: async () => {
    try {
      const res = await apiGet('/chat/chats');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) return data;
      }
    } catch (_) {}
    return null;
  },

  deleteChat: async (chatId) => {
    try {
      const key = await getApiKey();
      await fetch(`${BASE_URL}/chat/${chatId}`, {
        method: 'DELETE',
        headers: key ? { 'X-API-Key': key } : {},
      });
    } catch (_) {}
    return { status: 'ok', deleted: chatId };
  },

  // Graph
  getGraph: async () => {
    try {
      const res = await apiGet('/graph/visualize', { format: 'json' });
      if (!res.ok) return null;
      return await res.json();
    } catch (err) {
      console.warn('api.getGraph failed:', err);
      return null;
    }
  },

  getGraphHtml: async () => {
    try {
      const res = await apiGet('/graph/visualize', { format: 'html' });
      if (!res.ok) return null;
      return await res.text();
    } catch (err) {
      console.warn('api.getGraphHtml failed:', err);
      return null;
    }
  },

  buildGraph: async () => {
    const res = await apiPost('/build-graph');
    if (!res.ok) {
      throw new Error(`Build graph failed with status ${res.status}`);
    }
    return res.json();
  },

  // Curriculum
  getCurriculum: async () => {
    try {
      const res = await apiGet('/curriculum');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data) && data.length > 0) return data;
      }
    } catch (_) {}

    try {
      const res2 = await apiGet('/generate-curriculum');
      if (res2.ok) {
        const data2 = await res2.json();
        if (Array.isArray(data2)) return data2;
        if (data2 && Array.isArray(data2.chapters)) return data2.chapters;
      }
    } catch (_) {}

    return null;
  },

  generateCurriculum: async () => {
    const res = await apiPost('/generate-curriculum');
    if (!res.ok) {
      throw new Error(`Generate curriculum failed with status ${res.status}`);
    }
    return res.json();
  },

  checkHealth: async () => {
    try {
      const res = await fetch(`${BASE_URL}/health`);
      return res.ok;
    } catch (_) {
      return false;
    }
  },
};

export default api;
