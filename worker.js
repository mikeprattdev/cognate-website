// Cognate Audio site Worker (Workers + Static Assets model).
// - POST /api/contact    → validates + emails the Cognate inbox via Resend
// - POST /api/subscribe  → adds an email to the Resend Audience (newsletter)
// - Everything else      → falls through to static assets (ASSETS binding)

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/contact" && request.method === "POST") {
      return handleContact(request, env);
    }
    if (url.pathname === "/api/subscribe" && request.method === "POST") {
      return handleSubscribe(request, env);
    }

    return env.ASSETS.fetch(request);
  },
};

async function readPayload(request) {
  const ct = request.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    return await request.json();
  }
  const form = await request.formData();
  return Object.fromEntries(form.entries());
}

async function handleContact(request, env) {
  let data;
  try {
    data = await readPayload(request);
  } catch {
    return jsonResp({ ok: false, error: "Invalid request body" }, 400);
  }

  const name = (data.name || "").toString().trim();
  const email = (data.email || "").toString().trim();
  const subject = (data.subject || "general").toString().trim();
  const message = (data.message || "").toString().trim();
  const honeypot = (data._gotcha || "").toString().trim();

  if (honeypot) return jsonResp({ ok: true });

  if (!name || !email || !message) {
    return jsonResp({ ok: false, error: "Please fill in name, email and message." }, 400);
  }
  if (!isEmail(email)) {
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
    console.error("Resend (contact) error", resendResp.status, body);
    return jsonResp({ ok: false, error: "Could not send your message. Please try again." }, 502);
  }

  // Optional newsletter opt-in checkbox. Best-effort: a failure here
  // doesn't fail the contact submission.
  const subscribe = data.subscribe;
  const wantsNewsletter =
    subscribe === true || subscribe === "on" || subscribe === "1" || subscribe === 1;
  if (wantsNewsletter && env.RESEND_AUDIENCE_ID) {
    try {
      await fetch(
        `https://api.resend.com/audiences/${encodeURIComponent(env.RESEND_AUDIENCE_ID)}/contacts`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.RESEND_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ email, first_name: name, unsubscribed: false }),
        }
      );
    } catch (err) {
      console.error("Newsletter add via contact form failed", err);
    }
  }

  return jsonResp({ ok: true });
}

async function handleSubscribe(request, env) {
  let data;
  try {
    data = await readPayload(request);
  } catch {
    return jsonResp({ ok: false, error: "Invalid request body" }, 400);
  }

  const email = (data.email || "").toString().trim();
  const honeypot = (data._gotcha || "").toString().trim();

  if (honeypot) return jsonResp({ ok: true });
  if (!email || !isEmail(email)) {
    return jsonResp({ ok: false, error: "Please enter a valid email address." }, 400);
  }
  if (!env.RESEND_API_KEY || !env.RESEND_AUDIENCE_ID) {
    return jsonResp({ ok: false, error: "Newsletter is not configured yet." }, 500);
  }

  const audId = env.RESEND_AUDIENCE_ID;
  const addResp = await fetch(
    `https://api.resend.com/audiences/${encodeURIComponent(audId)}/contacts`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, unsubscribed: false }),
    }
  );

  // Resend returns 200 on add and 200/409-style for already-subscribed,
  // depending on API version. Treat any 2xx as success and surface a
  // friendly note for duplicates so the user gets feedback either way.
  let addJson = null;
  try { addJson = await addResp.json(); } catch {}
  const alreadyExists =
    addResp.status === 409 ||
    (addJson && (addJson.name === "validation_error" || addJson.name === "duplicate") &&
     /exist/i.test(addJson.message || ""));

  if (!addResp.ok && !alreadyExists) {
    console.error("Resend (subscribe) error", addResp.status, addJson);
    return jsonResp({ ok: false, error: "Could not subscribe. Please try again." }, 502);
  }

  // Welcome email. Skipping if duplicate to avoid re-spamming returnees.
  if (!alreadyExists) {
    const from = env.CONTACT_FROM_EMAIL || "hello@cognate.audio";
    const welcomeResp = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        from: `Cognate Audio <${from}>`,
        to: [email],
        subject: "Thanks for subscribing — Cognate Audio",
        text:
          "Thanks for signing up to the Cognate Audio newsletter.\n\n" +
          "We'll send the occasional update when we ship a new block, " +
          "post a setting we're proud of, or have something useful to share — " +
          "no flood, no fluff.\n\n" +
          "Catch up on what's out so far: https://cognate.audio/blocks\n\n" +
          "— Mike\n" +
          "Cognate Audio\n",
      }),
    });
    if (!welcomeResp.ok) {
      const body = await welcomeResp.text();
      console.error("Resend (welcome) error", welcomeResp.status, body);
      // Non-fatal: subscription succeeded, welcome email failed.
    }
  }

  return jsonResp({
    ok: true,
    duplicate: alreadyExists,
  });
}

function isEmail(s) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
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
