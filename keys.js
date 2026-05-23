const express = require('express');
const router = express.Router();
const { v4: uuidv4 } = require('uuid');
const db = require('../db/database');
const { auth } = require('./auth');

// All routes require admin auth
router.use(auth);

function generateKeyString(prefix = 'TWEAK-') {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const seg = () => Array.from({ length: 6 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  return `${prefix}${seg()}-${seg()}-${seg()}`;
}

function expiresAt(days) {
  const d = new Date();
  d.setDate(d.getDate() + parseInt(days));
  return d.toISOString();
}

// GET /admin/keys — list all keys (with optional filters)
router.get('/', (req, res) => {
  const { status, search } = req.query;
  let query = 'SELECT * FROM keys WHERE 1=1';
  const params = [];

  if (status) { query += ' AND status = ?'; params.push(status); }
  if (search) {
    query += ' AND (key LIKE ? OR user_label LIKE ?)';
    params.push(`%${search}%`, `%${search}%`);
  }
  query += ' ORDER BY created_at DESC';

  const rows = db.prepare(query).all(...params);
  res.json({ success: true, keys: rows });
});

// GET /admin/keys/stats — dashboard stats
router.get('/stats', (req, res) => {
  const total   = db.prepare("SELECT COUNT(*) as c FROM keys").get().c;
  const active  = db.prepare("SELECT COUNT(*) as c FROM keys WHERE status='active'").get().c;
  const frozen  = db.prepare("SELECT COUNT(*) as c FROM keys WHERE status='frozen'").get().c;
  const banned  = db.prepare("SELECT COUNT(*) as c FROM keys WHERE status='banned'").get().c;
  const expired = db.prepare("SELECT COUNT(*) as c FROM keys WHERE status='expired'").get().c;
  const checks  = db.prepare("SELECT SUM(check_count) as c FROM keys").get().c || 0;
  res.json({ success: true, stats: { total, active, frozen, banned, expired, checks } });
});

// GET /admin/keys/logs — recent validation logs
router.get('/logs', (req, res) => {
  const logs = db.prepare('SELECT * FROM key_logs ORDER BY timestamp DESC LIMIT 100').all();
  res.json({ success: true, logs });
});

// POST /admin/keys/generate — create new key
router.post('/generate', (req, res) => {
  const { type = 'Standard', userLabel = 'unnamed', days = 30, prefix = 'TWEAK-', notes = '' } = req.body;

  // Ensure no duplicate key
  let keyStr, attempts = 0;
  do {
    keyStr = generateKeyString(prefix);
    attempts++;
    if (attempts > 20) return res.status(500).json({ success: false, error: 'Could not generate unique key' });
  } while (db.prepare('SELECT id FROM keys WHERE key = ?').get(keyStr));

  const id = uuidv4();
  const expires = expiresAt(days);

  db.prepare(`
    INSERT INTO keys (id, key, type, user_label, status, days, expires_at, notes)
    VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
  `).run(id, keyStr, type, userLabel, days, expires, notes);

  const key = db.prepare('SELECT * FROM keys WHERE id = ?').get(id);
  res.json({ success: true, key });
});

// PATCH /admin/keys/:id/status — freeze, ban, activate
router.patch('/:id/status', (req, res) => {
  const { status } = req.body;
  const allowed = ['active', 'frozen', 'banned', 'expired'];
  if (!allowed.includes(status))
    return res.status(400).json({ success: false, error: 'Invalid status' });

  const result = db.prepare('UPDATE keys SET status = ? WHERE id = ?').run(status, req.params.id);
  if (!result.changes) return res.status(404).json({ success: false, error: 'Key not found' });

  res.json({ success: true, message: `Status set to ${status}` });
});

// PATCH /admin/keys/:id/days — add or remove days
router.patch('/:id/days', (req, res) => {
  const days = parseInt(req.body.days);
  if (isNaN(days)) return res.status(400).json({ success: false, error: 'Invalid days value' });

  const key = db.prepare('SELECT * FROM keys WHERE id = ?').get(req.params.id);
  if (!key) return res.status(404).json({ success: false, error: 'Key not found' });

  const newExpiry = new Date(key.expires_at);
  newExpiry.setDate(newExpiry.getDate() + days);
  const newDays = Math.max(0, key.days + days);

  db.prepare('UPDATE keys SET expires_at = ?, days = ? WHERE id = ?')
    .run(newExpiry.toISOString(), newDays, req.params.id);

  const updated = db.prepare('SELECT * FROM keys WHERE id = ?').get(req.params.id);
  res.json({ success: true, key: updated });
});

// PATCH /admin/keys/:id/notes — update notes
router.patch('/:id/notes', (req, res) => {
  const { notes } = req.body;
  db.prepare('UPDATE keys SET notes = ? WHERE id = ?').run(notes || '', req.params.id);
  res.json({ success: true });
});

// DELETE /admin/keys/:id — delete one key
router.delete('/:id', (req, res) => {
  const result = db.prepare('DELETE FROM keys WHERE id = ?').run(req.params.id);
  if (!result.changes) return res.status(404).json({ success: false, error: 'Key not found' });
  res.json({ success: true, message: 'Key deleted' });
});

// DELETE /admin/keys/bulk/expired — delete all expired keys
router.delete('/bulk/expired', (req, res) => {
  const result = db.prepare("DELETE FROM keys WHERE status = 'expired'").run();
  res.json({ success: true, deleted: result.changes });
});

// GET /admin/keys/export — export all as JSON
router.get('/export', (req, res) => {
  const rows = db.prepare('SELECT * FROM keys ORDER BY created_at DESC').all();
  res.setHeader('Content-Disposition', 'attachment; filename="tweakpanel_keys.json"');
  res.setHeader('Content-Type', 'application/json');
  res.send(JSON.stringify(rows, null, 2));
});

module.exports = router;
