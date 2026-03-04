import { useState, memo, useRef } from 'react';
import * as Menu from '@ariakit/react/menu';
import { FileText, LogOut, Sparkles, Zap, Shield } from 'lucide-react';
import { SystemRoles } from 'librechat-data-provider';
import { LinkIcon, GearIcon, DropdownMenuSeparator, Avatar } from '@librechat/client';
import { MyFilesModal } from '~/components/Chat/Input/Files/MyFilesModal';
import { useGetStartupConfig, useGetUserBalance, useGetSubscription } from '~/data-provider';
import { useAuthContext } from '~/hooks/AuthContext';
import AdminUsersModal from './AdminUsersModal';
import BillingModal from './BillingModal';
import { useLocalize } from '~/hooks';
import Settings from './Settings';
import { cn } from '~/utils';

function AccountSettings() {
  const localize = useLocalize();
  const { user, isAuthenticated, logout } = useAuthContext();
  const { data: startupConfig } = useGetStartupConfig();
  const billingEnabled = !!startupConfig?.billing?.enabled;
  const { data: subscription } = useGetSubscription({ enabled: !!isAuthenticated && billingEnabled });
  const balanceQuery = useGetUserBalance({
    enabled: !!isAuthenticated && startupConfig?.balance?.enabled,
  });
  const [showSettings, setShowSettings] = useState(false);
  const [showFiles, setShowFiles] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [showAdminUsers, setShowAdminUsers] = useState(false);
  const accountSettingsButtonRef = useRef<HTMLButtonElement>(null);

  const plan = subscription?.plan ?? 'free';
  const isAdmin = user?.role === SystemRoles.ADMIN;

  return (
    <Menu.MenuProvider>
      <Menu.MenuButton
        ref={accountSettingsButtonRef}
        aria-label={localize('com_nav_account_settings')}
        data-testid="nav-user"
        className="mt-text-sm flex h-auto w-full items-center gap-2 rounded-xl p-2 text-sm transition-all duration-200 ease-in-out hover:bg-surface-active-alt aria-[expanded=true]:bg-surface-active-alt"
      >
        <div className="-ml-0.9 -mt-0.8 h-8 w-8 flex-shrink-0">
          <div className="relative flex">
            <Avatar user={user} size={32} />
          </div>
        </div>
        <div
          className="mt-2 flex grow items-center gap-1.5 overflow-hidden text-left text-text-primary"
          style={{ marginTop: '0', marginLeft: '0' }}
        >
          <span className="truncate text-sm">
            {user?.name ?? user?.username ?? localize('com_nav_user')}
          </span>
          {billingEnabled && (
            <span
              className={cn(
                'flex-shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase leading-none',
                plan === 'unlimited'
                  ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400'
                  : plan === 'plus'
                    ? 'bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-400'
                    : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
              )}
            >
              {plan === 'unlimited' ? 'UNL' : plan === 'plus' ? 'PLUS' : 'FREE'}
            </span>
          )}
        </div>
      </Menu.MenuButton>
      <Menu.Menu
        className="account-settings-popover popover-ui z-[125] w-[305px] rounded-lg md:w-[244px]"
        style={{
          transformOrigin: 'bottom',
          translate: '0 -4px',
        }}
      >
        <div className="text-token-text-secondary ml-3 mr-2 py-2 text-sm" role="note">
          {user?.email ?? localize('com_nav_user')}
        </div>
        <DropdownMenuSeparator />
        {startupConfig?.balance?.enabled === true && balanceQuery.data != null && (
          <>
            <div className="text-token-text-secondary ml-3 mr-2 py-2 text-sm" role="note">
              {localize('com_nav_balance')}:{' '}
              {new Intl.NumberFormat().format(Math.round(balanceQuery.data.tokenCredits))}
            </div>
            <DropdownMenuSeparator />
          </>
        )}
        <Menu.MenuItem onClick={() => setShowFiles(true)} className="select-item text-sm">
          <FileText className="icon-md" aria-hidden="true" />
          {localize('com_nav_my_files')}
        </Menu.MenuItem>
        {startupConfig?.helpAndFaqURL !== '/' && (
          <Menu.MenuItem
            onClick={() => window.open(startupConfig?.helpAndFaqURL, '_blank')}
            className="select-item text-sm"
          >
            <LinkIcon aria-hidden="true" />
            {localize('com_nav_help_faq')}
          </Menu.MenuItem>
        )}
        {billingEnabled && (
          <Menu.MenuItem onClick={() => setShowBilling(true)} className="select-item text-sm">
            {plan === 'unlimited' ? (
              <Zap className="icon-md text-amber-500" aria-hidden="true" />
            ) : plan === 'plus' ? (
              <Sparkles className="icon-md text-violet-500" aria-hidden="true" />
            ) : (
              <Sparkles className="icon-md" aria-hidden="true" />
            )}
            {localize('com_billing_title')}
          </Menu.MenuItem>
        )}
        <Menu.MenuItem onClick={() => setShowSettings(true)} className="select-item text-sm">
          <GearIcon className="icon-md" aria-hidden="true" />
          {localize('com_nav_settings')}
        </Menu.MenuItem>
        {isAdmin && (
          <Menu.MenuItem onClick={() => setShowAdminUsers(true)} className="select-item text-sm">
            <Shield className="icon-md text-blue-500" aria-hidden="true" />
            User Management
          </Menu.MenuItem>
        )}
        <DropdownMenuSeparator />
        <Menu.MenuItem onClick={() => logout()} className="select-item text-sm">
          <LogOut className="icon-md" aria-hidden="true" />
          {localize('com_nav_log_out')}
        </Menu.MenuItem>
      </Menu.Menu>
      {showFiles && (
        <MyFilesModal
          open={showFiles}
          onOpenChange={setShowFiles}
          triggerRef={accountSettingsButtonRef}
        />
      )}
      {showSettings && <Settings open={showSettings} onOpenChange={setShowSettings} />}
      {showBilling && <BillingModal open={showBilling} onOpenChange={setShowBilling} />}
      {showAdminUsers && (
        <AdminUsersModal open={showAdminUsers} onOpenChange={setShowAdminUsers} />
      )}
    </Menu.MenuProvider>
  );
}

export default memo(AccountSettings);
