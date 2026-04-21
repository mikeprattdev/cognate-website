// Cognate Audio site Worker (Workers + Static Assets model).
// - POST /api/contact    → validates + forwards to Resend, returns JSON
// - Everything else      → falls through to static assets (ASSETS binding)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/contact" && request.method === "POST") {
      return handleContact(request, env);
    }

    return env.ASSETS.fetch(request);
  },
};

async function handleContact(request, env) {
  let data;
  try {
    const ct = request.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      data = await request.json();
    } else {
      const form = await request.formData();
      data = Object.fromEntries(form.entries());
    }
  } catch {
    return jsonResp({ ok: false, error: "Invalid request body" }, 400);
  }

  const name = (data.name || "").toString().trim();
  const email = (data.email || "").toString().trim();
  const subject = (data.subject || "general").toString().trim();
  const message = (data.message || "").toString().trim();
  const honeypot = (data._gotcha || "").toString().trim();

  // Silent success for bots that filled the honeypot.
  if (honeypot) return jsonResp({ ok: true });

  if (!name || !email || !message) {
    return jsonResp({ ok: false, error: "Please fill in name, email and message." }, 400);
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return jsonResp({ ok: false, error: "That email address doesn't look right." }, 400);
  }
  if (message.length > 10000) {
    return jsonResp({ ok: false, error: "Message too long (max 10,000 characters)." }, 400);
  }

  if (!env.RESEND_API_KEY) {
    return jsonResp({ ok: false, error: "Mail is not configured yet." }, 500);
  }

  const to = env.CONTACT_TO_EMAIL || "hello@cognate.audio";
  const from = env.CONTACT_FROM_EMAIL || "contact@cognate.audio";
  const subjectLine = `[Cognate Audio] ${subject} — ${name}`;
  const textBody =
    `New message from cognate.audio contact form\n\n` +
    `Name:    ${name}\n` +
    `Email:   ${email}\n` +
    `Subject: ${subject}\n\n` +
    `${message}\n`;

  const resendResp = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: `Cognate Audio Contact <${from}>`,
      to: [to],
      reply_to: email,
      subject: subjectLine,
      text: textBody,
    }),
  });

  if (!resendResp.ok) {
    const body = await resendResp.text();
    console.error("Resend error", resendResp.status, body);
    return jsonResp({ ok: false, error: "Could not send your message. Please try again." }, 502);
  }

  return jsonResp({ ok: true });
}

function jsonResp(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}
