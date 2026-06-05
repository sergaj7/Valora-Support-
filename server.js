// ═══════════════════════════════════════════════════════════
//  server.js  —  Ramin Tweaks Backend  (add to your existing)
//  NEW ENDPOINTS: /api/log  /api/hwid
//  Also updated: /api/verify now accepts &hwid= param
// ═══════════════════════════════════════════════════════════

const express = require('express');
const cors = require('cors');
const path = require('path');
const { Pool } = require('pg');

const app = express();
const PORT = process.env.PORT || 3000;
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    ssl: process.env.DATABASE_URL ? { rejectUnauthorized: false } : false
});

async function initDB() {
    // Original keys table
    await pool.query(`
        CREATE TABLE IF NOT EXISTS keys (
            id       TEXT PRIMARY KEY,
            key      TEXT UNIQUE NOT NULL,
            type     TEXT DEFAULT 'Standard',
            username TEXT DEFAULT 'unnamed',
            days     INTEGER DEFAULT 30,
            status   TEXT DEFAULT 'active',
            created  TIMESTAMPTZ DEFAULT NOW(),
            expires  TIMESTAMPTZ,
            prefix   TEXT DEFAULT 'TWEAK-',
            hwid     TEXT DEFAULT '',
            ip_log   TEXT DEFAULT ''
        );
    `);

    // ── NEW: ip_logs table ──────────────────────────────────────
    await pool.query(`
        CREATE TABLE IF NOT EXISTS ip_logs (
            id         SERIAL PRIMARY KEY,
            key        TEXT NOT NULL,
            hwid       TEXT,
            ip         TEXT,
            hostname   TEXT,
            logged_at  TIMESTAMPTZ DEFAULT NOW()
        );
    `);

    console.log('Database ready (with HWID + IP log tables)');
}

// ── Admin Auth ──────────────────────────────────────────────
const ADMIN_USER = process.env.ADMIN_USER || 'admin';
const ADMIN_PASS = process.env.ADMIN_PASS || 'admin123';

function requireAdmin(req, res, next) {
    if (req.headers['x-admin-token'] !== ADMIN_PASS)
        return res.status(401).json({ error: 'Unauthorized' });
    next();
}

// ═══════════════════════════════════════════════════════════
//  PUBLIC: /api/verify  (used by .exe — now with HWID check)
// ═══════════════════════════════════════════════════════════
app.get('/api/verify', async (req, res) => {
    const key  = (req.query.key  || '').toUpperCase().trim();
    const hwid = (req.query.hwid || '').trim();

    if (!key) return res.json({ valid: false, status: 'error', message: 'Kein Key angegeben' });

    try {
        const { rows } = await pool.query('SELECT * FROM keys WHERE key = $1', [key]);
        if (!rows.length)
            return res.json({ valid: false, status: 'invalid', message: 'Key ungueltig oder nicht gefunden', user: '', expiry: '' });

        const k = rows[0];

        // ── HWID LOCK ──────────────────────────────────────────
        if (k.hwid && k.hwid !== '' && hwid && k.hwid !== hwid) {
            return res.json({
                valid: false,
                status: 'hwid_mismatch',
                message: 'Key ist an ein anderes Gerät gebunden',
                user: k.username,
                expiry: k.expires
            });
        }
        // First use — bind HWID
        if ((!k.hwid || k.hwid === '') && hwid) {
            await pool.query('UPDATE keys SET hwid=$1 WHERE id=$2', [hwid, k.id]);
        }

        if (k.status === 'banned')
            return res.json({ valid: false, status: 'banned', message: 'Key gesperrt', user: k.username, expiry: k.expires });
        if (k.status === 'frozen')
            return res.json({ valid: false, status: 'frozen', message: 'Key eingefroren', user: k.username, expiry: k.expires });

        if (new Date() > new Date(k.expires)) {
            await pool.query("UPDATE keys SET status='expired' WHERE id=$1", [k.id]);
            return res.json({ valid: false, status: 'expired', message: 'Key abgelaufen', user: k.username, expiry: k.expires });
        }

        return res.json({
            valid: true,
            status: 'active',
            message: 'Key gueltig!',
            user: k.username,
            expiry: k.expires ? k.expires.toISOString().split('T')[0] : ''
        });
    } catch (e) {
        console.error(e);
        res.status(500).json({ valid: false, status: 'error', message: 'Datenbankfehler' });
    }
});

