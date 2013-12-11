from flask import current_app, render_template, jsonify

from .models import User

import json
import smtplib
import flask_sqlalchemy

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


def redirect_angular(url):
    return jsonify(redirect=url)


def send_email(to_addr, typ, **kwargs):
    conf = email_cfg[typ]
    send_addr = current_app.config['EMAIL_SENDER']
    send_name = current_app.config['EMAIL_SEND_NAME']
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
        host = smtplib.SMTP(current_app.config['EMAIL_SERVER'],
                            current_app.config['EMAIL_PORT'],
                            current_app.config['EMAIL_EHLO'],
                            timeout=2)
        host.set_debuglevel(current_app.config['EMAIL_DEBUG'])
        if current_app.config['EMAIL_USE_TLS']:
            host.starttls()
        host.ehlo()
        host.login(current_app.config['EMAIL_USERNAME'],
                   current_app.config['EMAIL_PASSWORD'])
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


def get_json_joined(*args, **kwargs):
    return json.dumps(get_joined(*args, **kwargs))


def get_joined(obj, join_prof="standard_join"):
    # If it's a list, join each of the items in the list and return modified
    # list
    if isinstance(obj, flask_sqlalchemy.BaseQuery) or isinstance(obj, list):
        lst = []
        for item in obj:
            lst.append(get_joined(item, join_prof=join_prof))
        return lst

    # split the join list into it's compoenents, obj to be removed, sub object
    # join data, and current object join values
    if isinstance(join_prof, basestring):
        join = getattr(obj, join_prof)
    else:
        join = join_prof

    remove = []
    sub_obj = []
    join_keys = []
    for key in join:
        if isinstance(key, basestring):
            if key.startswith('-'):
                remove.append(key[1:])
            else:
                join_keys.append(key)
        else:
            sub_obj.append(key)

    include_base = False
    try:
        join_keys.remove('__dont_mongo')
    except ValueError:
        include_base = True
    # run the primary object join
    join_vals = obj.jsonize(join_keys, raw=True)
    # catch our special config key
    if include_base:
        dct = obj.to_dict()
        # Remove keys from the bson that the join prefixes with a -
        for key in remove:
            dct.pop(key, None)
        dct.update(join_vals)
    else:
        dct = join_vals
    dct['_cls'] = obj.__class__.__name__

    # run all the subobject joins
    for conf in sub_obj:
        key = conf.get('obj')
        # allow the conf dictionary to specify a join profiel
        prof = conf.get('join_prof', "standard_join")
        subobj = getattr(obj, key)
        if subobj is not None:
            dct[key] = get_joined(subobj, join_prof=prof)
        else:
            current_app.logger.info(
                "Attempting to access attribute {} from {} resulted in {} "
                "type".format(key, type(obj), subobj))
            dct[key] = subobj
    return dct
