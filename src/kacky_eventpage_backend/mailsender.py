from urllib.error import HTTPError

import sendgrid
from sendgrid.helpers.mail import Content, Email, Mail, To


class MailSender:
    def __init__(self, config, secrets):
        self.sendgrid_key = secrets["sendgrid_api_key"]

    def send_pwd_reset_mail(self, mail, token):
        sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_key)
        from_email = Email("kacky@dingens.me")
        to_email = To(mail)
        subject = "Kacky.gg Password Reset"
        content = Content(
            "text/plain",
            "Heyho!\n\nForgot your password on kacky.gg? Gotcha!\n\n"
            f"Here is your password reset token:   {token}\n\n"
            "Have fun!\ncorkscrew"
            "\n\n\n\nYou received this mail because somebody used your username and email address "
            "in the password reset form.\nIf that wasn't you, just don't give the token to anybody and "
            "you'll be fine.\nFor further questions, you'll find me on Discord: corkscrew#0874",
        )
        mail = Mail(from_email, to_email, subject, content)
        try:
            response = sg.client.mail.send.post(request_body=mail.get())
        except HTTPError:
            return False
        if response.status_code < 300:
            return True
        return False
