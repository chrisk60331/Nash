import { useSearchParams } from 'react-router-dom';
import MfaEnrollmentFlow from '~/components/ui/MfaEnrollmentFlow';

export default function MfaEnrollmentScreen() {
  const [searchParams] = useSearchParams();
  const tempToken = searchParams.get('tempToken') ?? '';

  return (
    <div className="mt-4">
      <MfaEnrollmentFlow
        authToken={tempToken}
        title="Set up one-time codes"
        description="Scan the QR code with Google Authenticator or another TOTP app, verify one code, and save your backup codes before continuing."
      />
    </div>
  );
}
