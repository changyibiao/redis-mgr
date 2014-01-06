#!/usr/bin/env python
#coding: utf-8
#file   : monitor.py
#author : ning
#date   : 2014-01-06 15:24:48

import urllib, urllib2
import os, sys
import re, time
import logging
import json
from pcl import common

PWD = os.path.dirname(os.path.realpath(__file__))

def my_json_encode(j):
    return json.dumps(j, cls=common.MyEncoder)

class Monitor():
    def _monitor(self):
        '''
        - redis 
            - connected_clients
            - rdb_last_bgsave_time_sec:0
            - aof_last_rewrite_time_sec:0
            - latest_fork_usec
            - slow log
            - hitrate
            - master_link_status:down
        - proxy
            - all config of proxy is the same
            - forward_error
            - server_err
            - in_queue/out_queue

        save this to a file , in one line: 
        {
            'ts': xxx, 
            'timestr': xxx, 
            'infos': {
                'redis:host:port': {info}
                'redis:host:port': {info}
                'nutcracker:host:port': {info}
            },
        }
        '''
        now = time.time()

        infos = {}
        for r in self.all_redis + self.all_sentinel + self.all_nutcracker:
            infos[str(r)] = r._info_dict()
        self._check_warning(infos)

        ret = {
            'ts': now, 
            'timestr': common.format_time_to_min(now), 
            'infos': infos,
        }

        STAT_LOG = os.path.join(PWD, '../data/statlog.' + common.format_time_to_hour())
        fout = file(STAT_LOG, 'a+')
        print >> fout, my_json_encode(ret)
        fout.close()
        timeused = time.time() - now
        logging.notice("ts: %s, timeused: %.2fs" % (common.format_time_to_min(now), timeused))

    def _check_warning(self, infos):
        for i in infos:
            pass

    def monitor(self):
        '''
        a long time running monitor task, write WARN log on bad things happend
        '''
        while True:
            self._monitor()
            time.sleep(60)

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
