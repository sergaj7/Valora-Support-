const express = require('express');
const router = express.Router();
const db = require('../db/database');

// ─────────────────────────────────────────────────────────────
// PUBLIC ENDPOINTS — called by your tweak app, no auth needed
// ─────────────────────────────────────────────────────────────

// POST /api/validate
// Body: { "key": "TWEAK-XXXXXX-XXXXXX-XXXXXX" }
// Response examples:
//   { "valid": true,  "status": "active",  "type": "Pro", "expires_at": "...", "days_left": 14 }
//   { "valid": false, "status": "banned",  "reason": "Key is banned" }
//   { "valid": false, "status": "expired", "reason": "Key has expired" }
//   { "valid": false, "status": "not_found","reason": "Key not found" }

router.post('/validate', (req, res) => {
  const { key } = req.body;
  const ip = req.ip || req.connection.remoteAddress;

  if (!key || typeof key !== 'string')
    return res.status(400).json({ valid: false, status: 'error', reason: 'No key provided' });

  const row = db.prepare('SELECT * FROM keys WHERE key = ?').get(key.trim().toUpperCase());

  // Log the check
  function log(result) {
    db.prepare(`
      INSERT INTO key_logs (key_id, key, action, ip, result)
      VALUES (?, ?, 'validate', ?, ?)
    `).run(row?.id || null, key.trim().toUpperCase(), ip, result);
  }

  if (!row) {
    log('not_found');
    return res.json({ valid: false, status: 'not_found', reason: 'Key not found' });
  }

  // Update check stats
  db.prepare('UPDATE keys SET last_checked = datetime("now"), check_count = check_count + 1 WHERE id = ?')
    .run(row.id);

  // Check status first
  if (row.status === 'banned') {
    log('banned');
    return res.json({ valid: false, status: 'banned', reason: 'Key is banned' });
  }
  if (row.status === 'frozen') {
    log('frozen');
    return res.json({ valid: false, status: 'frozen', reason: 'Key is temporarily frozen' });
  }

  // Check expiry
  const now = new Date();
  const expires = new Date(row.expires_at);
  const daysLeft = Math.ceil((expires - now) / 86400000);

  if (row.status === 'expired' || daysLeft <= 0) {
    // Auto-mark as expired in DB
    if (row.status !== 'expired') {
      db.prepare("UPDATE keys SET status = 'expired' WHERE id = ?").run(row.id);
    }
    log('expired');
    return res.json({ valid: false, status: 'expired', reason: 'Key has expired' });
  }

  // All good!
  log('valid');
  return res.json({
    valid: true,
    status: 'active',
    type: row.type,
    user: row.user_label,
    expires_at: row.expires_at,
    days_left: daysLeft
  });
});

// GET /api/validate?key=TWEAK-XXXXX  (GET version, easier for some apps)
router.get('/validate', (req, res) => {
  req.body = { key: req.query.key };
  // Reuse the POST logic
  const { key } = req.query;
  const ip = req.ip || req.connection.remoteAddress;

  if (!key)
    return res.status(400).json({ valid: false, status: 'error', reason: 'No key provided' });

  const row = db.prepare('SELECT * FROM keys WHERE key = ?').get(key.trim().toUpperCase());

  function log(result) {
    db.prepare('INSERT INTO key_logs (key_id, key, action, ip, result) VALUES (?, ?, "validate", ?, ?)')
      .run(row?.id || null, key.trim().toUpperCase(), ip, result);
  }

  if (!row) { log('not_found'); return res.json({ valid: false, status: 'not_found', reason: 'Key not found' }); }

  db.prepare('UPDATE keys SET last_checked = datetime("now"), check_count = check_count + 1 WHERE id = ?').run(row.id);

  if (row.status === 'banned')   { log('banned');  return res.json({ valid: false, status: 'banned',  reason: 'Key is banned' }); }
  if (row.status === 'frozen')   { log('frozen');  return res.json({ valid: false, status: 'frozen',  reason: 'Key is temporarily frozen' }); }

  const now = new Date();
  const expires = new Date(row.expires_at);
  const daysLeft = Math.ceil((expires - now) / 86400000);

  if (row.status === 'expired' || daysLeft <= 0) {
    if (row.status !== 'expired') db.prepare("UPDATE keys SET status = 'expired' WHERE id = ?").run(row.id);
    log('expired');
    return res.json({ valid: false, status: 'expired', reason: 'Key has expired' });
  }

  log('valid');
  return res.json({ valid: true, status: 'active', type: row.type, user: row.user_label, expires_at: row.expires_at, days_left: daysLeft });
});

// GET /api/ping — health check
router.get('/ping', (req, res) => {
  res.json({ success: true, message: 'TweakPanel API is online', timestamp: new Date().toISOString() });
});

module.exports = router;
