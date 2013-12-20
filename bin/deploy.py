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
    '''
    子类需要实现 _alive, deploy, status, 并初始化args包含如下变量
    '''
    def __init__(self):
        self.args = {
            'startcmd' :'',
            'pidfile'  :'',
            'logfile'  :'',
        }

    def deploy(self):
        logging.error("deploy: not implement")

    def start(self):
        self._remote_run(self.args['startcmd'])
        if not self._alive():
            logging.error('start fail')

    def stop(self):
        cmd = T('cat $pidfile | xargs kill').s(self.args)
        self._remote_run(cmd)

    def kill(self):
        cmd = T('cat $pidfile | xargs kill -9').s(self.args)
        self._remote_run(cmd)

    def status(self):
        logging.error("status: not implement")

    def log(self):
        cmd = T('tail $logfile').s(self.args)
        print self._remote_run(cmd)

    def _alive(self):
        logging.error("_alive: not implement")

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

        self.args['conf'] = T('$path/conf/redis-$port.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/redis-$port.pid').s(self.args)
        self.args['logfile'] = T('$path/log/redis-$port.log').s(self.args)
        self.args['dir']     = T('$path/data').s(self.args)


    def __str__(self):
        return T('[RedisServer:$host:$port]').s(self.args)

    def _info(self):
        cmd = T('$redis_cli -h $host -p $port INFO').s(self.args)
        return self._run(cmd)

    def _info_dict(self):
        info = self._info()
        info = [line.split(':') for line in info.split('\r\n')]
        info = [i for i in info if len(i)>1]
        return dict(info)

    def _alive(self):
        if self._info().find('redis_version:') > -1:
            return True
        return False

    def _gen_conf(self):
        content = file('conf/redis.conf').read()
        content = T(content).s(self.args)

        self.args['local_config'] = T('tmp/redis-$port.conf').s(self.args)
        fout = open(self.args['local_config'], 'w+')
        fout.write(content)
        fout.close()

        cmd = T('rsync -avP $local_config $user@$host:$path/conf/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

    def deploy(self):
        self._init_dir()

        cmd = T('rsync -avP $redis_server $user@$host:$path/bin/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

        self._gen_conf()

    def status(self):
        print self._info()

    def isslaveof(self, master_host, master_port):
        info = self._info_dict()
        if 'master_host' in info and info['master_host'] == master_host and int(info['master_port']) == master_port:
            logging.debug('already slave of %s:%s' % (master_host, master_port))
            return True

    def slaveof(self, master_host, master_port):
        cmd = 'SLAVEOF %s %s' % (master_host, master_port)
        return self.rediscmd(cmd)

    def rediscmd(self, cmd):
        args = copy.deepcopy(self.args)
        args['cmd'] = cmd
        cmd = T('$redis_cli -h $host -p $port $cmd').s(args)
        return self._run(cmd)

class Sentinel(RedisServer):
    def __init__(self, user, host_port, path, masters):
        self.masters = masters
        self.args = {
                'user':  user,
                'host':  host_port.split(':')[0],
                'port':  int(host_port.split(':')[1]),
                'path':  path,
                }
        self.args.update(conf.binarys)
        self.args['startcmd'] = T('bin/redis-sentinel conf/sentinel-$port.conf').s(self.args)

        self.args['conf'] = T('$path/conf/sentinel-$port.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/sentinel-$port.pid').s(self.args)
        self.args['logfile'] = T('$path/log/sentinel-$port.log').s(self.args)

    def __str__(self):
        return T('[Sentinel:$host:$port]').s(self.args)

    def _gen_conf_section(self):
        template = '''\
sentinel monitor $server_name $host $port 2
sentinel down-after-milliseconds  $server_name 60000
sentinel failover-timeout $server_name 180000
#sentinel can-failover $server_name yes TODO: the new version has no this cfg
sentinel parallel-syncs $server_name 1
        '''
        cfg = '\n'.join([T(template).s(master.args) for master in self.masters])
        return cfg

    def _gen_conf(self):
        content = file('conf/sentinel.conf').read()
        content = T(content).s(self.args)

        self.args['local_config'] = T('tmp/sentinel-$port.conf').s(self.args)
        fout = open(self.args['local_config'], 'w+')
        fout.write(content)
        fout.write(self._gen_conf_section())
        fout.close()

        cmd = T('rsync -avP $local_config $user@$host:$path/conf/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

    def deploy(self):
        self._init_dir()

        cmd = T('rsync -avP $redis_sentinel $user@$host:$path/bin/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

        self._gen_conf()

class NutCracker(Base):
    def __init__(self, user, host_port, path, masters):
        self.masters = masters
        self.args = {
                'user':  user,
                'host':  host_port.split(':')[0],
                'port':  int(host_port.split(':')[1]),
                'path':  path,
                }
        self.args.update(conf.binarys)

        self.args['conf'] = T('$path/conf/nutcracker-$port.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/nutcracker-$port.pid').s(self.args)
        self.args['logfile'] = T('$path/log/nutcracker-$port.log').s(self.args)
        self.args['status_port'] = self.args['port'] + 1000

        self.args['startcmd'] = T('bin/nutcracker -d -c $conf -o $logfile -p $pidfile -s $status_port').s(self.args)

    def __str__(self):
        return T('[NutCracker:$host:$port]').s(self.args)

    def _alive(self):
        cmd = T('curl $host:$status_port').s(self.args)
        ret = self._run(cmd)
        if ret.find('service') > -1:
            return True
        return False

    def _gen_conf_section(self):
        template = '    - $host:$port:1 $server_name'
        cfg = '\n'.join([T(template).s(master.args) for master in self.masters])
        return cfg

    def _gen_conf(self):
        content = '''
$cluster_name:
  listen: $host:$port
  hash: fnv1a_64
  distribution: modula
  preconnect: true
  auto_eject_hosts: false
  redis: true
  backlog: 512
  client_connections: 0
  server_connections: 1
  server_retry_timeout: 2000
  server_failure_limit: 2
  servers:
'''
        content = T(content).s(self.args)

        self.args['local_config'] = T('tmp/nutcracker-$port.conf').s(self.args)
        fout = open(self.args['local_config'], 'w+')
        fout.write(content)
        fout.write(self._gen_conf_section())
        fout.close()

        cmd = T('rsync -avP $local_config $user@$host:$path/conf/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

    def deploy(self):
        self._init_dir()

        cmd = T('rsync -avP $nutcracker $user@$host:$path/bin/ 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

        self._gen_conf()

    def status(self):
        cmd = T('curl $host:$status_port 2>/dev/null').s(self.args)
        ret = self._run(cmd)
        if ret:
            print common.json_decode(ret)
        else:
            logging.error('%s is down' % self)

class Cluster():
    def __init__(self, args):
        self.args = args
        self.all_redis = [ RedisServer(self.args['user'], hp, path) for hp, path in self.args['redis'] ]
        masters = self.all_redis[::2]
        for m in masters:
            m.args['cluster_name'] = args['cluster_name']
            m.args['server_name'] = T('$cluster_name-$port').s(m.args)

        self.all_sentinel = [Sentinel(self.args['user'], hp, path, masters) for hp, path in self.args['sentinel'] ]
        self.all_nutcracker = [NutCracker(self.args['user'], hp, path, masters) for hp, path in self.args['nutcracker'] ]
        for m in self.all_nutcracker:
            m.args['cluster_name'] = args['cluster_name']

    def _doit(self, op, skip_if_alive):
        logging.notice('%s redis' % (op, ))
        for s in self.all_redis:
            if skip_if_alive and s._alive():
                logging.info('%s is alive' % s)
            else:
                logging.info('%s %s' % (op, s))
                eval('s.%s()' % op)

        logging.notice('%s sentinel' % (op, ))
        for s in self.all_sentinel:
            if skip_if_alive and s._alive():
                logging.info('%s is alive' % s)
            else:
                logging.info('%s %s' % (op, s))
                eval('s.%s()' % op)

        logging.notice('%s nutcracker' % (op, ))
        for s in self.all_nutcracker:
            if skip_if_alive and s._alive():
                logging.info('%s is alive' % s)
            else:
                logging.info('%s %s' % (op, s))
                eval('s.%s()' % op)

    def deploy(self):
        self._doit('deploy', True)

    def start(self):
        self._doit('start', True)

        logging.notice('setup master->slave')
        rs = self.all_redis
        pairs = [rs[i:i+2] for i in range(0, len(rs), 2)]
        for m, s in pairs:
            if s.isslaveof(m.args['host'], m.args['port']):
                logging.info('%s->%s is ok!' % (m,s ))
            else:
                logging.info('setup %s->%s' % (m,s ))
                s.slaveof(m.args['host'], m.args['port'])

    def stop(self):
        self._doit('stop', False)

    def status(self):
        self._doit('status', False)

    def log(self):
        self._doit('log', False)

def discover_op():
    import inspect
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m[0] for m in methods if not m[0].startswith('_')]
    return sets

def discover_cluster():
    sets = [s for s in dir(conf) if s.startswith('cluster')]
    return sets

def main():
    sys.argv.insert(1, '-v') # auto -v
    parser = argparse.ArgumentParser()
    parser.add_argument('op', choices=discover_op(),
        help='start/stop/clean cluster')
    parser.add_argument('target', choices=discover_cluster(), help='cluster target ')
    args = common.parse_args2('log/deploy.log', parser)

    eval('Cluster(conf.%s).%s()' % (args.target, args.op) )

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
