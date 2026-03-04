const jwt = require('jsonwebtoken');
const { logger } = require('@librechat/data-schemas');
const { SystemRoles } = require('librechat-data-provider');
const { findUser, createUser, updateUser } = require('~/models');
const { setAuthTokens } = require('~/server/services/AuthService');

function sanitizeRedirect(raw) {
  if (!raw || typeof raw !== 'string') {
    return '/';
  }
  try {
    const url = new URL(raw, 'http://localhost');
    return url.pathname + url.search;
  } catch {
    return '/';
  }
}

const ssoLoginController = async (req, res) => {
  const token = req.query.token || '';
  const redirectTo = sanitizeRedirect(req.query.redirect);
  const ssoSecret = process.env.SSO_SECRET || '';

  if (!ssoSecret || !token) {
    return res.status(400).send('SSO is not configured.');
  }

  let payload;
  try {
    payload = jwt.verify(token, ssoSecret, { algorithms: ['HS256'] });
  } catch (err) {
    if (err.name === 'TokenExpiredError') {
      return res.status(401).send('SSO link has expired.');
    }
    logger.error('[SSOController] Invalid token:', err.message);
    return res.status(401).send('Invalid SSO token.');
  }

  const email = (payload.email || '').trim().toLowerCase();
  const name = payload.name || email.split('@')[0];
  if (!email) {
    return res.status(400).send('Missing email in SSO token.');
  }

  try {
    let user = await findUser({ email });

    if (!user) {
      const userId = await createUser({
        provider: 'local',
        email,
        username: email,
        name,
        avatar: null,
        role: SystemRoles.USER,
        password: '__sso_managed__',
        emailVerified: true,
      });
      user = { _id: userId, email, name };
      await updateUser(userId, { emailVerified: true });
      logger.info(`[SSOController] Created user ${email} via SSO`);
    }

    const userId = user._id.toString ? user._id.toString() : user._id;
    const appToken = await setAuthTokens(userId, res);

    const safeRedirect = redirectTo.replace(/[&<>"']/g, '');
    return res.send(`<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>SSO Login</title></head>
<body>
<script>
  try { sessionStorage.setItem('sso_token', ${JSON.stringify(appToken)}); } catch(e) {}
  window.location.replace("${safeRedirect}");
</script>
<noscript><a href="${safeRedirect}">Continue</a></noscript>
</body></html>`);
  } catch (err) {
    logger.error('[SSOController] Error:', err);
    return res.status(500).send('SSO login failed.');
  }
};

module.exports = { ssoLoginController };
