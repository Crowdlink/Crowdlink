import argparse
import datetime
import time
import os
import mongoengine
import logging

from featurelet.models import *

logFormatter = logging.Formatter("%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s")
rootLogger = logging.getLogger()

consoleHandler = logging.StreamHandler()
consoleHandler.setFormatter(logFormatter)
rootLogger.addHandler(consoleHandler)
rootLogger.setLevel(logging.INFO)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Initializes the database with lots of default data via the api')
    args = parser.parse_args()

    try:
        team = Team.objects.get(text=args.teamname)
    except Team.DoesNotExist:
        team = Team(text=args.teamname)
        team.save()
    else:
        logging.error("Team already exists")
