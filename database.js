const Database = require('better-sqlite3');
const bcrypt = require('bcryptjs');
const path = require('path');
const fs = require('fs');

const DB_PATH = process.env.DB_PATH || path.join(__dirname, 'tweakpanel.db');

const db = new Database(DB_PATH);

// Enable WAL mode for better performance
db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

// Create tables
db.exec(`
  CREATE TABLE IF NOT EXISTS admins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS keys (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    type TEXT DEFAULT 'Standard',
    user_label TEXT DEFAULT 'unnamed',
    status TEXT DEFAULT 'active',
    days INTEGER DEFAULT 30,
    created_at TEXT DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    last_checked TEXT,
    check_count INTEGER DEFAULT 0,
    notes TEXT DEFAULT ''
  );

  CREATE TABLE IF NOT EXISTS key_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT,
    key TEXT,
    action TEXT,
    ip TEXT,
    result TEXT,
    timestamp TEXT DEFAULT (datetime('now')),
    FOREIGN KEY(key_id) REFERENCES keys(id) ON DELETE SET NULL
  );
`);

// Seed default admin if none exists
const adminExists = db.prepare('SELECT id FROM admins WHERE username = ?').get('admin');
if (!adminExists) {
  const hash = bcrypt.hashSync('admin123', 10);
  db.prepare('INSERT INTO admins (username, password_hash) VALUES (?, ?)').run('admin', hash);
  console.log('[DB] Default admin created: admin / admin123');
}

module.exports = db;
