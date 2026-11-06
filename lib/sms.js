// SMS de confirmation. À ADAPTER au fournisseur choisi (agrégateur SMS béninois) : variables SMS_API_URL, SMS_API_KEY, SMS_SENDER.
export async function sendSms(to, text) {
  const num = String(to || "").replace(/\D/g, "");
  if (!process.env.SMS_API_URL || !num) return false;
  try {
    const r = await fetch(process.env.SMS_API_URL, { method: "POST", headers: { "Content-Type": "application/json", Authorization: "Bearer " + process.env.SMS_API_KEY },
      body: JSON.stringify({ to: num.startsWith("229") ? num : "229" + num, from: process.env.SMS_SENDER || "Classio", message: text }) });
    return r.ok;
  } catch { return false; }
}
