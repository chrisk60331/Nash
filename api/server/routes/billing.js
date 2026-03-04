const express = require('express');
const { logger } = require('@librechat/data-schemas');
const {
  getSubscriptionBB,
  updateSubscriptionBB,
  resetPeriodUsageBB,
  invalidateSubscriptionCache,
  getIncludedTokens,
} = require('@librechat/api');
const { requireJwtAuth } = require('~/server/middleware');

const router = express.Router();

function getStripe() {
  const Stripe = require('stripe');
  return new Stripe(process.env.STRIPE_SECRET_KEY);
}

function getPriceIdForPlan(plan) {
  if (plan === 'plus') {
    return process.env.STRIPE_PRICE_ID_PLUS;
  }
  if (plan === 'unlimited') {
    return process.env.STRIPE_PRICE_ID_UNLIMITED;
  }
  return null;
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

router.get('/subscription', requireJwtAuth, async (req, res) => {
  try {
    const sub = await getSubscriptionBB(req.user.id);
    res.json({
      plan: sub.plan,
      usageTokens: sub.usageTokens,
      includedTokens: sub.includedTokens || getIncludedTokens(sub.plan),
      periodStart: sub.periodStart || null,
      periodEnd: sub.periodEnd || null,
      stripeSubscriptionId: sub.stripeSubscriptionId || null,
    });
  } catch (err) {
    logger.error('[Billing] Failed to get subscription', err);
    res.status(500).json({ error: 'Failed to get subscription' });
  }
});

router.post('/checkout', requireJwtAuth, async (req, res) => {
  try {
    const { priceId } = req.body;
    if (!priceId) {
      return res.status(400).json({ error: 'priceId is required' });
    }

    const plan = getPlanForPriceId(priceId);
    if (!plan) {
      return res.status(400).json({ error: 'Invalid price ID' });
    }

    const stripe = getStripe();
    const sub = await getSubscriptionBB(req.user.id);

    let customerId = sub.stripeCustomerId;
    if (!customerId) {
      const customer = await stripe.customers.create({
        email: req.user.email,
        metadata: { userId: req.user.id },
      });
      customerId = customer.id;
      await updateSubscriptionBB(req.user.id, { stripeCustomerId: customerId });
    }

    const session = await stripe.checkout.sessions.create({
      customer: customerId,
      mode: 'subscription',
      line_items: [{ price: priceId, quantity: 1 }],
      success_url: `${process.env.DOMAIN_CLIENT || 'http://localhost:3080'}/?billing=success`,
      cancel_url: `${process.env.DOMAIN_CLIENT || 'http://localhost:3080'}/?billing=cancelled`,
      metadata: { userId: req.user.id, plan },
    });

    res.json({ url: session.url });
  } catch (err) {
    logger.error('[Billing] Failed to create checkout session', err);
    res.status(500).json({ error: 'Failed to create checkout session' });
  }
});

router.post('/portal', requireJwtAuth, async (req, res) => {
  try {
    const sub = await getSubscriptionBB(req.user.id);
    if (!sub.stripeCustomerId) {
      return res.status(400).json({ error: 'No billing account found' });
    }

    const stripe = getStripe();
    const session = await stripe.billingPortal.sessions.create({
      customer: sub.stripeCustomerId,
      return_url: `${process.env.DOMAIN_CLIENT || 'http://localhost:3080'}/`,
    });

    res.json({ url: session.url });
  } catch (err) {
    logger.error('[Billing] Failed to create portal session', err);
    res.status(500).json({ error: 'Failed to create portal session' });
  }
});

module.exports = router;
