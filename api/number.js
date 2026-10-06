export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
    return res.status(204).end();
  }

  const { number } = req.query;
  const key = req.query.key || req.query.slug || null;

  // ⚠️ Common warning jo har response me jaayega
  const warning =;
    "⚠️ WARNING: This API is for educational and personal use only. " +
    "Any misuse, illegal or unauthorized activity is strictly prohibited. " +
    "Misuse will result in permanent key ban.";

  if (!number) {
    return res.status(400).json({
      status: "error",
      message: "number parameter required",
      warning,
      developer: "Suvam",
      youtube: "https://youtube.com/@suvammodx?si=cxO6TkGYKDnbKhNG"
    });
  }

  if (!key) {
    return res.status(401).json({
      status: "error",
      message: "key required",
      warning,
      developer: "Suvam",
      youtube: "https://youtube.com/@suvammodx?si=cxO6TkGYKDnbKhNG"
    })
  }

  // ✅ Ab key SUVAM- se start honi chahiye
  if (!key.startsWith('SUVAM-')) {
    return res.status(401).json({
      status: "error",
      message: "invalid key (must start with SUVAM-)",
      warning,
      developer: "Suvam"
    });
  }

  try {
    const upstream = await fetch(
      `https://numberinfo-api-adibhai.vercel.app/api/number?number=${encodeURIComponent(number)}`
    );
    const data = await upstream.json();

    return res.status(200).json({
      status: data.status || "success",
      number: data.number || number,
      data: data.data || null,
      warning,
      developer: "Suvam",
      youtube: "https://youtube.com/@suvammodx?si=cxO6TkGYKDnbKhNG"
    });
  } catch (err) {
    return res.status(500).json({
      status: "error",
      message: "upstream fetch failed",
      warning,
      developer: "Suvam",
      youtube: "https://youtube.com/@suvammodx?si=cxO6TkGYKDnbKhNG"
    });
  }
}
