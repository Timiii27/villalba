const { checkCredentials, makeToken, sessionCookie, MAX_AGE } = require("./_auth");

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Método no permitido" });
  }
  let body = req.body;
  if (typeof body === "string") {
    try { body = JSON.parse(body); } catch (e) { body = {}; }
  }
  const { user, pass } = body || {};
  if (!checkCredentials(user, pass)) {
    await new Promise((r) => setTimeout(r, 400)); // frena intentos a lo bruto
    return res.status(401).json({ error: "Usuario o contraseña incorrectos." });
  }
  res.setHeader("Set-Cookie", sessionCookie(makeToken(), MAX_AGE));
  return res.status(200).json({ ok: true });
};
