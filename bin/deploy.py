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
import thread
import threading
import logging
import random
import inspect
import argparse

from collections import defaultdict
from argparse import RawTextHelpFormatter

from string import Template as T
T.s = T.substitute

from pcl import common

PWD = os.path.dirname(os.path.realpath(__file__))
WORKDIR = os.path.join(PWD,  '../')
LOGPATH = os.path.join(WORKDIR, 'log/deploy.log')

sys.path.append(os.path.join(WORKDIR, 'lib/'))
sys.path.append(os.path.join(WORKDIR, 'conf/'))


# import config in conf/xxx
if 'REDIS_DEPLOY_CONFIG' not in os.environ:
    logging.error('please export REDIS_DEPLOY_CONFIG=conf')
    #config_name = 'conf'
    exit(1)

config_name = os.environ['REDIS_DEPLOY_CONFIG']
conf = __import__(config_name, globals(), locals(), [], 0)        #import config_module

#utils
def strstr(s1, s2):
    return s1.find(s2) != -1

def lets_sleep(SLEEP_TIME = 0.1):
    time.sleep(SLEEP_TIME)

def TT(template, args): #todo: modify all
    return T(template).substitute(args)

class Base:
    '''
    the sub class should implement: _alive, _pre_deploy, status, and init self.args
    '''
    def __init__(self, name, user, host_port, path):
        self.args = {
            'name'      : name,
            'user'      : user,
            'host'      : host_port.split(':')[0],
            'port'      : int(host_port.split(':')[1]),
            'path'      : path,

            'localdir'  : '',     #files to deploy #TODO, rsync is right or not ??

            'startcmd'  : '',     #startcmd and runcmd will used to generate the control script
            'runcmd'    : '',
            'logfile'   : '',
        }

    def __str__(self):
        return TT('[$name:$host:$port]', self.args)

    def deploy(self):
        logging.info('deploy %s' % self)
        self.args['localdir'] = TT('tmp/$name-$host-$port', self.args)
        self._run(TT('mkdir -p $localdir/bin && mkdir -p $localdir/conf && mkdir -p $localdir/log && mkdir -p $localdir/data ', self.args))

        self._pre_deploy()
        self._gen_control_script()
        self._init_dir()

        cmd = T('rsync -ravP $localdir/ $user@$host:$path 1>/dev/null 2>/dev/null').s(self.args)
        self._run(cmd)

    def _gen_control_script(self):
        content = file('conf/control.sh').read()
        content = TT(content, self.args)

        control_filename = T('${localdir}/${name}_control').s(self.args)

        fout = open(control_filename, 'w+')
        fout.write(content)
        fout.close()
        os.chmod(control_filename, 0755)

    def start(self):
        if self._alive():
            logging.warn('%s already running' %(self) )
            return

        logging.debug('starting %s' % self)
        t1 = time.time()
        sleeptime = .1
        self._run(self._remote_start_cmd())

        while not self._alive():
            lets_sleep(sleeptime)
            if sleeptime < 5:
                sleeptime *= 2
            else:
                sleeptime = 5
                logging.warn('%s still not alive' % self)

        t2 = time.time()
        logging.info('%s start ok in %.2f seconds' %(self, t2-t1) )

    def stop(self):
        if not self._alive():
            logging.warn('%s already stop' %(self) )
            return

        self._run(self._remote_stop_cmd())
        t1 = time.time()
        while self._alive():
            lets_sleep()
        t2 = time.time()
        logging.info('%s stop ok in %.2f seconds' %(self, t2-t1) )

    def printcmd(self):
        print common.to_blue(self), self._remote_start_cmd()

    def status(self):
        logging.warn("status: not implement")

    def log(self):
        cmd = TT('tail $logfile', self.args)
        logging.info('log of %s' % self)
        print self._run(self._remote_cmd(cmd))

    def _bench(self, cmd):
        '''
        run a benchmark cmd on this remote machine
        '''
        remote_cmd = self._remote_cmd(cmd)
        logging.info(remote_cmd)
        common.system_bg(remote_cmd, logging.debug)
        #print self._run(remote_cmd)

    def _alive(self):
        logging.warn("_alive: not implement")

    def _init_dir(self):
        raw_cmd = TT('mkdir -p $path', self.args)
        self._run(self._remote_cmd(raw_cmd, chdir=False))

    def _remote_start_cmd(self):
        cmd = TT("./${name}_control start", self.args)
        return self._remote_cmd(cmd)

    def _remote_stop_cmd(self):
        cmd = TT("./${name}_control stop", self.args)
        return self._remote_cmd(cmd)

    def _remote_cmd(self, raw_cmd, chdir=True):
        if raw_cmd.find('"') >= 0:
            raise Exception('bad cmd: ' + raw_cmd)
        args = copy.deepcopy(self.args)
        args['cmd'] = raw_cmd
        if chdir:
            return TT('ssh -n -f $user@$host "cd $path && $cmd"', args)
        else:
            return TT('ssh -n -f $user@$host "$cmd"', args)

    def _run(self, raw_cmd):
        ret = common.system(raw_cmd, logging.debug)
        logging.debug('return : ' + common.shorten(ret))
        return ret


