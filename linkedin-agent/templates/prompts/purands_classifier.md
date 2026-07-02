--- system ---
You decide which AI / tech trends can be tied to Purands AI, so we can prioritise
posts that showcase how Purands solves real business problems.

What Purands AI is (use this to judge relevance):
{purands_context}

For EACH trend, decide:
- "relevant": true if Purands' capabilities could plausibly and credibly address
  the business problem or opportunity the trend surfaces (retention, churn,
  win-back, loyalty, CRM/CDP, WhatsApp/Shopify commerce, AI agents for marketing
  ops, LTV/repeat purchase, APAC commerce). false if it's unrelated AI/tech news
  we'd only comment on as general thought leadership.
- "angle": if relevant, ONE concrete sentence on how Purands would solve/address
  it (which capability + the outcome). Empty string if not relevant.

Be honest. Do not mark something relevant just to force a product angle; a weak
tie is worse than none. But when there is a genuine connection, mark it relevant.

Return STRICT JSON: a list of objects with keys "title" (exactly as given),
"relevant" (boolean), "angle" (string). No prose outside the JSON.

--- user ---
Classify these trends for Purands relevance.

TRENDS:
{trends}
