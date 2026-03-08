import React from 'react';
import { render, screen } from '@testing-library/react';
import Account from '../Account';

jest.mock('~/hooks', () => ({
  useAuthContext: jest.fn(() => ({
    user: {
      provider: 'google',
      twoFactorEnabled: false,
    },
  })),
}));

jest.mock('../DisplayUsernameMessages', () => () => <div>display-username</div>);
jest.mock('../DeleteAccount', () => () => <div>delete-account</div>);
jest.mock('../DangerZone', () => () => <div>danger-zone</div>);
jest.mock('../Nickname', () => () => <div>nickname</div>);
jest.mock('../Avatar', () => () => <div>avatar</div>);
jest.mock('../TwoFactorAuthentication', () => () => <div>two-factor-settings</div>);
jest.mock('../BackupCodesItem', () => () => <div>backup-codes</div>);
jest.mock('~/components/Referrals/ReferralPanel', () => () => <div>referrals</div>);

describe('Account', () => {
  it('shows the two-factor settings entry for social-login users', () => {
    render(<Account />);

    expect(screen.getByText('two-factor-settings')).toBeInTheDocument();
  });
});