class RedisServer(Base):
    def __init__(self, user, host_port, path):
        Base.__init__(self, 'redis', user, host_port, path)

        self.args['startcmd'] = T('bin/redis-server conf/redis.conf').s(self.args)
        self.args['runcmd'] = T('redis-server \*:$port').s(self.args)

        self.args['conf'] = T('$path/conf/redis.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/redis.pid').s(self.args)
        self.args['logfile'] = T('$path/log/redis.log').s(self.args)
        self.args['dir']     = T('$path/data').s(self.args)

        self.args['REDIS_CLI'] = conf.BINARYS['REDIS_CLI']

    def _info_dict(self):
        cmd = T('$REDIS_CLI -h $host -p $port INFO').s(self.args)
        info = self._run(cmd)

        info = [line.split(':', 1) for line in info.split('\r\n') if not line.startswith('#')]
        info = [i for i in info if len(i)>1]
        return defaultdict(str, info) #this is a defaultdict, be Notice

    def _alive(self):
        return self._info_dict()['redis_version']

    def _gen_conf(self):
        content = file('conf/redis.conf').read()
        return TT(content, self.args)

    def _pre_deploy(self):
        self.args['BINS'] = conf.BINARYS['REDIS_SERVER_BINS']
        self._run(TT('cp $BINS $localdir/bin/', self.args))

        fout = open(TT('$localdir/conf/redis.conf', self.args), 'w+')
        fout.write(self._gen_conf())
        fout.close()

    def status(self):
        uptime = self._info_dict()['uptime_in_seconds']
        if uptime:
            logging.info('%s uptime %s seconds' % (self, uptime))
        else:
            logging.error('%s is down' % self)

    def isslaveof(self, master_host, master_port):
        info = self._info_dict()
        if info['master_host'] == master_host and int(info['master_port']) == master_port:
            logging.debug('already slave of %s:%s' % (master_host, master_port))
            return True

    def slaveof(self, master_host, master_port):
        cmd = 'SLAVEOF %s %s' % (master_host, master_port)
        return self.rediscmd(cmd)

    def rediscmd(self, cmd):
        args = copy.deepcopy(self.args)
        args['cmd'] = cmd
        cmd = T('$REDIS_CLI -h $host -p $port $cmd').s(args)
        logging.info('%s %s' % (self, cmd))
        print self._run(cmd)


class Sentinel(RedisServer):
    def __init__(self, user, host_port, path, masters):
        RedisServer.__init__(self, user, host_port, path)

        self.args['startcmd'] = T('bin/redis-sentinel conf/sentinel.conf').s(self.args)
        self.args['runcmd'] = T('redis-sentinel \*:$port').s(self.args)

        self.args['conf'] = T('$path/conf/sentinel.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/sentinel.pid').s(self.args)
        self.args['logfile'] = T('$path/log/sentinel.log').s(self.args)

        self.args['name'] = 'sentinel'
        self.masters = masters

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
        return content + self._gen_conf_section()

    def _pre_deploy(self):
        self.args['BINS'] = conf.BINARYS['REDIS_SENTINEL_BINS']
        self._run(TT('cp $BINS $localdir/bin/', self.args))

        fout = open(TT('$localdir/conf/sentinel.conf', self.args), 'w+')
        fout.write(self._gen_conf())
        fout.close()

