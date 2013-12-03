from flask import url_for, session, g, current_app, request, flash, render_template, jsonify

from . import db, github, app
from .models import User

import sys
import mongoengine
import json
import smtplib

from bson.json_util import _json_convert
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import sqlalchemy
import flask_sqlalchemy

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
    send_addr = app.config['EMAIL_SENDER']
    send_name = app.config['EMAIL_SEND_NAME']
    msg = MIMEMultipart('alternative')
    msg['Subject'] = conf['subject']
    msg['From'] = "{0} <{1}>".format(send_name, send_addr)
    msg['To'] = to_addr
    if 'plain_template' in conf:
        msg.attach(MIMEText(render_template(conf['plain_template'], **kwargs), 'plain'))
    if 'html_template' in conf:
        msg.attach(MIMEText(render_template(conf['html_template'], **kwargs), 'html'))

    try:
        host = smtplib.SMTP(app.config['EMAIL_SERVER'],
                            app.config['EMAIL_PORT'],
                            app.config['EMAIL_EHLO'],
                            timeout=2)
        host.set_debuglevel(app.config['EMAIL_DEBUG'])
        if app.config['EMAIL_USE_TLS']:
            host.starttls()
        host.ehlo()
        host.login(app.config['EMAIL_USERNAME'], app.config['EMAIL_PASSWORD'])
        current_app.logger.info(host.sendmail(send_addr,
                      to_addr,
                      msg.as_string()))
        return True
    except KeyError:
        current_app.logger.exception("Missing required server configuration for Email config")
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


def obj_to_dict(model):
    """ converts a sqlalchemy model to a dictionary """
    # first we get the names of all the columns on your model
    columns = [c.key for c in sqlalchemy.orm.class_mapper(model.__class__).columns]
    # then we return their values in a dict
    return dict((c, getattr(model, c)) for c in columns)


def get_joined(obj, join_prof="standard_join"):
    # If it's a list, join each of the items in the list and return modified
    # list
    current_app.logger.debug("Attempting to join in " + str(type(obj)))
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
    current_app.logger.debug("Join list " + str(join))
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
        dct = obj_to_dict(obj)
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
        current_app.logger.info(
            "Attempting to access attribute {} from {} resulted in {} "
            "type".format(key, type(obj), subobj))
        if subobj is not None:
            dct[key] = get_joined(subobj, join_prof=prof)
        else:
            dct[key] = subobj
    return dct

def catch_error_graceful(form=None, out_flash=False):
    """ This is a utility function that handles exceptions that might be omitted
    from Mongoengine in a graceful, patterned way. In production these errors
    should never really happen, so they can be handled uniformly logging and user
    return. It is called by the safe_save utility. """
    exc, txt, tb = sys.exc_info()
    def log(msg):
        from pprint import pformat
        from traceback import format_exc
        exc = format_exc()
        try:
            current_app.logger.warn(
                "=============================================================\n" +
                "{0}\nRequest dump: {1}\n{2}\n".format(msg, pformat(vars(request)), exc) +
                "=============================================================\n"
            )
        except RuntimeError:
            print("{0}\n\n{1}\n".format(msg, exc))

    # default to danger....
    cat = "danger"
    if exc is sqlalchemy.exc:
        msg = ('An unknown database replated exception occured')
        log("Unknown error")

    if form:
        form.start.add_msg(message=msg, type=cat)
    elif out_flash:
        flash(msg, category=cat)


def distribute_event(sender, event, type, subscriber_send=False, self_send=False):
    """ A function that will de-normalize an event by distributing it to requested
    subscribing event lists. This only handles the logic and action of distribution,
    and not the initial routing which is instead handled on notifications
    distribute method """
    # Distribute to all subscribers who have the right options
    if subscriber_send:
        for sub in sender.subscribers:
            # If they wish to recieve this type of event
            if getattr(sub, type, False):
                # This could be optimized by loading all users at once, instead of
                # resolving one at a time
                sub.user.events.append(event)
                sender.safe_save()
                current_app.logger.debug(
                    "{0} was distributed event '{1}' for object {2}".format(sub.user.username, type, sender))
            else:
                current_app.logger.debug(
                    "{0} was not distributed event '{1}' because of settings, even though subscribed".format(sub.user, type))

    # Add the event to the senders own list if there is one
    if self_send:
        if isinstance(sender, User):
            sender.public_events.append(event)
            sender.safe_save()
        else:
            sender.events = sender.events + [event]
            sender.safe_save()
