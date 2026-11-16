// Utilidades de sesión: cookie firmada con HMAC. Las credenciales salen de variables de entorno
// (APP_USER, APP_PASS, APP_SECRET) y, si no están, de los valores por defecto de abajo.
const crypto = require("crypto");

const USER = process.env.APP_USER || "villalba";
const PASS = process.env.APP_PASS || "123456";
const SECRET = process.env.APP_SECRET || "cambia-este-secreto-en-vercel";
const COOKIE = "vgl_session";
const MAX_AGE = 60 * 60 * 24 * 30; // 30 días

const sign = (v) => crypto.createHmac("sha256", SECRET).update(v).digest("base64url");

function safeEqual(a, b) {
  const x = Buffer.from(String(a)), y = Buffer.from(String(b));
  return x.length === y.length && crypto.timingSafeEqual(x, y);
}

function checkCredentials(user, pass) {
  return safeEqual(String(user || "").trim().toLowerCase(), USER.toLowerCase()) && safeEqual(pass || "", PASS);
}

function makeToken() {
  const payload = Buffer.from(JSON.stringify({ u: USER, exp: Math.floor(Date.now() / 1000) + MAX_AGE })).toString("base64url");
  return payload + "." + sign(payload);
}

function readCookie(req, name) {
  const raw = req.headers.cookie || "";
  for (const part of raw.split(";")) {
    const [k, ...v] = part.trim().split("=");
    if (k === name) return decodeURIComponent(v.join("="));
  }
  return null;
}

function isLoggedIn(req) {
  const tok = readCookie(req, COOKIE);
  if (!tok || !tok.includes(".")) return false;
  const [payload, sig] = tok.split(".");
  if (!safeEqual(sig, sign(payload))) return false;
  try {
    const { exp } = JSON.parse(Buffer.from(payload, "base64url").toString());
    return exp > Math.floor(Date.now() / 1000);
  } catch (e) {
    return false;
  }
}

function sessionCookie(value, maxAge) {
  const secure = process.env.VERCEL ? "; Secure" : "";
  return `${COOKIE}=${encodeURIComponent(value)}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure}`;
}

module.exports = { checkCredentials, makeToken, isLoggedIn, sessionCookie, MAX_AGE };
