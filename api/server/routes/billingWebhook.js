const express = require('express');
const { logger } = require('@librechat/data-schemas');
const {
  updateSubscriptionBB,
  resetPeriodUsageBB,
  invalidateSubscriptionCache,
  getIncludedTokens,
} = require('@librechat/api');

const router = express.Router();

function getStripe() {
  const Stripe = require('stripe');
  return new Stripe(process.env.STRIPE_SECRET_KEY);
}

function getPlanForPriceId(priceId) {
  if (priceId === process.env.STRIPE_PRICE_ID_PLUS) {
    return 'plus';
  }
  if (priceId === process.env.STRIPE_PRICE_ID_UNLIMITED) {
    return 'unlimited';
  }
  return null;
}

router.post(
  '/',
  express.raw({ type: 'application/json' }),
  async (req, res) => {
    const stripe = getStripe();
    const sig = req.headers['stripe-signature'];
    const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

    if (!webhookSecret) {
      logger.error('[Billing Webhook] STRIPE_WEBHOOK_SECRET not configured');
      return res.status(500).send('Webhook secret not configured');
    }

    let event;
    try {
      event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
    } catch (err) {
      logger.error('[Billing Webhook] Signature verification failed', err.message);
      return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    try {
      switch (event.type) {
        case 'checkout.session.completed': {
          const session = event.data.object;
          const userId = session.metadata?.userId;
          const plan = session.metadata?.plan;
          if (userId && plan) {
            const subscription = await stripe.subscriptions.retrieve(session.subscription);
            await updateSubscriptionBB(userId, {
              plan,
              stripeCustomerId: session.customer,
              stripeSubscriptionId: session.subscription,
              periodStart: new Date(subscription.current_period_start * 1000).toISOString(),
              periodEnd: new Date(subscription.current_period_end * 1000).toISOString(),
              usageTokens: 0,
              includedTokens: getIncludedTokens(plan),
            });
            logger.info(`[Billing Webhook] Activated ${plan} plan for user ${userId}`);
          }
          break;
        }

        case 'customer.subscription.updated': {
          const subscription = event.data.object;
          const priceId = subscription.items?.data?.[0]?.price?.id;
          const plan = getPlanForPriceId(priceId);
          const customerId = subscription.customer;

          if (plan && customerId) {
            const stripe2 = getStripe();
            const customer = await stripe2.customers.retrieve(customerId);
            const userId = customer.metadata?.userId;
            if (userId) {
              await updateSubscriptionBB(userId, {
                plan,
                stripeSubscriptionId: subscription.id,
                periodStart: new Date(subscription.current_period_start * 1000).toISOString(),
                periodEnd: new Date(subscription.current_period_end * 1000).toISOString(),
                includedTokens: getIncludedTokens(plan),
              });
              logger.info(`[Billing Webhook] Updated to ${plan} plan for user ${userId}`);
            }
          }
          break;
        }

        case 'customer.subscription.deleted': {
          const subscription = event.data.object;
          const customerId = subscription.customer;
          if (customerId) {
            const stripe2 = getStripe();
            const customer = await stripe2.customers.retrieve(customerId);
            const userId = customer.metadata?.userId;
            if (userId) {
              await updateSubscriptionBB(userId, {
                plan: 'free',
                stripeSubscriptionId: undefined,
                usageTokens: 0,
                includedTokens: 0,
                periodStart: undefined,
                periodEnd: undefined,
              });
              invalidateSubscriptionCache(userId);
              logger.info(`[Billing Webhook] Downgraded to free for user ${userId}`);
            }
          }
          break;
        }

        case 'invoice.paid': {
          const invoice = event.data.object;
          const customerId = invoice.customer;
          if (customerId) {
            const stripe2 = getStripe();
            const customer = await stripe2.customers.retrieve(customerId);
            const userId = customer.metadata?.userId;
            if (userId && invoice.subscription) {
              const subscription = await stripe2.subscriptions.retrieve(invoice.subscription);
              await resetPeriodUsageBB(
                userId,
                new Date(subscription.current_period_start * 1000).toISOString(),
                new Date(subscription.current_period_end * 1000).toISOString(),
              );
              logger.info(`[Billing Webhook] Reset usage for user ${userId}`);
            }
          }
          break;
        }

        default:
          break;
      }
    } catch (err) {
      logger.error(`[Billing Webhook] Error processing ${event.type}`, err);
    }

    res.json({ received: true });
  },
);

module.exports = router;