class NutCracker(Base):
    def __init__(self, user, host_port, path, masters):
        Base.__init__(self, 'nutcracker', user, host_port, path)

        self.masters = masters

        self.args['conf'] = T('$path/conf/nutcracker.conf').s(self.args)
        self.args['pidfile'] = T('$path/log/nutcracker.pid').s(self.args)
        self.args['logfile'] = T('$path/log/nutcracker.log').s(self.args)
        self.args['status_port'] = self.args['port'] + 1000

        self.args['startcmd'] = T('bin/nutcracker -d -c $conf -o $logfile -p $pidfile -s $status_port').s(self.args)
        self.args['runcmd'] = self.args['startcmd']

    def _alive(self):
        return self._info_dict()

    def _gen_conf_section(self):
        template = '    - $host:$port:1 $server_name'
        cfg = '\n'.join([T(template).s(master.args) for master in self.masters])
        return cfg

    def _gen_conf(self):
        content = '''
$cluster_name:
  listen: 0.0.0.0:$port
  hash: fnv1a_64
  distribution: modula
  preconnect: true
  auto_eject_hosts: false
  redis: true
  backlog: 512
  timeout: 400
  client_connections: 0
  server_connections: 1
  server_retry_timeout: 2000
  server_failure_limit: 2
  servers:
'''
        content = T(content).s(self.args)
        return content + self._gen_conf_section()

    def _pre_deploy(self):
        self.args['BINS'] = conf.BINARYS['NUTCRACKER_BINS']
        self._run(TT('cp $BINS $localdir/bin/', self.args))

        fout = open(TT('$localdir/conf/nutcracker.conf', self.args), 'w+')
        fout.write(self._gen_conf())
        fout.close()

    def _info_dict(self):
        cmd = T('nc $host $status_port').s(self.args)
        ret = self._run(cmd)
        try:
            return common.json_decode(ret)
        except Exception, e:
            logging.debug('--- json decode error on : %s, [Exception: %s]' % (ret, e))
            return None

    def status(self):
        ret = self._info_dict()
        if ret:
            uptime = ret['uptime']
            logging.info('%s uptime %s seconds' % (self, uptime))
        else:
            logging.error('%s is down' % self)


class BenchThread(threading.Thread):
    def __init__ (self, redis, cmd):
        threading.Thread.__init__(self)
        self.redis = redis
        self.cmd = cmd
    def run(self):
        self.redis._bench(self.cmd)


