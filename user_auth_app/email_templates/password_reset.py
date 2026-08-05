
PASSWORD_RESET_EMAIL_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #ffffff;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
        <tr>
            <td style="padding: 60px 20px;">
                <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="margin: 0 auto;">
                    <tr>
                        <td align="center" style="padding-bottom: 40px;">
                            <img src="cid:logo_cid" alt="Videoflix" width="200" style="display: block; margin: 0 auto;">                         
                        </td>
                    </tr>
                    <tr>
                        <td>
                            <p style="color: #333333; font-size: 16px; line-height: 1.6; margin-bottom: 24px;">
                                Hello,<br><br>
                                We received a request to reset your password for your Videoflix account. If you made this request, please click the button below:
                            </p>
                            <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                                <tr>
                                    <td align="center" style="border-radius: 25px;" bgcolor="#2948ff">
                                        <a href="{reset_url}" target="_blank" style="font-size: 16px; color: #ffffff; background-color: #2948ff; border: none; border-radius: 25px; padding: 14px 32px; text-decoration: none; display: inline-block; font-weight: bold;">
                                            Reset password
                                        </a>
                                    </td>
                                </tr>
                            </table>
                            <p style="color: #666666; font-size: 16px; line-height: 1.6; margin-top: 32px;">
                                This link is valid for 24 hours.<br><br>
                                If you did not request a password reset, please ignore this email.<br><br>
                                Best regards,<br>
                                Your Videoflix Team.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def render_password_reset_html(reset_url):
    return PASSWORD_RESET_EMAIL_HTML_TEMPLATE.format(reset_url=reset_url)
