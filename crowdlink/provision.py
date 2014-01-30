from crowdlink import db, root
from crowdlink.models import Email, User, Project, Task, Comment

from flask import current_app
from flask.ext.login import login_user

import yaml

def provision():
    """ Creates fixture data for the tests by making real connections with
    Stripe and setting up test projects, tasks, etc """
    # ensure we aren't sending any emails
    current_app.config['send_emails'] = False
    users = {}

    # make an admin user, and set him as the current user
    admin = User.create("admin", "testing", "admin@crowdlink.io")
    admin.admin = True  # make them an admin
    db.session.commit()
    assert Email.activate_email('admin@crowdlink.io', force=True)
    login_user(admin)

    # make a bunch of testing users
    # =========================================================================
    # fred isn't activated, no email address verified
    fred = User.create("fred", "testing", "fred@crowdlink.io")
    users['fred'] = fred
    db.session.commit()

    # regular users...
    for username in ['velma', 'scrappy', 'shaggy', 'scooby', 'daphne', 'crowdlink',
                     'barney', 'betty']:
        usr = User.create(username, "testing", username + "@crowdlink.io")
        db.session.commit()
        assert Email.activate_email(username + '@crowdlink.io', force=True)
        users[username] = usr

    # Create projects, tasks, comments, etc from a template file
    # =========================================================================
    pdata = yaml.load(open(root + '/assets/provision.yaml'))
    projects = {}
    for project in pdata['projects']:
        # create a sweet new project...
        proj = Project(
            owner=users[project['owner']],
            name=project['name'],
            website=project['website'],
            url_key=project['url_key'],
            desc=project['desc']).save()
        curr_proj = {'obj': proj}
        projects[proj.url_key] = curr_proj

        # subscribe some users if requested in config
        if 'subscribers' in project:
            for sub in project['subscribers']:
                proj.set_subscribed(True, user=users[sub])

        if 'maintainers' in project:
            for maintainer in project['maintainers']:
                proj.add_maintainer(username=users[maintainer].username)

        # Add out tasks to the database
        curr_proj['tasks'] = {}
        for task in project.get('tasks', []):
            # add some solutions to the task
            new_task = Task.create(
                user=users[task.get('creator', proj.owner.username)],
                title=task['title'],
                desc=task.get('desc'),
                project=proj).save()

            curr_task = {'obj': new_task}
            curr_proj['tasks'][task.get('key', new_task.url_key)] = curr_task

            # add comments to the task
            curr_task['comments'] = {}
            for comm_tmpl in task.get('comments', []):
                comm = Comment.create(
                    thing=new_task,
                    user=users[comm_tmpl.get('creator', new_task.creator.username)],
                    message=comm_tmpl.get('message')).save()
                curr_task['comments'][comm_tmpl.get('key', comm.id)] = (
                    {'obj': comm})
