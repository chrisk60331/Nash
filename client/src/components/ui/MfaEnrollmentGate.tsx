import MfaEnrollmentFlow from './MfaEnrollmentFlow';

interface MfaEnrollmentGateProps {
  onDecline: () => void;
  onCompleted: () => void;
}

export default function MfaEnrollmentGate({ onDecline, onCompleted }: MfaEnrollmentGateProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-primary p-6">
      <MfaEnrollmentFlow
        title="Multi-factor authentication required"
        description="Before you can continue, set up one-time codes with Google Authenticator or another TOTP app. This is required for admins and any workspace where MFA is enforced for all users."
        onDecline={onDecline}
        declineLabel="Sign out"
        onCompleted={onCompleted}
      />
    </div>
  );
}
