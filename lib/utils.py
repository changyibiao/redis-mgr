import os
import re
import sys
import time
import copy
import thread
import socket
import threading
import logging
import inspect
import argparse
import telnetlib
import redis
import random
import redis
import json

from collections import defaultdict
from argparse import RawTextHelpFormatter

from pcl import common
from pcl import crontab
from string import Template

# we have to do this here, so that lib/monitor.py can use conf.xxx
# import config in conf/REDIS_DEPLOY_CONFIG.py
if 'REDIS_DEPLOY_CONFIG' not in os.environ:
    logging.error('please export REDIS_DEPLOY_CONFIG=conf')
    exit(1)
config_name = os.environ['REDIS_DEPLOY_CONFIG']
conf = __import__(config_name, globals(), locals(), [], 0)        #import config_module

common.system('mkdir -p data tmp', None)

def my_json_encode(j):
    return json.dumps(j, cls=common.MyEncoder)

def strstr(s1, s2):
    return s1.find(s2) != -1

def lets_sleep(SLEEP_TIME = 0.1):
    time.sleep(SLEEP_TIME)

def TT(template, args): #todo: modify all
    return Template(template).substitute(args)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
