import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import BillingContent from '~/components/Nav/BillingContent';
import Presentation from '~/components/Chat/Presentation';
import { useLocalize } from '~/hooks';

export default function BillingRoute() {
  const localize = useLocalize();

  return (
    <Presentation>
      <div className="h-full overflow-y-auto bg-presentation">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
          <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-sm text-text-secondary">
            <Link className="transition-colors hover:text-text-primary" to="/c/new">
              {localize('com_ui_chat')}
            </Link>
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
            <span className="text-text-primary">{localize('com_billing_title')}</span>
          </nav>

          <div className="max-w-3xl">
            <h1 className="text-2xl font-semibold text-text-primary sm:text-3xl">
              {localize('com_billing_title')}
            </h1>
            <p className="mt-2 text-sm leading-6 text-text-secondary sm:text-base">
              Compare plans, review included usage, and upgrade without the cramped modal layout.
            </p>
          </div>

          <BillingContent variant="page" />
        </div>
      </div>
    </Presentation>
  );
}
