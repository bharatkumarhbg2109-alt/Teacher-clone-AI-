"""Transactional email via Resend (no-op if no API key)."""
import html as html_mod

from app.config import settings


async def send_invitation_email(
    to_email: str, inviter_name: str, org_name: str, role: str, invitation_url: str
) -> bool:
    if not settings.RESEND_API_KEY:
        # Dev: log instead of send.
        print(f"[email] invite {to_email} to {org_name} as {role}: {invitation_url}")
        return True
    import resend

    resend.api_key = settings.RESEND_API_KEY
    org_safe = html_mod.escape(org_name)
    inviter_safe = html_mod.escape(inviter_name)
    role_safe = html_mod.escape(role)
    email_html = f"""
    <div style="font-family:sans-serif;max-width:480px;margin:auto">
      <h2>You've been invited to {org_safe}</h2>
      <p>{inviter_safe} invited you to join <b>{org_safe}</b> on TeachClone as a <b>{role_safe}</b>.</p>
      <p><a href="{invitation_url}"
            style="background:#6366F1;color:#fff;padding:12px 20px;border-radius:8px;
                   text-decoration:none">Accept invitation</a></p>
      <p style="color:#888;font-size:12px">This invitation expires in 7 days.</p>
    </div>
    """
    resend.Emails.send(
        {
            "from": settings.FROM_EMAIL,
            "to": to_email,
            "subject": f"You've been invited to join {org_name} on TeachClone",
            "html": email_html,
        }
    )
    return True
