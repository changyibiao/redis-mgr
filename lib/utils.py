import os
import re
import sys
import time
import copy
import thread
import threading
import logging
import inspect
import argparse
import redis
import random
import redis
import json

from collections import defaultdict
from argparse import RawTextHelpFormatter

from pcl import common
from pcl import crontab
from string import Template

def my_json_encode(j):
    return json.dumps(j, cls=common.MyEncoder)

def TT(template, args): #todo: modify all
    return Template(template).substitute(args)

def strstr(s1, s2):
    return s1.find(s2) != -1

def lets_sleep(SLEEP_TIME = 0.1):
    time.sleep(SLEEP_TIME)

def TT(template, args): #todo: modify all
    return Template(template).substitute(args)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
