import { create } from 'zustand';
import type { User } from '@/types';
import { authApi } from '@/services/api';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (name: string, email: string, password: string, role: 'consultant' | 'owner') => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  loadUser: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  token: localStorage.getItem('skogsplan_token'),
  isAuthenticated: !!localStorage.getItem('skogsplan_token'),
  loading: false,
  error: null,

  login: async (email, password) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.login({ email, password });
      localStorage.setItem('skogsplan_token', response.accessToken);
      set({
        user: response.user,
        token: response.accessToken,
        isAuthenticated: true,
        loading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Inloggning misslyckades';
      set({ loading: false, error: message });
      throw err;
    }
  },

  register: async (name, email, password, role) => {
    set({ loading: true, error: null });
    try {
      const response = await authApi.register({ name, email, password, role });
      localStorage.setItem('skogsplan_token', response.accessToken);
      set({
        user: response.user,
        token: response.accessToken,
        isAuthenticated: true,
        loading: false,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Registrering misslyckades';
      set({ loading: false, error: message });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('skogsplan_token');
    set({ user: null, token: null, isAuthenticated: false });
  },

  setUser: (user) => set({ user }),

  loadUser: async () => {
    const token = localStorage.getItem('skogsplan_token');
    if (!token) return;
    set({ loading: true });
    try {
      const user = await authApi.getMe();
      set({ user, isAuthenticated: true, loading: false });
    } catch {
      localStorage.removeItem('skogsplan_token');
      set({ user: null, token: null, isAuthenticated: false, loading: false });
    }
  },

  clearError: () => set({ error: null }),
}));
