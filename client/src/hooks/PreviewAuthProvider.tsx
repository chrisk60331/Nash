import {
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useNavigate } from 'react-router-dom';
import { SystemRoles } from 'librechat-data-provider';
import type * as t from 'librechat-data-provider';
import type { TAuthContext, TResError } from '~/common';
import { useLoginUserMutation, useLogoutUserMutation } from '~/data-provider';
import { AuthContext } from './AuthContext';



export function PreviewAuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [user, setUser] = useState<t.TUser | undefined>(undefined);
  const [token, setToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | undefined>(undefined);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const loginMutation = useLoginUserMutation({
    onSuccess: (data: t.TLoginResponse) => {
      const { user, token, twoFAPending, mfaSetupRequired, tempToken } = data;

      if (twoFAPending) {
        navigate(`/login/2fa?tempToken=${tempToken}`, { replace: true });
        return;
      }

      if (mfaSetupRequired) {
        navigate(`/login/mfa-enroll?tempToken=${tempToken}`, { replace: true });
        return;
      }

      setError(undefined);
      setUser(user);
      setToken(token);
      setIsAuthenticated(true);
    },
    onError: (err: TResError | unknown) => {
      const resError = err as TResError;
      setError(resError.message);
    },
  });

  const logoutMutation = useLogoutUserMutation({
    onSuccess: () => {
      setUser(undefined);
      setToken(undefined);
      setError(undefined);
      setIsAuthenticated(false);
    },
    onError: () => {
      setUser(undefined);
      setToken(undefined);
      setIsAuthenticated(false);
    },
  });

  const login = useCallback((data: t.TLoginUser) => {
    loginMutation.mutate(data);
  }, [loginMutation]);

  const logout = useCallback((redirect?: string) => {
    logoutMutation.mutate(undefined, {
      onSettled: () => {
        if (redirect) {
          navigate(redirect, { replace: true });
        }
      },
    });
  }, [logoutMutation, navigate]);

  const value = useMemo<TAuthContext>(
    () => ({
      user,
      token,
      error,
      login,
      logout,
      setError,
      isAuthenticated,
      roles: {
        [SystemRoles.USER]: null,
        [SystemRoles.ADMIN]: null,
      },
    }),
    [user, token, error, login, logout, isAuthenticated],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
