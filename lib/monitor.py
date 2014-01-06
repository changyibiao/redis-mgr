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
from utils import *

PWD = os.path.dirname(os.path.realpath(__file__))

class BenchThread(threading.Thread):
    def __init__ (self, redis, cmd):
        threading.Thread.__init__(self)
        self.redis = redis
        self.cmd = cmd
    def run(self):
        self.redis._bench(self.cmd)

class Benchmark():
    def bench(self):
        '''
        run benchmark against proxy
        '''
        for s in self.all_nutcracker:
            cmd = TT('bin/redis-benchmark --csv -h $host -p $port -r 100000 -t set,get -n 100000 -c 100 ', s.args)
            BenchThread(random.choice(self._active_masters()), cmd).start()

    def mbench(self):
        '''
        run benchmark against redis master
        '''
        for s in self._active_masters():
            cmd = TT('bin/redis-benchmark --csv -h $host -p $port -r 100000 -t set,get -n 100000 -c 100 ', s.args)
            BenchThread(s, cmd).start()

    def stopbench(self):
        '''
        you will need this for stop benchmark
        '''
        return self.sshcmd("pkill -f 'bin/redis-benchmark'")

class Monitor():
    def _monitor_redis(self, what, format_func = lambda x:x):
        masters = self._active_masters()
        for i in xrange(1000*1000):
            if i%10 == 0:
                masters = self._active_masters()
                header = common.to_blue(' '.join(['%5s' % s.args['port'] for s in masters]))
                print header
            def get_v(s):
                info = s._info_dict()
                if what not in info:
                    return '-'
                return format_func(info[what])
            print ' '.join([ '%5s' % get_v(s) for s in masters]) + '\t' + common.format_time(None, '%X')
            
            time.sleep(1)

    def mm(self):
        '''
        monitor used_memory_human:1.53M
        '''
        def format(s):
            return re.sub('\.\d+', '', s) # 221.53M=>221M
        self._monitor_redis('used_memory_human', format)

    def mq(self):
        '''
        monitor instantaneous_ops_per_sec
        '''
        self._monitor_redis('instantaneous_ops_per_sec')

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

    def scheduler(self):
        '''
        start following threads:
            - failover 
            - cron of monitor
            - cron of rdb 
            = graph web server
        '''
        
        thread.start_new_thread(self.failover, ())

        cron = crontab.Cron()
        cron.add('* * * * *'   , self._monitor) # every minute
        cron.add('* * * * *' , self.rdb, use_thread=True)        # every day
        cron.run()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
