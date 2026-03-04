const fs = require('fs').promises;
const multer = require('multer');
const express = require('express');
const { logger } = require('@librechat/data-schemas');
const {
  handleChatCompletions,
  handleListModels,
  uploadDocumentToBackboard,
  listBackboardDocuments,
  deleteBackboardDocument,
  syncAgentToBackboard,
  listAgentMappings,
  getSubscriptionBB,
  isFreeTierModel,
} = require('@librechat/api');
const { requireJwtAuth } = require('~/server/middleware');

const router = express.Router();
const upload = multer({ dest: '/tmp/backboard-uploads' });

router.post('/chat/completions', async (req, res, next) => {
  const userId = req.headers['x-backboard-user-id'];
  if (userId) {
    try {
      const sub = await getSubscriptionBB(userId);
      const model = req.body?.model ?? '';
      if (sub.plan === 'free' && !isFreeTierModel(model)) {
        return res.status(403).json({
          error: 'upgrade_required',
          message: 'This model requires a Plus or Unlimited plan.',
          requiredPlan: 'plus',
          currentPlan: 'free',
        });
      }
    } catch (err) {
      logger.error('[Backboard Proxy] Subscription check failed, blocking request', err);
      return res.status(500).json({
        error: 'subscription_check_failed',
        message: 'Unable to verify subscription status.',
      });
    }
  }
  return handleChatCompletions(req, res);
});
router.get('/models', (req, res) => handleListModels(req, res));

router.get('/documents', requireJwtAuth, async (req, res) => {
  try {
    const docs = await listBackboardDocuments();
    res.status(200).json(docs);
  } catch (error) {
    logger.error('[Backboard] Error listing documents:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/documents', requireJwtAuth, upload.single('file'), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file provided' });
    }

    const fileBuffer = await fs.readFile(req.file.path);
    const doc = await uploadDocumentToBackboard(req.file.originalname, fileBuffer);

    await fs.unlink(req.file.path).catch(() => {});
    res.status(201).json(doc);
  } catch (error) {
    logger.error('[Backboard] Error uploading document:', error);
    if (req.file?.path) {
      await fs.unlink(req.file.path).catch(() => {});
    }
    res.status(500).json({ error: error.message });
  }
});

router.delete('/documents/:documentId', requireJwtAuth, async (req, res) => {
  try {
    const deleted = await deleteBackboardDocument(req.params.documentId);
    if (!deleted) {
      return res.status(404).json({ error: 'Document not found' });
    }
    res.status(200).json({ deleted: true });
  } catch (error) {
    logger.error('[Backboard] Error deleting document:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/agents/sync', requireJwtAuth, async (req, res) => {
  try {
    const { agentId, name, description, instructions } = req.body;
    if (!agentId || !name) {
      return res.status(400).json({ error: 'agentId and name are required' });
    }
    const bbAssistantId = await syncAgentToBackboard({
      agentId,
      name,
      description,
      instructions,
    });
    res.status(200).json({ agentId, bbAssistantId });
  } catch (error) {
    logger.error('[Backboard] Error syncing agent:', error);
    res.status(500).json({ error: error.message });
  }
});

router.get('/agents/mappings', requireJwtAuth, async (req, res) => {
  try {
    const mappings = await listAgentMappings();
    res.status(200).json(mappings);
  } catch (error) {
    logger.error('[Backboard] Error listing mappings:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;
