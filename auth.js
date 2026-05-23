const express = require('express');
const router = express.Router();
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('../db/database');

const JWT_SECRET = process.env.JWT_SECRET || 'tweakpanel-super-secret-change-in-production';

// Middleware: verify JWT token
function auth(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ success: false, error: 'No token' });
  try {
    req.admin = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ success: false, error: 'Invalid token' });
  }
}

// POST /auth/login
router.post('/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password)
    return res.status(400).json({ success: false, error: 'Missing fields' });

  const admin = db.prepare('SELECT * FROM admins WHERE username = ?').get(username);
  if (!admin || !bcrypt.compareSync(password, admin.password_hash))
    return res.status(401).json({ success: false, error: 'Invalid credentials' });

  const token = jwt.sign({ id: admin.id, username: admin.username }, JWT_SECRET, { expiresIn: '12h' });
  res.json({ success: true, token, username: admin.username });
});

// POST /auth/change-password  (requires auth)
router.post('/change-password', auth, (req, res) => {
  const { newUsername, newPassword } = req.body;
  if (!newUsername || !newPassword)
    return res.status(400).json({ success: false, error: 'Missing fields' });

  const hash = bcrypt.hashSync(newPassword, 10);
  db.prepare('UPDATE admins SET username = ?, password_hash = ? WHERE id = ?')
    .run(newUsername, hash, req.admin.id);

  res.json({ success: true, message: 'Credentials updated' });
});

// GET /auth/verify  (check if token is still valid)
router.get('/verify', auth, (req, res) => {
  res.json({ success: true, username: req.admin.username });
});

module.exports = router;
module.exports.auth = auth;
