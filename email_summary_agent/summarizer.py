"""
Email summarizer.

Groups fetched emails by account and builds an HTML + plain-text
daily digest ready for delivery.
"""

from collections import defaultdict
from datetime import datetime


def _escape_html(text):
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_summary(emails, summary_date=None):
    """
    Build a daily email summary from a list of email dicts.

    Returns (subject, plain_text, html_text).
    """
    if summary_date is None:
        summary_date = datetime.now().strftime("%A, %B %d, %Y")

    subject = f"Daily Email Summary - {summary_date}"

    if not emails:
        plain = f"Daily Email Summary - {summary_date}\n\nNo new emails in the last 24 hours."
        html = _build_html_wrapper(
            summary_date,
            "<p style='color:#666;'>No new emails in the last 24 hours.</p>",
        )
        return subject, plain, html

    # Group by account
    by_account = defaultdict(list)
    for em in emails:
        by_account[em["account_label"]].append(em)

    # --- Plain text ---
    plain_parts = [f"Daily Email Summary - {summary_date}", f"Total: {len(emails)} email(s)\n"]
    for acct, msgs in by_account.items():
        plain_parts.append(f"{'='*60}")
        plain_parts.append(f"  {acct} ({len(msgs)} message{'s' if len(msgs) != 1 else ''})")
        plain_parts.append(f"{'='*60}")
        for m in msgs:
            plain_parts.append(f"\n  From:    {m['from']}")
            plain_parts.append(f"  Subject: {m['subject']}")
            plain_parts.append(f"  Date:    {m['date']}")
            snippet = m.get("snippet", "")
            if snippet:
                plain_parts.append(f"  Preview: {snippet[:200]}")
            plain_parts.append(f"  {'-'*40}")
    plain_text = "\n".join(plain_parts)

    # --- HTML ---
    html_sections = []
    for acct, msgs in by_account.items():
        rows = ""
        for m in msgs:
            snippet = _escape_html(m.get("snippet", "")[:200])
            rows += f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #eee;">
                <strong style="color:#1a5d1a;">{_escape_html(m['subject'])}</strong><br>
                <span style="color:#555;font-size:13px;">From: {_escape_html(m['from'])}</span><br>
                <span style="color:#888;font-size:12px;">{_escape_html(m['date'])}</span>
                {f'<p style="color:#444;font-size:13px;margin:6px 0 0;">{snippet}</p>' if snippet else ''}
              </td>
            </tr>"""

        html_sections.append(f"""
        <div style="margin-bottom:24px;">
          <h2 style="color:#1a5d1a;font-size:16px;margin:0 0 8px;padding:8px 12px;
                     background:#f0f7f0;border-left:4px solid #1a5d1a;">
            {_escape_html(acct)}
            <span style="color:#888;font-weight:normal;font-size:13px;">
              &mdash; {len(msgs)} message{'s' if len(msgs) != 1 else ''}
            </span>
          </h2>
          <table width="100%" cellpadding="0" cellspacing="0"
                 style="border:1px solid #e0e0e0;border-radius:6px;">
            {rows}
          </table>
        </div>""")

    body_html = "\n".join(html_sections)
    total_line = f"<p style='color:#555;font-size:14px;'><strong>{len(emails)}</strong> email(s) across <strong>{len(by_account)}</strong> account(s)</p>"
    html_text = _build_html_wrapper(summary_date, total_line + body_html)

    return subject, plain_text, html_text


def _build_html_wrapper(date_str, body):
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:600px;margin:20px auto;background:#fff;border-radius:8px;
              box-shadow:0 2px 8px rgba(0,0,0,0.08);overflow:hidden;">
    <div style="background:#1a5d1a;padding:20px 24px;">
      <h1 style="margin:0;color:#fff;font-size:20px;">Daily Email Summary</h1>
      <p style="margin:4px 0 0;color:#c9a227;font-size:14px;">{_escape_html(date_str)}</p>
    </div>
    <div style="padding:20px 24px;">
      {body}
    </div>
    <div style="padding:12px 24px;background:#f9f9f9;text-align:center;
                border-top:1px solid #eee;">
      <p style="margin:0;color:#999;font-size:11px;">
        Sent by The Golf Fellowship Email Summary Agent
      </p>
    </div>
  </div>
</body>
</html>"""
