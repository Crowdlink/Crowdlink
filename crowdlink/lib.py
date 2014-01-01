from flask import current_app, render_template

import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


email_cfg = {
    'confirm': {'subject': 'Confirm your email address on Featurelet',
                'html_template': 'email/confirm.html',
                'plain_template': 'email/confirm_plain.html'},
    'test': {'subject': 'Admin test email from Featurelet',
             'html_template': 'email/test.html',
             'plain_template': 'email/test_plain.html'}
}


def send_email(to_addr, typ, **kwargs):
    conf = email_cfg[typ]
    send_addr = current_app.config['email_send_address']
    send_name = current_app.config['email_send_name']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = conf['subject']
    msg['From'] = "{0} <{1}>".format(send_name, send_addr)
    msg['To'] = to_addr
    if 'plain_template' in conf:
        msg.attach(MIMEText(render_template(conf['plain_template'], **kwargs),
                            'plain'))
    if 'html_template' in conf:
        msg.attach(MIMEText(render_template(conf['html_template'], **kwargs),
                            'html'))

    try:
        host = smtplib.SMTP(current_app.config['email_server'],
                            current_app.config['email_port'],
                            current_app.config['email_ehlo'],
                            timeout=2)
        host.set_debuglevel(current_app.config['email_debug'])
        if current_app.config['email_use_tls']:
            host.starttls()
        host.ehlo()
        host.login(current_app.config['email_username'],
                   current_app.config['email_password'])
        current_app.logger.info(host.sendmail(send_addr,
                                              to_addr,
                                              msg.as_string()))
        return True
    except KeyError:
        current_app.logger.exception(
            "Missing required server configuration for Email config")
    except Exception:
        from traceback import format_exc
        current_app.logger.info(
            "=============================================================\n" +
            "Failed to send mail: {0}\n".format(format_exc()) +
            "=============================================================\n"
        )
        return False
