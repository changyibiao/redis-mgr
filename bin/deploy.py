#!/usr/bin/env python
#coding: utf-8
#file   : deploy.py
#author : ning
#date   : 2013-12-17 21:51:52

import os
import re
import sys
import time
import copy
import logging
import argparse
from string import Template as T
T.s = T.substitute
from pcl import common

PWD = os.path.dirname(os.path.realpath(__file__))
WORKDIR = os.path.join(PWD,  '../')
LOGPATH = os.path.join(WORKDIR, 'log/deploy.log')

sys.path.append(os.path.join(WORKDIR, 'lib/'))
sys.path.append(os.path.join(WORKDIR, 'conf/'))

import conf

class Base:
    def __init__(self):
        self.args = {}

    def alive(self):
        logging.error("alive: not implement")

    def copyfile(self):
        logging.error("scp: not implement")

    def start(self):
        self._remote_run(self.args['startcmd'])

    def stop(self):
        logging.error("stop : not implement")

    def kill(self):
        logging.error("kill: not implement")

    def ps(self):
        logging.error("ps: not implement")

    def log(self):
        logging.error("log: not implement")

    def clean(self):
        logging.error("clean: not implement")

    def _run(self, raw_cmd):
        return common.system(raw_cmd, logging.debug)

    def _init_dir(self):
        raw_cmd = T('mkdir -p $path/bin && mkdir -p $path/log && mkdir -p $path/data && mkdir -p $path/conf').s(self.args)
        self._remote_run(raw_cmd, chdir=False)

    def _remote_run(self, raw_cmd, chdir=True):
        if raw_cmd.find('"') >= 0:
            raise Exception('bad cmd: ' + raw_cmd)
        args = copy.deepcopy(self.args)
        args['cmd'] = raw_cmd
        if chdir:
            cmd = T('ssh -n -f $user@$host "cd $path && $cmd"').s(args)
        else:
            cmd = T('ssh -n -f $user@$host "$cmd"').s(args)
        return common.system(cmd, logging.debug)

class RedisServer(Base):
    def __init__(self, user, host_port, path):
        self.args = {
                'user':  user,
                'host':  host_port.split(':')[0],
                'port':  int(host_port.split(':')[1]),
                'path':  path,
                }
        self.args.update(conf.binarys)
        self.args['startcmd'] = T('bin/redis-server conf/redis-$port.conf').s(self.args)

    def gen_conf(self):
        content = file('conf/redis.conf').read()
        self.args['conf'] = T('$path/conf/redis-$port.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/redis-$port.pid').s(self.args)
        self.args['logfile'] = T('$path/log/redis-$port.log').s(self.args)
        self.args['dir']     = T('$path/data').s(self.args)
        content = T(content).s(self.args)

        self.args['local_config'] = T('conf/redis-$port.conf').s(self.args)
        fout = open(self.args['local_config'], 'w+')
        fout.write(content)
        fout.close()

        cmd = T('rsync -avP $local_config $user@$host:$path/conf/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

    def deploy(self):
        self._init_dir()
        cmd = T('rsync -avP $redis_server $user@$host:$path/bin/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)
        self.gen_conf()

    def start(self):
        self.deploy()
        Base.start(self)

    def alive(self):
        cmd = T('$redis_cli -h $host -p $port info').s(self.args)
        ret = self._run(cmd)
        if ret.find('redis_version:') > -1:
            return True
        return False


class Cluster():
    def __init__(self, args):
        self.args = args

    def deploy(self):
        for redis in self.args['redis']:
            r = RedisServer(self.args['user'], *redis)
            if not r.alive():
                r.start()



    def start(self):
        for redis in self.args['redis']:
            r = RedisServer(self.args['user'], *redis)
            if not r.alive():
                r.start()

    def stop(self):
        pass

    def ps(self):
        pass

    def log(self):
        pass

def discover_op():
    import inspect
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m[0] for m in methods if not m[0].startswith('_')]
    return sets

def discover_cluster():
    sets = [s for s in dir(conf) if s.startswith('cluster')]
    return sets

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('op', choices=discover_op(),
        help='start/stop/clean cluster')
    parser.add_argument('target', choices=discover_cluster(), help='cluster target ')
    args = common.parse_args2('log/deploy.log', parser)

    eval('Cluster(conf.%s).%s()' % (args.target, args.op) )

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
