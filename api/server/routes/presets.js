const crypto = require('crypto');
const express = require('express');
const { logger } = require('@librechat/data-schemas');
const { getPresetsBB, savePresetBB, deletePresetsBB } = require('@librechat/api');
const requireJwtAuth = require('~/server/middleware/requireJwtAuth');

const router = express.Router();
router.use(requireJwtAuth);

router.get('/', async (req, res) => {
  try {
    const presets = await getPresetsBB(req.user.id);
    res.status(200).json(presets);
  } catch (error) {
    logger.error('[/presets] error loading presets', error);
    res.status(200).json([]);
  }
});

router.post('/', async (req, res) => {
  const update = req.body || {};

  update.presetId = update?.presetId || crypto.randomUUID();

  try {
    const preset = await savePresetBB(req.user.id, update);
    res.status(201).json(preset);
  } catch (error) {
    logger.error('[/presets] error saving preset', error);
    res.status(500).send('There was an error when saving the preset');
  }
});

router.post('/delete', async (req, res) => {
  let filter = {};
  const { presetId } = req.body || {};

  if (presetId) {
    filter = { presetId };
  }

  logger.debug('[/presets/delete] delete preset filter', filter);

  try {
    const deleteCount = await deletePresetsBB(req.user.id, filter);
    res.status(201).json(deleteCount);
  } catch (error) {
    logger.error('[/presets/delete] error deleting presets', error);
    res.status(500).send('There was an error deleting the presets');
  }
});

module.exports = router;
