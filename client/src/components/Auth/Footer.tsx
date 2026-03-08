import { Fragment, useState } from 'react';
import { Link } from 'react-router-dom';
import { Constants, TStartupConfig } from 'librechat-data-provider';
import ReleaseNotesModal from '~/components/Chat/ReleaseNotesModal';

function Footer({ startupConfig }: { startupConfig: TStartupConfig | null | undefined }) {
  const [showReleaseNotes, setShowReleaseNotes] = useState(false);

  const statusUrl =
    ((startupConfig as Record<string, unknown>)?.statusPageURL as string | undefined) ??
    'https://crimson-rabbit-6111.statusgator.app';
  const supportUrl =
    ((startupConfig as Record<string, unknown>)?.supportURL as string | undefined) ??
    'mailto:support@backboard.io';

  const linkClass =
    'text-sm text-green-600 underline decoration-transparent transition-all duration-200 hover:text-green-700 hover:decoration-green-700 focus:text-green-700 focus:decoration-green-700 dark:text-green-500 dark:hover:text-green-400 dark:hover:decoration-green-400 dark:focus:text-green-400 dark:focus:decoration-green-400';
  const sep = <div className="h-4 border-r-[1px] border-gray-300 dark:border-gray-600" />;

  const links = [
    <Link key="privacy" to="/privacy" className={linkClass}>Privacy Policy</Link>,
    <Link key="terms" to="/terms" className={linkClass}>Terms of Service</Link>,
    <Link key="cookies" to="/cookies" className={linkClass}>Cookies</Link>,
    <a
      key="status"
      href={statusUrl}
      target={statusUrl.startsWith('http') ? '_blank' : undefined}
      rel="noreferrer"
      className={linkClass}
    >
      Status
    </a>,
    <a key="support" href={supportUrl} className={linkClass}>Support</a>,
  ];

  return (
    <>
      <div className="align-end m-4 flex flex-wrap items-center justify-center gap-2 text-center" role="contentinfo">
        {links.map((link, i) => (
          <Fragment key={link.key}>
            {link}
            {i < links.length - 1 && sep}
          </Fragment>
        ))}
        {sep}
        <button
          type="button"
          className={linkClass}
          onClick={() => setShowReleaseNotes(true)}
          title={`Open release notes for ${String(Constants.VERSION)}`}
        >
          {`Nash ${String(Constants.VERSION)}`}
        </button>
      </div>
      <ReleaseNotesModal
        open={showReleaseNotes}
        onOpenChange={setShowReleaseNotes}
        currentVersion={String(Constants.VERSION)}
      />
    </>
  );
}

export default Footer;
