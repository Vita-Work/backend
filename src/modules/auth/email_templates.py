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
    preheader = f"Your Vita sign-in code is {code}. It expires in {expires_in_minutes} minutes."

    return f"""\
<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>Your Vita sign-in code</title>
  </head>
  <body style="margin:0;padding:0;background-color:#fafafa;color:#111111;font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
      {escape(preheader)}
    </div>

    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#fafafa;margin:0;padding:0;width:100%;">
      <tr>
        <td align="center" style="padding:48px 16px;">
          <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:480px;width:100%;text-align:left;">
            <tr>
              <td style="background-color:#ffffff;border:1px solid #e5e5e5;border-radius:12px;padding:40px;box-shadow:0 4px 24px rgba(0,0,0,0.02);">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                  <tr>
                    <td style="padding-bottom:32px;">
                      <div style="display:inline-block;padding:6px 10px;background-color:#f4f4f5;border:1px solid #e4e4e7;border-radius:6px;font-size:11px;font-weight:600;color:#52525b;letter-spacing:0.02em;text-transform:uppercase;">
                        Secure Sign-In
                      </div>
                    </td>
                  </tr>

                  <tr>
                    <td style="padding-bottom:16px;">
                      <div style="font-size:24px;line-height:1.2;color:#09090b;font-weight:600;letter-spacing:-0.02em;">
                        Your sign-in code for Vita
                      </div>
                    </td>
                  </tr>

                  <tr>
                    <td style="padding-bottom:32px;font-size:15px;line-height:1.6;color:#52525b;">
                      Use this code to continue signing in. It expires in <strong style="color:#09090b;font-weight:600;">{safe_minutes} minutes</strong>.
                    </td>
                  </tr>

                  <tr>
                    <td style="padding-bottom:32px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                          <td align="center" style="border-radius:8px;background-color:#f8fafc;border:1px solid #e2e8f0;padding:24px 16px;">
                            <div style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;font-size:36px;line-height:1;color:#0f172a;font-weight:700;letter-spacing:0.25em;text-indent:0.25em;">
                              {safe_code}
                            </div>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>

                  <tr>
                    <td align="center" style="padding-bottom:32px;">
                      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                          <td align="center">
                            <a href="{safe_url}" style="display:block;width:100%;padding:14px 0;background-color:#09090b;border-radius:8px;font-size:14px;line-height:1;color:#ffffff;font-weight:500;text-decoration:none;text-align:center;">
                              Sign in to Vita
                            </a>
                          </td>
                        </tr>
                      </table>
                    </td>
                  </tr>

                  <tr>
                    <td style="border-top:1px solid #e4e4e7;padding-top:24px;font-size:13px;line-height:1.6;color:#71717a;">
                      If you did not request this email, you can safely ignore it.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>

            <tr>
              <td align="center" style="padding-top:24px;font-size:12px;line-height:1.6;color:#a1a1aa;">
                Vita &middot; Secure Access
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
        f"Your Vita sign-in code is {code}.\n\n"
        f"It expires in {expires_in_minutes} minutes.\n\n"
        f"Open {verification_url} to continue.\n\n"
        "If you did not request this email, you can safely ignore it."
    )
