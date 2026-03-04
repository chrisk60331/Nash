const { handleError, getSubscriptionBB, isFreeTierModel, getIncludedTokens } = require('@librechat/api');
const { logger } = require('@librechat/data-schemas');
const { ViolationTypes } = require('librechat-data-provider');
const { getModelsConfig } = require('~/server/controllers/ModelController');
const { logViolation } = require('~/cache');
/**
 * Validates the model of the request.
 * Also enforces free-tier provider restrictions.
 *
 * @async
 * @param {ServerRequest} req - The Express request object.
 * @param {Express.Response} res - The Express response object.
 * @param {Function} next - The Express next function.
 */
const validateModel = async (req, res, next) => {
  const { model, endpoint } = req.body;
  if (!model) {
    return handleError(res, { text: 'Model not provided' });
  }

  const modelsConfig = await getModelsConfig(req);

  if (!modelsConfig) {
    return handleError(res, { text: 'Models not loaded' });
  }

  const availableModels = modelsConfig[endpoint];
  if (!availableModels) {
    return handleError(res, { text: 'Endpoint models not loaded' });
  }

  let validModel = !!availableModels.find((availableModel) => availableModel === model);

  if (!validModel) {
    const { ILLEGAL_MODEL_REQ_SCORE: score = 1 } = process.env ?? {};
    const type = ViolationTypes.ILLEGAL_MODEL_REQUEST;
    const errorMessage = { type };
    await logViolation(req, res, type, errorMessage, score);
    return handleError(res, { text: 'Illegal model request' });
  }

  try {
    const sub = await getSubscriptionBB(req.user.id);
    if (sub.plan === 'free' && !isFreeTierModel(model)) {
      return res.status(403).json({
        error: 'upgrade_required',
        message: 'This model requires a Plus or Unlimited plan.',
        requiredPlan: 'plus',
        currentPlan: 'free',
      });
    }

    if (sub.plan !== 'free') {
      const budget = getIncludedTokens(sub.plan);
      if (budget > 0 && (sub.usageTokens ?? 0) >= budget) {
        const isPlus = sub.plan === 'plus';
        return res.status(403).json({
          error: 'token_budget_exceeded',
          message: isPlus
            ? 'You\'ve used all your included tokens this billing period. Upgrade to Unlimited for 6x more usage, or wait for your next billing cycle.'
            : 'You\'ve used all your included tokens this billing period. Usage resets at the start of your next billing cycle.',
          currentPlan: sub.plan,
          usageTokens: sub.usageTokens,
          includedTokens: budget,
          periodEnd: sub.periodEnd,
        });
      }
    }
  } catch (err) {
    logger.error('[validateModel] Subscription check failed, blocking request', err);
    return res.status(500).json({
      error: 'subscription_check_failed',
      message: 'Unable to verify subscription status. Please try again.',
    });
  }

  return next();
};

module.exports = validateModel;
