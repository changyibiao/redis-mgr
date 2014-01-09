#!/usr/bin/env python
#coding: utf-8

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
    def nbench(self):
        '''
        run benchmark against nutcracker
        '''
        for s in self.all_nutcracker:
            cmd = TT('bin/redis-benchmark --csv -h $host -p $port -r 100000 -t set,get -n 10000000 -c 100 ', s.args)
            BenchThread(random.choice(self._active_masters()), cmd).start()

    def mbench(self):
        '''
        run benchmark against redis master
        '''
        for s in self._active_masters():
            cmd = TT('bin/redis-benchmark --csv -h $host -p $port -r 100000 -t set,get -n 10000000 -c 100 ', s.args)
            BenchThread(s, cmd).start()

    def stopbench(self):
        '''
        you will need this for stop benchmark
        '''
        return self.sshcmd("pkill -f 'bin/redis-benchmark'")

class Monitor():
    def _live_nutcracker(self, what, format_func = lambda x:x):
        
        for i in xrange(1000*1000):
            if i%10 == 0:
                self.all_nutcracker
                header = common.to_blue(' '.join(['%5s' % s.args['port'] for s in self.all_nutcracker]))
                print header

            def get_v(s):
                info = s._info_dict()[self.args['cluster_name']]
                if what not in info:
                    return '-'
                return format_func(info[what])

            print ' '.join([ '%5s' % get_v(s) for s in self.all_nutcracker]) + '\t' + common.format_time(None, '%X')
            
            time.sleep(1)

    def _live_redis(self, what, format_func = lambda x:x):
        masters = self._active_masters()
        for i in xrange(1000*1000):
            if i%10 == 0:
                old_masters = masters
                masters = self._active_masters()

                old_masters_list = [str(m) for m in old_masters]
                masters_list = [str(m) for m in masters]

                if masters_list == old_masters_list: 
                    header = common.to_blue(' '.join(['%5s' % s.args['port'] for s in masters]))
                else:
                    header = common.to_red(' '.join(['%5s' % s.args['port'] for s in masters]))
                print header
            def get_v(s):
                info = s._info_dict()
                if what not in info:
                    return '-'
                return format_func(info[what])
            print ' '.join([ '%5s' % get_v(s) for s in masters]) + '\t' + common.format_time(None, '%X')
            
            time.sleep(1)

    def mlive_mem(self):
        '''
        monitor used_memory_human:1.53M of master
        '''
        def format(s):
            return re.sub('\.\d+', '', s) # 221.53M=>221M
        self._live_redis('used_memory_human', format)

    def mlive_qps(self):
        '''
        monitor instantaneous_ops_per_sec of master
        '''
        self._live_redis('instantaneous_ops_per_sec')

    def nlive_request(self):
        '''
        monitor nutcracker requests/s
        '''
        self._live_nutcracker('requests_INC')

    def nlive_forward_error(self):
        '''
        monitor nutcracker forward_error/s
        '''
        self._live_nutcracker('forward_error_INC')

    def nlive_inqueue(self):
        '''
        monitor nutcracker forward_error/s
        '''
        self._live_nutcracker('in_queue')

    def nlive_outqueue(self):
        '''
        monitor nutcracker forward_error/s
        '''
        self._live_nutcracker('out_queue')

    def _monitor(self):
        '''
        - redis 
            - connected_clients
            - mem
            - rdb_last_bgsave_time_sec:0
            - aof_last_rewrite_time_sec:0
            - latest_fork_usec
            - slow log
            - hitrate
            - master_link_status:down
        - nutcracker
            - all config of nutcracker is the same
            - forward_error
            - server_err
            - in_queue/out_queue

        save this to a file , in one line: 
        {
            'ts': xxx, 
            'timestr': xxx, 
            'infos': {
                '[redis:host:port]': {info}
                '[redis:host:port]': {info}
                '[nutcracker:host:port]': {info}
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

        DIR = os.path.join(PWD, '../data')
        STAT_LOG = os.path.join(DIR, 'statlog.%s' % common.format_time(now, '%Y%m%d%H'))
        common.system('mkdir -p %s' % DIR, None)

        fout = file(STAT_LOG, 'a+')
        print >> fout, my_json_encode(ret)
        fout.close()
        timeused = time.time() - now
        logging.notice("monitor @ ts: %s, timeused: %.2fs" % (common.format_time_to_min(now), timeused))

    def _check_warning(self, infos):
        def match(val, expr):
            if type(expr) == set:
                return val in expr
            _min, _max = expr
            return _min <= float(val) <= _max

        def check_redis(node, info):
            if not info or 'uptime_in_seconds' not in info:
                logging.warn('%s is down' % node)
            now = time.time()
            redis_spec = {
                    'connected_clients':          (0, 1000),
                    'used_memory_peak' :          (0, 5*(2**30)),
                    'rdb_last_bgsave_time_sec':   (0, 1),
                    'aof_last_rewrite_time_sec':  (0, 1),
                    'latest_fork_usec':           (0, 100*1000), #100ms
                    'master_link_status':         set(['up']),
                    'rdb_last_bgsave_status':     set(['ok']),
                    'rdb_last_save_time':         (now-25*60*60, now),
                    #- hit_rate
                    #- slow log
                }
            if 'REDIS_MONITOR_EXTRA' in dir(conf):
                redis_spec.update(conf.REDIS_MONITOR_EXTRA)

            for k, expr in redis_spec.items():
                if k in info and not match(info[k], expr):
                    logging.warn('%s.%s is:\t %s, not in %s' % (node, k, info[k], expr))


        def check_nutcracker(node, info):
            '''
            see NutCracker._info_dict() for fields
            '''
            if not info or 'uptime' not in info:
                logging.warn('%s is down' % node)

            nutcracker_cluster_spec = {
                    'client_connections':  (0, 10000),
                    "forward_error_INC":   (0, 1000),  # in every minute
                    "client_err_INC":      (0, 1000),  # in every minute
                    'in_queue':            (0, 1000),
                    'out_queue':           (0, 1000),
            }
            if 'NUTCRACKER_MONITOR_EXTRA' in dir(conf):
                nutcracker_cluster_spec.update(conf.NUTCRACKER_MONITOR_EXTRA)

            #got info of this cluster
            info = info[self.args['cluster_name']]
            for k, expr in nutcracker_cluster_spec.items():
                if k in info and not match(info[k], expr):
                    logging.warn('%s.%s is:\t %s, not in %s' % (node, k, info[k], expr))
        

        for node, info in infos.items():
            if strstr(node, 'redis'):
                check_redis(node, info)
            if strstr(node, 'nutcracker'):
                check_nutcracker(node, info)

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
        cron.add('0 3 * * *' , self.rdb, use_thread=True)                # every day
        cron.add('0 5 * * *' , self.aof_rewrite, use_thread=True)        # every day
        cron.run()

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
