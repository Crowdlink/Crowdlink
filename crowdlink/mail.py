from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template, url_for

import smtplib


class EmailBase(object):

    html_template = None
    plain_template = None
    subject = None

    def __init__(self):
        """ Should be used to setup all arguments to the template rendering """
        self.email_server = current_app.config.get('email_server')
        self.email_ehlo = current_app.config.get('email_ehlo')
        self.email_debug = bool(current_app.config.get('email_debug'))
        self.email_tls = bool(current_app.config.get('email_use_tls'))
        self.email_port = current_app.config.get('email_port', 25)
        self.email_timeout = current_app.config.get('email_timeout', 2)
        self.email_username = current_app.config.get('email_username', '')
        self.email_password = current_app.config.get('email_password', '')
        self.send_real = current_app.config.get('send_emails', True)

        self.plain_context = {}
        self.html_context = {}

    def send(self, to_addr, force_send=None):
        # allow us to override the application level config manually
        if force_send is not None:
            self.send_real = force_send

        # if we shouldn't actually send, then don't
        if self.send_real is False:
            current_app.logger.debug(
                "Not sending email because configuration or override")
            return True

        send_addr = current_app.config['email_send_address']
        send_name = current_app.config['email_send_name']

        msg = MIMEMultipart('alternative')
        msg['Subject'] = self.subject
        msg['From'] = "{0} <{1}>".format(send_name, send_addr)
        msg['To'] = to_addr

        if self.plain_template is None and self.html_template is None:
            raise AttributeError(
                "There must be at least an html or plain template")

        if self.plain_template is not None:
            plain = render_template(self.plain_template, **self.plain_context)
            msg.attach(MIMEText(plain, 'plain'))
        if self.html_template is not None:
            html = render_template(self.html_template, **self.html_context)
            msg.attach(MIMEText(html, 'html'))

        try:
            host = smtplib.SMTP(host=self.email_server,
                                port=self.email_port,
                                local_hostname=self.email_ehlo,
                                timeout=self.email_timeout)
            host.set_debuglevel(self.email_debug)
            if self.email_tls:
                host.starttls()
            if self.email_ehlo:
                host.ehlo()

            host.login(self.email_username, self.email_password)
            host.sendmail(send_addr,
                          to_addr,
                          msg.as_string())
            host.quit()
            return True
        except smtplib.SMTPException:
            current_app.logger.warn('Email unable to send', exc_info=True)
            return False


class TestEmail(EmailBase):
    """ a email used to test our systems and template """

    html_template = "email/base.html"
    subject = 'A test of the Crowdlink.io email system'

    def __init__(self):
        super(TestEmail, self).__init__()
        body = """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed quis
        feugiat tellus. Etiam euismod adipiscing massa, in mollis nisi aliquet
        at. Nunc varius arcu ac tellus dictum interdum. Etiam porta arcu lorem,
        et consectetur elit tempus ac. Ut feugiat mi eu nulla condimentum, nec
        rutrum dolor vestibulum. Morbi accumsan et enim hendrerit suscipit.
        Suspendisse eu ante id nunc aliquet congue vel id magna.
        """
        url = url_for('angular_root', _external=True)
        self.html_context = dict(
            title='This is a simple test email',
            one_button_row=True,
            body=body,
            button_one_text='Home',
            button_one_link=url,
            sincere=True)


class ActivationEmail(EmailBase):
    """ Email for creating an activation email """

    html_template = "email/base.html"
    subject = 'Activate your Crowdlink.io Account'

    def __init__(self, email_obj):
        super(ActivationEmail, self).__init__()
        if email_obj.activate_hash is None:
            raise AttributeError("Tried to send an activation email for an "
                                 "email with no activation hash")
        body = """
        A user has registered an account with Crowdlink.io and requested
        that it be activated. If this wasn't you, you can safely ignore this
        email. Otherwise, please click the link below.
        """
        activation_href = url_for('activate_email',
                                  _external=True,
                                  address=email_obj.address,
                                  hash=email_obj.activate_hash)

        self.html_context = dict(
            title='Please activate your Crowdlink account',
            one_button_row=True,
            body=body,
            button_one_text='Activate',
            button_one_link=activation_href,
            sincere=True)


class RecoverEmail(EmailBase):
    """ Email for recovering account password """

    html_template = "email/base.html"
    subject = 'Recover your account password at Crowdlink'

    def __init__(self, user_obj):
        super(RecoverEmail, self).__init__()
        if user_obj.recover_hash is None:
            raise AttributeError("Tried to send a recovery email for a "
                                 "user with no recovery hash")
        body = """
        Someone has requested to recover your account password for your account
        on Crowdlink.io. To change your password click below and follow the
        link.
        """
        recovery_href = url_for('angular_root',
                                _external=True,
                                _anchor='/recover/{hash}/{user_id}'
                                .format(hash=user_obj.recover_hash,
                                        user_id=user_obj.id))

        self.html_context = dict(
            title='Recover your account on Crowdlink',
            one_button_row=True,
            body=body,
            button_one_text='Recover',
            button_one_link=recovery_href,
            sincere=True)
