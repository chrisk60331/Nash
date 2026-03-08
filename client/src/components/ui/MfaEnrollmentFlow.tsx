import { useCallback, useState } from 'react';
import { useSetRecoilState } from 'recoil';
import { Progress, useToastContext } from '@librechat/client';
import { dataService, type TUser } from 'librechat-data-provider';
import { SetupPhase, QRPhase, VerifyPhase, BackupPhase } from '~/components/Nav/SettingsTabs/Account/TwoFactorPhases';
import { useLocalize } from '~/hooks';
import store from '~/store';

type Phase = 'setup' | 'qr' | 'verify' | 'backup';

interface MfaEnrollmentFlowProps {
  authToken?: string;
  title: string;
  description: string;
  onDecline?: () => void;
  declineLabel?: string;
  onCompleted?: () => void;
}

const steps = ['Setup', 'Scan QR', 'Verify', 'Backup'];
const phasesLabel: Record<Phase, string> = {
  setup: 'Setup',
  qr: 'Scan QR',
  verify: 'Verify',
  backup: 'Backup',
};

function getErrorMessage(error: unknown, fallback: string): string {
  const err = error as { response?: { data?: { message?: unknown } } };
  return typeof err.response?.data?.message === 'string' ? err.response.data.message : fallback;
}

export default function MfaEnrollmentFlow({
  authToken,
  title,
  description,
  onDecline,
  declineLabel = 'Sign out',
  onCompleted,
}: MfaEnrollmentFlowProps) {
  const localize = useLocalize();
  const { showToast } = useToastContext();
  const setUser = useSetRecoilState(store.user);

  const [phase, setPhase] = useState<Phase>('setup');
  const [secret, setSecret] = useState('');
  const [otpauthUrl, setOtpauthUrl] = useState('');
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [verificationToken, setVerificationToken] = useState('');
  const [downloaded, setDownloaded] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isVerifying, setIsVerifying] = useState(false);
  const [redirectAfterCompletion, setRedirectAfterCompletion] = useState(false);

  const currentStep = steps.indexOf(phasesLabel[phase]);

  const handleGenerateQRCode = useCallback(async () => {
    try {
      setIsGenerating(true);
      const data = await dataService.enableTwoFactor(authToken);
      setOtpauthUrl(data.otpauthUrl);
      setSecret(data.otpauthUrl.split('secret=')[1]?.split('&')[0] ?? '');
      setBackupCodes(data.backupCodes);
      setDownloaded(false);
      setPhase('qr');
    } catch (error) {
      showToast({ message: getErrorMessage(error, 'Failed to generate authenticator setup'), status: 'error' });
    } finally {
      setIsGenerating(false);
    }
  }, [authToken, showToast]);

  const handleVerify = useCallback(async () => {
    try {
      setIsVerifying(true);
      await dataService.verifyTwoFactor({ token: verificationToken }, authToken);
      showToast({ message: localize('com_ui_2fa_verified') });
      const confirmed = await dataService.confirmTwoFactor({ token: verificationToken }, authToken);
      if (confirmed.user != null) {
        setUser((prev) => ({ ...(prev ?? {}), ...(confirmed.user as TUser) }) as TUser);
      }
      setRedirectAfterCompletion((confirmed.token ?? '') !== '');
      setPhase('backup');
    } catch (error) {
      showToast({ message: getErrorMessage(error, 'Invalid authentication code'), status: 'error' });
    } finally {
      setIsVerifying(false);
    }
  }, [authToken, localize, setUser, showToast, verificationToken]);

  const handleDownload = useCallback(() => {
    if (!backupCodes.length) {
      return;
    }
    const blob = new Blob([backupCodes.join('\n')], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'backup-codes.txt';
    anchor.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  }, [backupCodes]);

  const handleComplete = useCallback(() => {
    if (redirectAfterCompletion) {
      window.location.href = '/';
      return;
    }
    onCompleted?.();
  }, [onCompleted, redirectAfterCompletion]);

  return (
    <div className="w-full max-w-xl rounded-2xl border border-border-light bg-surface-primary p-6 shadow-xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-text-primary">{title}</h1>
        <p className="mt-2 text-sm leading-relaxed text-text-secondary">{description}</p>
      </div>

      <div className="mb-6 space-y-3">
        <Progress value={(currentStep / (steps.length - 1)) * 100} className="h-2 rounded-full" />
        <div className="flex justify-between text-xs font-medium">
          {steps.map((step, index) => (
            <span key={step} className={currentStep >= index ? 'text-text-primary' : 'text-text-tertiary'}>
              {step}
            </span>
          ))}
        </div>
      </div>

      {phase === 'setup' && (
        <SetupPhase isGenerating={isGenerating} onGenerate={handleGenerateQRCode} onNext={() => {}} onError={() => {}} />
      )}
      {phase === 'qr' && (
        <QRPhase secret={secret} otpauthUrl={otpauthUrl} onNext={() => setPhase('verify')} />
      )}
      {phase === 'verify' && (
        <VerifyPhase
          token={verificationToken}
          onTokenChange={setVerificationToken}
          isVerifying={isVerifying}
          onNext={handleVerify}
          onError={() => {}}
        />
      )}
      {phase === 'backup' && (
        <BackupPhase
          backupCodes={backupCodes}
          onDownload={handleDownload}
          downloaded={downloaded}
          onNext={handleComplete}
          onError={() => {}}
        />
      )}

      {onDecline != null && (
        <button
          type="button"
          onClick={onDecline}
          className="mt-6 w-full rounded-xl border border-border-light px-4 py-3 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
        >
          {declineLabel}
        </button>
      )}
    </div>
  );
}