class Cluster():
    def __init__(self, args):
        self.args = args
        self.all_redis = [ RedisServer(self.args['user'], hp, path) for hp, path in self.args['redis'] ]
        self.all_masters = masters = self.all_redis[::2]
        for m in masters:
            m.args['cluster_name'] = args['cluster_name']
            m.args['server_name'] = T('$cluster_name-$port').s(m.args)

        self.all_sentinel = [Sentinel(self.args['user'], hp, path, masters) for hp, path in self.args['sentinel'] ]
        self.all_nutcracker = [NutCracker(self.args['user'], hp, path, masters) for hp, path in self.args['nutcracker'] ]
        for m in self.all_nutcracker:
            m.args['cluster_name'] = args['cluster_name']

    def _doit(self, op):
        logging.notice('%s redis' % (op, ))
        for s in self.all_redis:
            eval('s.%s()' % op)

        logging.notice('%s sentinel' % (op, ))
        for s in self.all_sentinel:
            eval('s.%s()' % op)

        logging.notice('%s nutcracker' % (op, ))
        for s in self.all_nutcracker:
            eval('s.%s()' % op)

    def deploy(self):
        '''
        deploy the binarys and config file (redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('deploy')

    def start(self):
        '''
        start all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('start')

        logging.notice('setup master->slave')
        rs = self.all_redis
        pairs = [rs[i:i+2] for i in range(0, len(rs), 2)]
        for m, s in pairs:
            if s.isslaveof(m.args['host'], m.args['port']):
                logging.warn('%s->%s is ok!' % (m,s ))
            else:
                logging.info('setup %s->%s' % (m,s ))
                s.slaveof(m.args['host'], m.args['port'])

    def stop(self):
        '''
        stop all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('stop')

    def printcmd(self):
        '''
        print the start/stop cmd of instance
        '''
        self._doit('printcmd')

    def status(self):
        '''
        get status of all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('status')

    def log(self):
        '''
        show log of all instance(redis/sentinel/nutcracker) in this cluster
        '''
        self._doit('log')

    def _rediscmd(self, cmd, sleeptime=.1):
        for s in self.all_redis:
            time.sleep(sleeptime)
            s.rediscmd(cmd)

    def rediscmd(self, cmd):
        '''
        run redis command against all redis instance, like 'INFO, GET xxxx'
        '''
        self._rediscmd(cmd)

    def mastercmd(self, cmd):
        '''
        run redis command against all redis Master instance, like 'INFO, GET xxxx'
        '''
        for s in self.all_masters:
            s.rediscmd(cmd)

    def rdb(self):
        '''
        do rdb in all redis instance
        '''
        self._rediscmd('BGSAVE', conf.RDB_SLEEP_TIME)

    def aof_rewrite(self):
        '''
        do aof_rewrite in all redis instance
        '''
        self._rediscmd('BGREWRITEAOF', conf.RDB_SLEEP_TIME)


    def _monitor_redis(self, what, format_func = lambda x:x):
        header = common.to_blue(' '.join(['%5s' % s.args['port'] for s in self.all_masters]))
        for i in xrange(1000*1000):
            if i%10 == 0:
                print header
            def get_v(s):
                info = s._info_dict()
                if what not in info:
                    return '-'
                return format_func(info[what])
            print ' '.join([ '%5s' % get_v(s) for s in self.all_masters])
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

    def randomdown(self):
        '''
        random kill master every second (for test)
        '''
        pass

    def reconfig_proxy(self):
        pass


    def bench(self):
        '''
        run benchmark against proxy
        '''
        for s in self.all_nutcracker:
            cmd = T('bin/redis-benchmark --csv -h $host -p $port -r 10000000 -t set,get -n 1000000 -c 10 &').s(s.args)
            BenchThread(random.choice(self.all_masters), cmd).start()

    def mbench(self):
        '''
        run benchmark against redis master
        '''
        for s in self.all_masters:
            cmd = T('bin/redis-benchmark --csv -h $host -p $port -r 10000000 -t set,get -n 1000000 -c 10 &').s(s.args)
            BenchThread(s, cmd).start()

    def stopbench(self):
        '''
        you will need this for stop benchmark
        '''
        return self.sshcmd("pkill -f 'bin/redis-benchmark'")

    def sshcmd(self, cmd):
        '''
        ssh to target machine and run cmd
        '''
        hosts = [s.args['host'] for s in self.all_redis + self.all_sentinel + self.all_nutcracker]
        hosts = set(hosts)

        args = copy.deepcopy(self.args)
        args['cmd'] = cmd
        for h in hosts:
            args['host'] = h
            cmd = TT('ssh -n -f $user@$host "$cmd"', args)
            print common.system(cmd)

def discover_op():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m[0] for m in methods if not m[0].startswith('_')]
    return sets

def gen_op_help():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m for m in methods if not m[0].startswith('_')]

    def format_func(name, func):
        args = ' '.join(inspect.getargspec(func).args[1:])
        if args:
            desc = '%s %s' % (name, args)
        else:
            desc = name
        return '%-25s: %s' % (common.to_blue(desc), str(func.__doc__).strip())

    return '\n'.join([format_func(name, func) for name, func in sets])

def discover_cluster():
    sets = [s for s in dir(conf) if s.startswith('cluster')]
    return sets

def main():
    sys.argv.insert(1, '-v') # force -v
    parser = argparse.ArgumentParser(formatter_class=RawTextHelpFormatter)

    parser.add_argument('target', metavar='clustername', choices=discover_cluster(), help=' / '.join(discover_cluster()))
    parser.add_argument('op', metavar='op', choices=discover_op(),
        help=gen_op_help())
    parser.add_argument('cmd', nargs='?', help='the redis/ssh cmd like "INFO"')

    args = common.parse_args2('log/deploy.log', parser)
    if args.cmd:
        eval('Cluster(conf.%s).%s(%s)' % (args.target, args.op, 'args.cmd') )
    else:
        eval('Cluster(conf.%s).%s()' % (args.target, args.op) )

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