// ═══════════════════════════════════════════════════════════
//  PUBLIC: /api/log  (IP + HWID logging from .exe)
// ═══════════════════════════════════════════════════════════
app.get('/api/log', async (req, res) => {
    const key      = (req.query.key  || '').toUpperCase().trim();
    const hwid     = (req.query.hwid || '').trim();
    const ip       = req.query.ip || req.ip || req.connection.remoteAddress || '';
    const hostname = (req.query.host || '').trim();

    if (!key) return res.json({ ok: false });

    try {
        // Insert log entry
        await pool.query(
            `INSERT INTO ip_logs (key, hwid, ip, hostname) VALUES ($1,$2,$3,$4)`,
            [key, hwid, ip, hostname]
        );
        // Also update last_ip on keys table (add column if not exists)
        await pool.query(`ALTER TABLE keys ADD COLUMN IF NOT EXISTS last_ip TEXT DEFAULT ''`);
        await pool.query(`ALTER TABLE keys ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ`);
        await pool.query(
            `UPDATE keys SET last_ip=$1, last_seen=NOW() WHERE key=$2`,
            [ip, key]
        );
        res.json({ ok: true });
    } catch (e) {
        console.error('IP log error:', e.message);
        res.json({ ok: false });
    }
});

// ═══════════════════════════════════════════════════════════
//  ADMIN: Login
// ═══════════════════════════════════════════════════════════
app.post('/api/admin/login', (req, res) => {
    const { user, pass } = req.body;
    if (user === ADMIN_USER && pass === ADMIN_PASS)
        res.json({ success: true, token: ADMIN_PASS });
    else
        res.status(401).json({ success: false, message: 'Falsche Zugangsdaten' });
});

// ═══════════════════════════════════════════════════════════
//  ADMIN: Keys CRUD
// ═══════════════════════════════════════════════════════════
app.get('/api/admin/keys', requireAdmin, async (req, res) => {
    const { rows } = await pool.query('SELECT * FROM keys ORDER BY created DESC');
    res.json(rows.map(toClient));
});

app.post('/api/admin/keys', requireAdmin, async (req, res) => {
    const { key, type, user, days, status, expires, prefix } = req.body;
    const id = Date.now().toString() + Math.random().toString(36).slice(2, 8);
    const { rows } = await pool.query(
        `INSERT INTO keys (id, key, type, username, days, status, expires, prefix)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *`,
        [id, key, type, user, days, status, expires, prefix]
    );
    res.json(toClient(rows[0]));
});

app.patch('/api/admin/keys/:id', requireAdmin, async (req, res) => {
    const fields = [], vals = [];
    let i = 1;
    const map = { status: 'status', expires: 'expires', days: 'days', user: 'username', hwid: 'hwid' };
    for (const [k, col] of Object.entries(map)) {
        if (req.body[k] !== undefined) { fields.push(`${col}=$${i++}`); vals.push(req.body[k]); }
    }
    if (!fields.length) return res.json({ success: true });
    vals.push(req.params.id);
    const { rows } = await pool.query(`UPDATE keys SET ${fields.join(',')} WHERE id=$${i} RETURNING *`, vals);
    res.json(toClient(rows[0]));
});

app.delete('/api/admin/keys/:id', requireAdmin, async (req, res) => {
    await pool.query('DELETE FROM keys WHERE id=$1', [req.params.id]);
    res.json({ success: true });
});

// ── ADMIN: HWID Reset ───────────────────────────────────────
app.post('/api/admin/keys/:id/reset-hwid', requireAdmin, async (req, res) => {
    await pool.query('UPDATE keys SET hwid=\'\' WHERE id=$1', [req.params.id]);
    res.json({ success: true, message: 'HWID resettet — nächste Anmeldung bindet neues Gerät' });
});

// ── ADMIN: IP Logs ──────────────────────────────────────────
app.get('/api/admin/logs', requireAdmin, async (req, res) => {
    const { key } = req.query;
    let q = 'SELECT * FROM ip_logs ORDER BY logged_at DESC LIMIT 200';
    let args = [];
    if (key) { q = 'SELECT * FROM ip_logs WHERE key=$1 ORDER BY logged_at DESC LIMIT 100'; args=[key]; }
    const { rows } = await pool.query(q, args);
    res.json(rows);
});

// ── Helper ──────────────────────────────────────────────────
function toClient(row) {
    return {
        id:       row.id,
        key:      row.key,
        type:     row.type,
        user:     row.username,
        days:     row.days,
        status:   row.status,
        created:  row.created,
        expires:  row.expires,
        prefix:   row.prefix,
        hwid:     row.hwid     || '',
        last_ip:  row.last_ip  || '',
        last_seen:row.last_seen|| null,
    };
}

// ── Serve frontend ──────────────────────────────────────────
app.get('*', (req, res) => res.sendFile(path.join(__dirname, 'public', 'index.html')));

initDB().then(() => {
    app.listen(PORT, () => console.log(`Ramin Tweaks API running on port ${PORT}`));
}).catch(err => {
    console.error('DB init failed:', err.message);
    process.exit(1);
});
