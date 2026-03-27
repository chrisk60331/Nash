import { useState } from 'react';
import {
  OGDialog,
  OGDialogContent,
  OGDialogTitle,
  OGDialogDescription,
} from '@librechat/client';
import { useAuthContext } from '~/hooks/AuthContext';
import { useGetStartupConfig } from '~/data-provider';
import LoginForm from './LoginForm';
import SocialLoginRender from './SocialLoginRender';
import RegistrationForm from './RegistrationForm';

interface AuthModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: 'login' | 'register';
}

export default function AuthModal({ open, onOpenChange, defaultTab = 'login' }: AuthModalProps) {
  const [tab, setTab] = useState<'login' | 'register'>(defaultTab);
  const { error, setError, login } = useAuthContext();
  const { data: startupConfig } = useGetStartupConfig();

  if (!startupConfig) {
    return null;
  }

  return (
    <OGDialog open={open} onOpenChange={onOpenChange}>
      <OGDialogContent className="w-full max-w-md border-border-light bg-surface-primary px-6 py-6 text-text-primary">
        {/* Visually hidden title for a11y */}
        <OGDialogTitle className="sr-only">
          {tab === 'login' ? 'Sign in to Nash' : 'Create a Nash account'}
        </OGDialogTitle>
        <OGDialogDescription className="sr-only">
          {tab === 'login'
            ? 'Sign in to save your conversations and access all features.'
            : 'Create a free account to get started with Nash.'}
        </OGDialogDescription>

        {/* Logo + subtitle */}
        <div className="mb-5 flex flex-col items-center gap-1">
          <img
            src="assets/nash.png"
            className="h-8 w-auto object-contain dark:hidden"
            alt="Nash"
          />
          <img
            src="assets/nash_dark.png"
            className="hidden h-8 w-auto object-contain dark:block"
            alt="Nash"
          />
          <p className="mt-1.5 text-xs text-text-secondary">
            {tab === 'login' ? 'Sign in to save your chats' : 'Create a free account'}
          </p>
        </div>

        {/* Tab switcher */}
        {startupConfig.registrationEnabled && (
          <div className="mb-5 flex rounded-xl border border-border-light bg-surface-secondary/50 p-1">
            <button
              type="button"
              onClick={() => setTab('login')}
              className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                tab === 'login'
                  ? 'bg-surface-primary text-text-primary shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => setTab('register')}
              className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-colors ${
                tab === 'register'
                  ? 'bg-surface-primary text-text-primary shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              Sign up
            </button>
          </div>
        )}

        {/* Forms */}
        {tab === 'login' ? (
          <LoginForm
            onSubmit={login}
            startupConfig={startupConfig}
            error={error}
            setError={setError}
          />
        ) : (
          <RegistrationForm
            startupConfig={startupConfig}
            onSuccess={() => onOpenChange(false)}
          />
        )}

        {/* Social logins */}
        <SocialLoginRender startupConfig={startupConfig} />
      </OGDialogContent>
    </OGDialog>
  );
}
