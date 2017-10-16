# -*- coding:utf-8 -*-
import time

import multiprocessing

import os

from datetime import datetime

from concurrent import futures

from collections import namedtuple

try:
    from . import db
    from . import auto
except Exception as e:
    import db
    import auto

Result = namedtuple('Result', 'data')


with open('sample.csv', 'r') as fp:
    glass_id = fp.readlines()

glass_id = [i.rstrip() for i in glass_id]

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

MAX_WORKER = 200


def query_many_map(query, glass_id):
    workers = min(MAX_WORKER, len(glass_id))
    with futures.ThreadPoolExecutor(workers) as execute:
        res = execute.map(query, sorted(glass_id))
    return res


def query_many(query, glass_id):
    workers = min(MAX_WORKER, len(glass_id))
    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_gid = {executor.submit(query, g_id): g_id for g_id in sorted(glass_id)} 
        result = {}
        for future in futures.as_completed(future_to_gid):
            g_id = future_to_gid[future]
            try:
                data = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (g_id, exc))
            else:
                print('%r glass_id has %d rows' % (g_id, len(data)))
            result.setdefault(g_id, data)
    return result


def _query_edc_data_many(query, data):
    workers = min(MAX_WORKER, len(data))
    with futures.ThreadPoolExecutor(max_workers=workers) as executor:
        to_do = []
        future = executor.submit(query, data[0], data[1], data[2])
        to_do.append(future)
        #msg = 'Scheduled for {}: {}'
        #print(msg.format(g_id, future))

        result = []
        for future in futures.as_completed(to_do):
            res = future.result()
            msg = '{} result: {!r}'
            #print(msg.format(future, res))
            result.append(res)

    return result


def query_edc_data_many(query, datas):
    with futures.ProcessPoolExecutor() as executor:
        future_to_sid = {
            executor.submit(
            query, value[0], value[1], value[2]): value[1] for value in datas
        }
        result = {}
        for future in futures.as_completed(future_to_sid):
            s_id = future_to_sid[future]
            try:
                data = future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (s_id, exc))
            else:
                #print('%r step_id has %d rows' % (s_id, len(data)))
                pass
            result.setdefault(s_id, data)
    return result


def edc_data():
    """caculate on here
    """
    while True:
        term = yield
        if term is None:
            break
        result = auto.get_edc_data(term[0], term[1], term[2])
    return Result(result)


def grouper(result, key):
    while True:
        result[key] = yield from edc_data()


def chain(*iterables):
    for it in iterables:
        yield from it


def report(g_id, datas):
    path = os.path.join(BASE_DIR, g_id + '.csv')
    with open(path, 'w') as fp:
        for key, values in datas.items():
            for value in values:
                value = list(map(str, value))
                #value = list(value)
                for i in range(len(value)):
                    if isinstance(value[i], datetime):
                        value[i] = (value[i].strftime('%Y/%m/%d %H:%M:%S'))
                    if value[i] is None:
                        value[i] = "" 
                #value = list(map(str, value))
                fp.write(', '.join(value))
                fp.write('\n')


def main(query, query_many):    
    t0 = time.time()
    ret = query_many(query, glass_id)
    elapsed = time.time() - t0
    msg = '\n{} glass_id query in {:.2f}s'
    print(msg.format(len(ret), elapsed))

    t0 = time.time()
    results = {}
    for key, values in ret.items():
        t1 = time.time()
        #print('{}: \n{}'.format(key, list(chain(values))))
        msg = '\n{} each glass_id_dec_step_id query in {:.2f}s'

        # Query by thread 7s BUT process 2~3s
        result = query_edc_data_many(auto.get_edc_data, values)
        results.setdefault(key, result)
        print(msg.format(len(result), time.time() - t1))

        # yield from 
        #group = grouper(results, key)
        #next(group)
        #for value in values:
        #    print('send value: {}'.format(value))
        #    group.send(value)
        #group.send(None)
        #print(msg.format(len(results), time.time() - t1))

    elapsed_edc = time.time() - t0
    msg = '\n{} All glass_id_dec_step_id query in {:.2f}s'
    print(msg.format(len(results), elapsed_edc))
    
    for key, values in results.items():
        report(g_id=key, datas=values)


if __name__ == '__main__':
    main(auto.get_edc_glass_history, query_many)

