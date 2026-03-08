import React from 'react';
import DisplayUsernameMessages from './DisplayUsernameMessages';
import DeleteAccount from './DeleteAccount';
import DangerZone from './DangerZone';
import Nickname from './Nickname';
import Avatar from './Avatar';
import EnableTwoFactorItem from './TwoFactorAuthentication';
import BackupCodesItem from './BackupCodesItem';
import ReferralPanel from '~/components/Referrals/ReferralPanel';
import { useAuthContext } from '~/hooks';

function Account() {
  const { user } = useAuthContext();
  return (
    <div className="flex flex-col gap-3 p-1 text-sm text-text-primary">
      <div className="pb-3">
        <Nickname />
      </div>
      <div className="pb-3">
        <DisplayUsernameMessages />
      </div>
      <div className="pb-3">
        <Avatar />
      </div>
      <div className="pb-3">
        <ReferralPanel showRedeem={true} />
      </div>
      <div className="pb-3">
        <EnableTwoFactorItem />
      </div>
      {user?.twoFactorEnabled && (
        <div className="pb-3">
          <BackupCodesItem />
        </div>
      )}
      <div className="pb-3">
        <DeleteAccount />
      </div>
      <div className="pb-3">
        <DangerZone />
      </div>
    </div>
  );
}

export default React.memo(Account);
