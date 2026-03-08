import React from 'react';
import { render, screen } from '@testing-library/react';
import Root from '../Root';

jest.mock('@librechat/client', () => ({
  useMediaQuery: jest.fn(() => false),
}));

jest.mock('~/hooks', () => ({
  useSearchEnabled: jest.fn(),
  useAssistantsMap: jest.fn(() => ({})),
  useAuthContext: jest.fn(() => ({
    isAuthenticated: true,
    logout: jest.fn(),
    user: {
      role: 'ADMIN',
      twoFactorEnabled: false,
    },
  })),
  useAgentsMap: jest.fn(() => ({})),
  useFileMap: jest.fn(() => ({})),
}));

jest.mock('~/Providers', () => {
  const React = require('react');
  return {
    PromptGroupsProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    AssistantsMapContext: { Provider: ({ children }: { children: React.ReactNode }) => <>{children}</> },
    AgentsMapContext: { Provider: ({ children }: { children: React.ReactNode }) => <>{children}</> },
    SetConvoProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    FileMapContext: { Provider: ({ children }: { children: React.ReactNode }) => <>{children}</> },
  };
});

jest.mock('~/data-provider', () => ({
  useUserTermsQuery: jest.fn(() => ({ data: { termsAccepted: true } })),
  useGetStartupConfig: jest.fn(() => ({ data: { requireMfaForAllUsers: false } })),
  useInitQuery: jest.fn(),
  useHealthCheck: jest.fn(),
}));

jest.mock('~/components/Nav', () => ({
  Nav: () => <div>nav</div>,
  MobileNav: () => <div>mobile-nav</div>,
  NAV_WIDTH: { MOBILE: 320 },
}));

jest.mock('~/components/ui', () => ({
  CookieConsentBanner: () => <div>cookie-banner</div>,
  TermsGate: () => <div>terms-gate</div>,
  MfaEnrollmentGate: () => <div>mfa-gate</div>,
}));

jest.mock('~/components/Banners', () => ({
  Banner: () => <div>banner</div>,
}));

describe('Root', () => {
  it('blocks admins without MFA behind the enrollment gate', () => {
    render(<Root />);

    expect(screen.getByText('mfa-gate')).toBeInTheDocument();
  });
});
