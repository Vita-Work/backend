from __future__ import annotations

# ruff: noqa: E501
from html import escape


def render_sign_in_code_email(
    *,
    code: str,
    verification_url: str,
    expires_in_minutes: int,
) -> str:
    safe_code = escape(code)
    safe_url = escape(verification_url, quote=True)
    safe_minutes = escape(str(expires_in_minutes))
    preheader = f"Your Vitable sign-in code is {code}. It expires in {expires_in_minutes} minutes."

    return f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>Your Vitable sign-in code</title>
  </head>
  <body style="margin:0;padding:0;background-color:#f7f4fb;color:#20132b;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
      {escape(preheader)}
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f7f4fb;margin:0;padding:0;width:100%;">
      <tr>
        <td align="center" style="padding:32px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:600px;width:100%;">
            <tr>
              <td align="center" style="padding-bottom:18px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="border:1px solid #eadff6;border-radius:999px;background-color:#ffffff;padding:8px 14px;font-size:11px;line-height:1;color:#ff6a68;font-weight:700;letter-spacing:0.14em;text-transform:uppercase;">
                      Secure sign-in
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td style="background-color:#1f112a;border-radius:28px;padding:32px 28px 24px 28px;box-shadow:0 24px 60px rgba(36,20,58,0.18);">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="padding-bottom:24px;">
                      <div style="font-size:32px;line-height:1.05;color:#ffffff;font-weight:600;letter-spacing:-0.03em;">
                        Your sign-in code for
                        <span style="color:#ff6a68;font-style:italic;">Vitable</span>
                      </div>
                    </td>
                  </tr>

                  <tr>
                    <td style="padding-bottom:22px;font-size:16px;line-height:1.65;color:#d4c8df;">
                      Use this code to continue signing in. It expires in <strong style="color:#ffffff;">{safe_minutes} minutes</strong>.
                    </td>
                  </tr>

                  <tr>
                    <td style="padding-bottom:24px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                          <td align="center" style="border-radius:22px;background:linear-gradient(135deg,#fff7f7 0%,#fff2ef 100%);border:1px solid rgba(255,106,104,0.22);padding:22px 16px;">
                            <div style="font-size:13px;line-height:1;color:#725d86;font-weight:600;letter-spacing:0.12em;text-transform:uppercase;padding-bottom:12px;">
                              Verification code
                            </div>
                            <div style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:38px;line-height:1;color:#20132b;font-weight:700;letter-spacing:0.32em;text-indent:0.32em;">
                              {safe_code}
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>

                  <tr>
                    <td align="center" style="padding-bottom:22px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                          <td align="center" bgcolor="#ff6a68" style="border-radius:999px;">
                            <a href="{safe_url}" style="display:inline-block;padding:14px 22px;font-size:14px;line-height:1;color:#20132b;font-weight:700;text-decoration:none;">
                              Open Vitable
                            </a>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>

                  <tr>
                    <td style="border-top:1px solid rgba(255,255,255,0.10);padding-top:18px;font-size:13px;line-height:1.7;color:#a794bb;">
                      If you did not request this email, you can safely ignore it.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td align="center" style="padding-top:16px;font-size:12px;line-height:1.6;color:#8f7ea2;">
                Vitable · Secure access email
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def render_sign_in_code_text(
    *,
    code: str,
    verification_url: str,
    expires_in_minutes: int,
) -> str:
    return (
        f"Your Vitable sign-in code is {code}.\n\n"
        f"It expires in {expires_in_minutes} minutes.\n\n"
        f"Open {verification_url} to continue.\n\n"
        "If you did not request this email, you can safely ignore it."
    )
