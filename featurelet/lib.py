from flask import url_for, session, g, current_app, request

from featurelet import db, github, app
from featurelet.models import User

import sys
import mongoengine

def catch_error_graceful(form=None):
    # grab current exception information
    exc, txt, tb = sys.exc_info()

    def log(msg):
        from pprint import pformat
        from traceback import format_exc
        current_app.logger.warn(
            "=============================================================\n" +
            "{0}\nRequest dump: {1}\n{2}\n".format(msg, pformat(vars(request)), format_exc()) +
            "=============================================================\n"
        )

    if exc is mongoengine.errors.ValidationError:
        if form:
            form.start.add_error({'message': 'A database schema validation error has occurred. This has been logged with a high priority.'})
        log("A validation occurred.")
    elif exc is mongoengine.errors.InvalidQueryError:
        if form:
            form.start.add_error({'message': 'A database schema validation error has occurred. This has been logged with a high priority.'})
        log("An inconsistency in the models was detected")
    elif exc is mongoengine.errors.NotUniqueError:
        if form:
            form.start.add_error({'message': 'A duplication error happended on the datastore side, one of your values is not unique. This has been logged.'})
        log("A duplicate check on the database side was not caught")
    elif exc in (mongoengine.errors.OperationError, mongoengine.errors.DoesNotExist):
        if form:
            form.start.add_error({'message': 'An unknown database error. This has been logged.'})
        log("An unknown operation error occurred")
    else:
        if form:
            form.start.add_error({'message': 'An unknown error has occurred'})
        log("")


def distribute_event(sender, event, type, subscriber_send=False, self_send=False):
    """ A function that will de-normalize an event by distributing it to all
    subscribing event lists """
    # Distribute to all subscribers who have the right options if asked
    if subscriber_send:
        for sub in sender.subscribers:
            # If they wish to recieve this type of event
            if getattr(sub, type, False):
                # This could be optimized by loading all users at once, instead of
                # resolving one at a time
                sub.user.events.append(event)
                sub.user.save()

    # Add the event to the senders own list if there is one
    if self_send:
        if isinstance(sender, User):
            sender.public_events.append(event)
            sender.save()
        else:
            sender.events.append(event)
            sender.save()

