// Devuelve los datos de la liga solo con sesión iniciada. data/liga.json no se publica como archivo estático.
const { isLoggedIn } = require("./_auth");
const data = require("../data/liga.json");

module.exports = (req, res) => {
  res.setHeader("Cache-Control", "private, no-store");
  if (!isLoggedIn(req)) return res.status(401).json({ error: "Inicia sesión" });
  return res.status(200).json(data);
};
