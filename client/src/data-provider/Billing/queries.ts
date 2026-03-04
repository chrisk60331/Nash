import { QueryKeys, dataService } from 'librechat-data-provider';
import { useQuery, useMutation } from '@tanstack/react-query';
import type { QueryObserverResult, UseQueryOptions } from '@tanstack/react-query';
import type { BillingSubscription, CheckoutResponse, PortalResponse } from 'librechat-data-provider';

export const useGetSubscription = (
  config?: UseQueryOptions<BillingSubscription>,
): QueryObserverResult<BillingSubscription> => {
  return useQuery<BillingSubscription>(
    [QueryKeys.billingSubscription],
    () => dataService.getBillingSubscription(),
    {
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
      staleTime: 30_000,
      ...config,
    },
  );
};

export const useCreateCheckout = () => {
  return useMutation<CheckoutResponse, Error, string>(
    (priceId: string) => dataService.createBillingCheckout(priceId),
  );
};

export const useCreatePortalSession = () => {
  return useMutation<PortalResponse, Error, void>(
    () => dataService.createBillingPortal(),
  );
};
