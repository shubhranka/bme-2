import { useState, useEffect } from "react";

interface User {
  id: string;
  email: string;
}

interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  });

  // Check authentication status on mount
  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await fetch("/api/me", {
        credentials: "include",
      });

      if (response.ok) {
        const user = await response.json();
        setState({ user, loading: false, error: null });
      } else {
        setState({ user: null, loading: false, error: null });
      }
    } catch (err) {
      setState({ user: null, loading: false, error: "Failed to check authentication" });
    }
  };

  const logout = async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "include",
      });
      setState({ user: null, loading: false, error: null });
    } catch (err) {
      console.error("Logout failed:", err);
    }
  };

  return {
    user: state.user,
    loading: state.loading,
    error: state.error,
    logout,
    refreshAuth: checkAuth,
  };
}
