#!/usr/bin/env python
#coding: utf-8

import os
import sys

PWD = os.path.dirname(os.path.realpath(__file__))
WORKDIR = os.path.join(PWD,  '../')
sys.path.append(os.path.join(WORKDIR, 'lib/'))
sys.path.append(os.path.join(WORKDIR, 'conf/'))

from utils import *
from monitor import Monitor, Benchmark

class Base:
    '''
    the sub class should implement: _alive, _pre_deploy, status, and init self.args
    '''
    def __init__(self, name, user, host_port, path):
        self.args = {
            'name'      : name,
            'user'      : user,
            'host'      : socket.gethostbyname(host_port.split(':')[0]),
            'port'      : int(host_port.split(':')[1]),
            'path'      : path,

            'localdir'  : '',     #files to deploy

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

        cmd = TT('rsync -ravP $localdir/ $user@$host:$path 1>/dev/null 2>/dev/null', self.args)
        self._run(cmd)

    def _gen_control_script(self):
        content = file('conf/control.sh').read()
        content = TT(content, self.args)

        control_filename = TT('${localdir}/${name}_control', self.args)

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
        #common.system_bg(remote_cmd, logging.debug)
        print self._run(remote_cmd)

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
        logging.debug('return : [%d] [%s] ' % (len(ret), common.shorten(ret)) )
        return ret


class RedisServer(Base):
    def __init__(self, user, host_port, path):
        Base.__init__(self, 'redis', user, host_port, path)

        self.args['startcmd'] = TT('bin/redis-server conf/redis.conf', self.args)
        self.args['runcmd']   = TT('redis-server \*:$port', self.args)

        self.args['conf']     = TT('$path/conf/redis.conf', self.args)
        self.args['pidfile']  = TT('$path/log/redis.pid', self.args)
        self.args['logfile']  = TT('$path/log/redis.log', self.args)
        self.args['dir']      = TT('$path/data', self.args)

        self.args['REDIS_CLI'] = conf.BINARYS['REDIS_CLI']

    def _info_dict(self):
        cmd = TT('$REDIS_CLI -h $host -p $port INFO', self.args)
        info = self._run(cmd)

        info = [line.split(':', 1) for line in info.split('\r\n') if not line.startswith('#')]
        info = [i for i in info if len(i)>1]
        return defaultdict(str, info) #this is a defaultdict, be Notice

    def _ping(self):
        cmd = TT('$REDIS_CLI -h $host -p $port PING', self.args)
        return self._run(cmd)

    def _alive(self):
        return strstr(self._ping(), 'PONG')

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
        cmd = TT('$REDIS_CLI -h $host -p $port $cmd', args)
        logging.info('%s %s' % (self, cmd))
        print self._run(cmd)


class Sentinel(RedisServer):
    def __init__(self, user, host_port, path, masters):
        RedisServer.__init__(self, user, host_port, path)

        self.args['startcmd'] = TT('bin/redis-sentinel conf/sentinel.conf', self.args)
        self.args['runcmd']   = TT('redis-sentinel \*:$port', self.args)

        self.args['conf']     = TT('$path/conf/sentinel.conf', self.args)
        self.args['pidfile']  = TT('$path/log/sentinel.pid', self.args)
        self.args['logfile']  = TT('$path/log/sentinel.log', self.args)

        self.args['name']     = 'sentinel'
        self.masters = masters

    def _gen_conf_section(self):
        template = '''\
sentinel monitor $server_name $host $port 2
sentinel down-after-milliseconds  $server_name 60000
sentinel failover-timeout $server_name 180000
sentinel parallel-syncs $server_name 1
        '''
        cfg = '\n'.join([TT(template, master.args) for master in self.masters])
        return cfg

    def _gen_conf(self):
        content = file('conf/sentinel.conf').read()
        content = TT(content, self.args)
        return content + self._gen_conf_section()

    def _pre_deploy(self):
        self.args['BINS'] = conf.BINARYS['REDIS_SENTINEL_BINS']
        self._run(TT('cp $BINS $localdir/bin/', self.args))

        fout = open(TT('$localdir/conf/sentinel.conf', self.args), 'w+')
        fout.write(self._gen_conf())
        fout.close()

    def get_masters(self):
        '''return currnet master list of (host:port, name)'''
        conn = redis.Redis(self.args['host'], self.args['port'])
        masters = conn.sentinel_masters()
        logging.debug('sentinel got masters: %s' % masters)
        return [('%s:%s' % (m['ip'], m['port']), m['name']) for m in masters.values()]

    def get_failover_event(self):
        self._sub = redis.Redis(self.args['host'], self.args['port']).pubsub()
        self._sub.subscribe('+switch-master')
        logging.info('subscribe +switch-master on %s' % self)
        iterator = self._sub.listen()
        if next(iterator)['channel'] != '+switch-master':
            raise Exception('error on subscribe')

        for msg in iterator:
            logging.info('got msg: %s' % msg)
            yield msg

class NutCracker(Base):
    def __init__(self, user, host_port, path, masters):
        Base.__init__(self, 'nutcracker', user, host_port, path)

        self.masters = masters

        self.args['conf']        = TT('$path/conf/nutcracker.conf', self.args)
        self.args['pidfile']     = TT('$path/log/nutcracker.pid', self.args)
        self.args['logfile']     = TT('$path/log/nutcracker.log', self.args)
        self.args['status_port'] = self.args['port'] + 1000

        self.args['startcmd']    = TT('bin/nutcracker -d -c $conf -o $logfile -p $pidfile -s $status_port', self.args)
        self.args['runcmd']      = self.args['startcmd']
        self._last_info = None

    def _alive(self):
        return self._info_dict()

    def _gen_conf_section(self):
        template = '    - $host:$port:1 $server_name'
        cfg = '\n'.join([TT(template, master.args) for master in self.masters])
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
        content = TT(content, self.args)
        return content + self._gen_conf_section()

    def _pre_deploy(self):
        self.args['BINS'] = conf.BINARYS['NUTCRACKER_BINS']
        self._run(TT('cp $BINS $localdir/bin/', self.args))

        fout = open(TT('$localdir/conf/nutcracker.conf', self.args), 'w+')
        fout.write(self._gen_conf())
        fout.close()

    def _info_dict(self):
        '''
                                                        | We will add fields in the info dict
        "uptime": 370,                                  |
        "timestamp": 1389231960,                        | timestamp_INC
        ....                                            |
        "cluster0": {                                   |
            "client_connections": 100,                  | 
            "client_eof": 500,                          |
            "forward_error": 0,                         | calc forward_error_INC
            "client_err": 0,                            | calc client_err_INC
            "fragments": 0,                             |  
            "server_ejects": 0,                         |  
                                                        | add global in_queue/out_queue/
                                                        | add global requests/responses/
                                                        | add global server_timedout/server_err
                                                        | calc requests_INC responses_INC
                                                        | calc server_timedout_INC server_err_INC
            "cluster0-20001": {       #a backend        | 
                "server_timedout": 0,                   | 
                "server_err": 0,                        | 
                "responses": 125406,                    | 
                "response_bytes": 828478,               | 
                "in_queue_bytes": 0,                    | 
                "server_connections": 1,                | 
                "request_bytes": 5189724,               | 
                "out_queue": 0,                         | 
                "server_eof": 0,                        | 
                "requests": 125406,                     | 
                "in_queue": 0,                          | 
                "out_queue_bytes": 0                    | 
            },                                          |
        '''
        info = self._raw_info_dict()
        #logging.debug(info)
        if not info:
            return None

        def calc_inc(cluster_name, info, last_info):
            TO_CALC_INC = ('forward_error', 'client_err', 'requests', 'responses', 'server_timedout', 'server_err')
            for item in TO_CALC_INC:
                info[item + '_INC'] = info[item] - last_info[item]

        def aggregation(cluster_name, info):
            TO_AGGREGATION = ('in_queue', 'out_queue', 'requests', 'responses', 'server_timedout', 'server_err')
            for item in TO_AGGREGATION:
                info[item] = 0
            for k, v, in info.items():
                if type(v) == dict: # a backend
                    for item in TO_AGGREGATION:
                        info[item] += v[item]

        if self._last_info:
            info['timestamp_INC'] = info['timestamp'] - self._last_info['timestamp']

        for k, v in info.items():
            if type(v) == dict:
                cluster_name = k
                cluster_info = v
                aggregation(cluster_name, cluster_info)
                if self._last_info:
                    calc_inc(cluster_name, cluster_info, self._last_info[cluster_name])

        self._last_info = info
        logging.debug(info)
        return info

    def _raw_info_dict(self):
        try:
            ret = telnetlib.Telnet(self.args['host'], self.args['status_port']).read_all()
            return common.json_decode(ret)
        except Exception, e:
            logging.debug('--- can not get _info_dict of nutcracker, [Exception: %s]' % (e, ))
            return None

    def status(self):
        ret = self._info_dict()
        if ret:
            uptime = ret['uptime']
            logging.info('%s uptime %s seconds' % (self, uptime))
        else:
            logging.error('%s is down' % self)

    def get_masters(self):
        '''return currnet master list of (host:port, name)'''
        cmd = TT('cat $conf', self.args)
        content = self._run(self._remote_cmd(cmd))
        logging.debug('current proxy config: %s' % content)

        def parse_line(line):
            _x, host_port_w, name = line.split()
            host, port, _w = host_port_w.split(':')
            return ('%s:%s' % (host, port), name)
        return [parse_line(line) for line in content.split('\n') if line.startswith('    -')]

    def reconfig(self, masters):
        self.masters = masters
        self.stop()
        self.deploy()
        self.start()
        logging.info('proxy %s:%s is updated' % (self.args['host'], self.args['port']))


class Cluster(object, Monitor, Benchmark):
    def __init__(self, args):
        self.args = args
        self.all_redis = [ RedisServer(self.args['user'], hp, path) for hp, path in self.args['redis'] ]
        pairs = zip(self.all_redis[::2], self.all_redis[1::2])

        for m, s in pairs: #slave use same name as master
            s.args['cluster_name'] = m.args['cluster_name'] = args['cluster_name']
            s.args['server_name'] = m.args['server_name'] = TT('$cluster_name-$port', m.args)

        masters = self.all_redis[::2]

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

    def _get_available_sentinel(self):
        for s in self.all_sentinel:
            if s._alive():
                return s
        logging.warn('No sentinel instance are available')
        return None

    def _active_masters(self):
        '''return the current master list on sentinel'''
        new_masters = self._get_available_sentinel().get_masters()
        new_masters = sorted(new_masters, key=lambda x: x[1])

        def make_master(host_port, name): # make master instance
            host = host_port.split(':')[0]
            port = int(host_port.split(':')[1])
            for r in self.all_redis:
                if r.args['host'] == host and r.args['port'] == port:
                    return r

        masters = [make_master(host_port, name) for host_port, name in new_masters]
        return masters

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
        if 'yes' == raw_input('do you want to stop yes/no: '):
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
        for s in self._active_masters():
            s.rediscmd(cmd)

    def rdb(self):
        '''
        do rdb in all redis instance, 
        '''
        self._rediscmd('BGSAVE', conf.RDB_SLEEP_TIME)

    def aof_rewrite(self):
        '''
        do aof_rewrite in all redis instance
        '''
        self._rediscmd('BGREWRITEAOF', conf.RDB_SLEEP_TIME)

    def randomkill(self):
        '''
        random kill master every mintue (for test failover)
        '''
        while True:
            r = random.choice(self._active_masters())
            logging.notice('will restart %s' % r)
            r.stop()
            time.sleep(80)
            r.start()
            time.sleep(60)

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

    def reconfigproxy(self):
        '''
        sync the masters list from sentinel to proxy
        '''
        logging.notice('begin reconfigproxy')
        old_masters = self.all_nutcracker[0].get_masters()
        new_masters = self._get_available_sentinel().get_masters()
        logging.info("old masters: %s" % sorted(old_masters, key=lambda x: x[1]))
        logging.info("new masters: %s" % sorted(new_masters, key=lambda x: x[1]))

        if set(new_masters) == set(old_masters):
            logging.notice('masters list of proxy are already newest, we will not do reconfigproxy')
            return
        logging.notice('we will do reconfigproxy')

        masters = self._active_masters()
        for m in self.all_nutcracker:
            m.reconfig(masters)
        logging.notice('reconfig all nutcracker Done!')

    def failover(self):
        '''
        catch failover event and update the proxy configuration
        '''
        while True:
            try:
                sentinel = self._get_available_sentinel()
                for event in sentinel.get_failover_event():
                    self.reconfigproxy()
            except Exception, e:
                logging.warn('we got exception: %s on failover task' % e)
                logging.exception(e)

    def migrage(self):
        '''
        migrage a redis instance to another machine
        '''
        pass

def discover_op():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m[0] for m in methods if not m[0].startswith('_')]
    return sets

def gen_op_help():
    methods = inspect.getmembers(Cluster, predicate=inspect.ismethod)
    sets = [m for m in methods if not m[0].startswith('_')]

    #sort the function list, based on the their position in the files
    lines = file('bin/deploy.py').readlines() + file('lib/monitor.py').readlines()
    def rank(x):
        name, func = x
        t = 'def ' + name 
        for i in range(len(lines)):
            if strstr(lines[i], t):
                return i
    sets = sorted(sets, key=rank)

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

    LOGPATH = os.path.join(WORKDIR, 'log/deploy.log')
    args = common.parse_args2(LOGPATH, parser)
    if args.cmd:
        eval('Cluster(conf.%s).%s(%s)' % (args.target, args.op, 'args.cmd') )
    else:
        eval('Cluster(conf.%s).%s()' % (args.target, args.op) )

if __name__ == "__main__":
    main()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
