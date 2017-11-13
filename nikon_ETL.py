import subprocess as sp
import os
import time
import logging
import uuid
import asyncio

import lazy_logger

from dbs import nikon

from contextlib import contextmanager
from collections import OrderedDict
from itertools import dropwhile, chain
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def log_time():
    """return log datetime
    rtype: str time
    """
    return str(time.strftime("%Y%m%d%H%M", time.localtime(time.time())))


def call_lazylog(f):
    def lazylog(*args, **kwargs):
        log_path = os.path.join(
            os.getcwd(), 'logs',
            log_time() + '-' + str(uuid.uuid1()) + '.log'
        )
        lazy_logger.log_to_console(logger)
        lazy_logger.log_to_rotated_file(logger=logger, file_name=log_path)
        logger.info('logger file: {0}'.format(log_path))
        kwargs['log_path'] = log_path
        return f(*args, **kwargs)

    return lazylog


def get_lastendtime(row):
    """get lastendtime from row, get the first return.
    :types: rows: list(dict())
    :rtype: datatime
    """
    row = row[0]  # get first row
    return row['last_end_time']


def ckflow(row):
    """check etl flow, if exist more than 1 row return True
    :types: rows: list(dict())
    :rtype: bool()
    """
    if len(row):
        return True
    return False


@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(newdir)
    try:
        yield
    finally:
        os.chdir(prevdir)


def run_command_under_r_root(cmd, catched=True):
    RPATH = os.path.join(os.path.abspath(__file__), 'R')
    with cd(newdir=RPATH):
        if catched:
            process = sp.run(cmd, stdout=sp.PIPE, stderr=sp.PIPE)
        else:
            process = sp.run(cmd)
        return process


def rscript(r, toolid, df):
    rprocess = OrderedDict()
    commands = OrderedDict([
        (toolid, [RScript, r, df]),
    ])
    for cmd_name, cmd in commands.items():
        rprocess[cmd_name] = run_command_under_r_root(cmd)
    return rprocess


def rscript_avm(r, toolid, starttime, endtime):
    rprocess = OrderedDict()
    commands = OrderedDict([
        (toolid, [RScript, r, starttime, endtime]),
    ])
    for cmd_name, cmd in commands.items():
        rprocess[cmd_name] = run_command_under_r_root(cmd)
    return rprocess


class ETL:
    """docstring for ETL
    """

    def __init__(self, toolid):
        super(ETL, self).__init__()
        self.fdc_psql = nikon.FdcPGSQL()
        self.fdc_oracle = nikon.FdcOracle()
        self.eda_oracle = nikon.EdaOracle()
        self.toolid = toolid

    def column_state(self, edc, schema):
        add_cols = list(set(edc) - set(schema))
        del_cols = list(set(schema) - set(edc))

        if add_cols and del_cols:
            return {'ret': False, 'add': add_cols, 'del': del_cols}
        elif add_cols:
            return {'ret': False, 'add': add_cols, 'del': del_cols}
        elif del_cols:
            return {'ret': False, 'add': add_cols, 'del': del_cols}
        else:
            return {'ret': True, 'add': add_cols, 'del': del_cols}

    @asyncio.coroutine
    def insert(self, toolid):
        while True:
            row = yield
            if row is None:
                break
            self.fdc_psql.save_edcdata(
                toolid=toolid,
                edcdata=row
            )

    @asyncio.coroutine
    def grouper(self, toolid):
        while True:
            yield from self.insert(toolid=toolid)

    @logger.patch
    def etl(self, apname, *args, **kwargs):
        """start etl edc import
        """
        print('Nikon ETL Process Start...')
        row = self.get_aplastendtime(apname=apname)
        etlflow = ckflow(row=row)

        if etlflow:
            ora_lastendtime = self.fdc_oracle.get_lastendtime()[0]
            psql_lastendtime = get_lastendtime(row=row)
            print('Lastendtime, Oracle:{}, PSQL:{}'.format(ora_lastendtime, psql_lastendtime))

        # ora lastendtime new than psql lastendtime.
        if ora_lastendtime > psql_lastendtime:
            try:
                self.fdc_psql.delete_tlcd(
                    psql_lastendtime=psql_lastendtime,
                    ora_lastendtime=ora_lastendtime
                )
            except Exception as e:
                raise e

            endtime_data = self.fdc_oracle.get_endtimedata(
                psql_lastendtime=psql_lastendtime,
                ora_lastendtime=ora_lastendtime
            )

            if len(endtime_data):
                # Add login time in all row.
                insert_data = []
                logintime = datetime.now()
                for d in endtime_data:
                    d.setdefault('LOGIN_TIME', logintime)
                    insert_data.append(tuple(d.values()))

                try:
                    pass
                    # self.fdc_psql.save_endtime(
                    #    endtime_data=insert_data
                    # )
                except Exception as e:
                    raise e

            # Import data in table
            toolids = list(set(data['TOOLID'] for data in endtime_data))
            for toolid in sorted(toolids):
                toolid = toolid.lower()
                # check table exists or not.
                pgclass = self.fdc_psql.get_pgclass(toolid=toolid)
                print('Toolid: {}, pg_class count: {}'.format(toolid, pgclass))

                if pgclass[0]['count']:

                    print('Reday to Import EDC toolid: {}'.format(toolid))
                    try:
                        print('Delete rows duplicate...')
                        self.fdc_psql.delete_toolid(
                            toolid=toolid,
                            psql_lastendtime=psql_lastendtime,
                            ora_lastendtime=ora_lastendtime
                        )
                    except Exception as e:
                        raise e

                    schemacolnames = self.fdc_psql.get_schemacolnames(
                        toolid=toolid
                    )
                    schemacolnames = [column[0].upper() for column in schemacolnames]

                    edc_data = self.fdc_oracle.get_edcdata(
                        toolid=toolid,
                        psql_lastendtime=psql_lastendtime,
                        ora_lastendtime=ora_lastendtime
                    )
                    edc_columns = list(edc_data[0].keys())

                    column_state = self.column_state(edc=edc_columns, schema=schemacolnames)
                    if column_state.get('ret', False):
                        print('Column status: ret={} add={} del={}'.format(
                            column_state.get('ret'), column_state.get('add'),
                            column_state.get('del')
                        ))
                        datas = [tuple(d.values()) for d in edc_data]

                    try:
                        # should using high performance.
                        print('Insert Count: {}'.format(len(edc_data)))
                        for idx, values in enumerate(datas):
                            group = self.grouper(toolid=toolid)
                            next(group)
                            group.send(values)
                        group.send(None)
                        # self.fdc_psql.save_edcdata(
                        #    toolid=toolid,
                        #    edcdata=data
                        # )
                    except Exception as e:
                        raise e

                # Update last endtime.
                try:
                    pass
                    # self.fdc_psql.update_lastendtime(
                    #    toolid=self.toolid,
                    #    apname=apname,
                    #    last_endtime=ora_lastendtime
                    # )
                except Exception as e:
                    raise e

    @logger.patch
    def rot(self, apname, *args, **kwargs):
        """start etl rot, clean data in psql
        """
        print("Nikon ETL ROT Transform Process Start...")
        row = self.get_aplastendtime(apname=apname)
        edcrow = self.get_aplastendtime(apname='EDC_Import')
        rotflow = ckflow(row=row)

        if rotflow:
            psql_lastendtime_rot = get_lastendtime(row=row)
            psql_lastendtime_edc = get_lastendtime(row=edcrow)
            update_starttime = datetime.strptime('2017-07-13 20:00:27', '%Y-%m-%d %H:%M:%S')
            #update_starttime = psql_lastendtime_rot
            update_endtime = psql_lastendtime_edc
            print('EDC Import Lastendtime: {}, '
                  'ROT Transform Lastendtime: {}'.format(
                psql_lastendtime_edc, psql_lastendtime_rot
            ))

        while True:
            # stop if update_starttime same.
            if update_starttime == psql_lastendtime_edc:
                print('Done')
                break

            if (update_starttime + timedelta(seconds=86400)) < psql_lastendtime_edc:
                update_endtime = update_starttime + timedelta(seconds=86400)
            #else:
            #    update_endtime = psql_lastendtime_edc

            # Get candidates of toolist
            toolist = self.fdc_psql.get_toolid(
                update_starttime=update_starttime,
                update_endtime=update_endtime
            )
            toolids = list(chain.from_iterable(toolist))
            print(toolids)

            for toolid in sorted([id.lower() for id in toolids]):
                print('Candidate {} time period '\
                      'start: {}, end: {}.'.format(
                    toolid, update_starttime, update_endtime
                ))
                nikonrot_data = self.fdc_psql.get_nikonrot(
                    toolid=toolid,
                    update_starttime=update_starttime,
                    update_endtime=update_endtime
                )
                print('Candidate count: {}'.format(
                    len(nikonrot_data)
                ))
            break

        '''
                if len(nikonrot_data):
                    # run rscript
                    ret = rscript(
                        r='TLCD_Nikon_ROT.R',
                        toolid=toolid,
                        df=nikonrot_data
                    )
                    print('ROT End...')

                measrot_data = self.eda_oracle.get_measrotdata(
                    update_starttime=update_starttime,
                    update_endtime=update_endtime
                )
                print('ROT Transform start Meas Candidate count {}'.format(
                    len(measrot_data)
                ))

                if len(measrot_data):
                    # run rscript
                    ret = rscript(
                        r='TLCD_NIKON_MEA_ROT.R',
                        toolid=toolid,
                        df=measrot_data
                    )
                    print('ROT Meas End...')

                # TODO which sql command call to data integration??
                print('Refresh MTV (tlcd_nikon_mea_process_summary_mv) in the end..."')
                try:
                    self.fdc_psql.refresh_nikonmea()
                except Exception as e:
                    raise e

                # Update lastendtime for ROT_Transform
                try:
                    self.fdc_psql.update_lastendtime(
                        toolid=toolid,
                        apname=apname,
                        last_endtime=update_endtime
                    )
                    update_starttime = update_endtime
                except Exception as e:
                    raise e
        '''
    @logger.patch
    def avm(self, apname, *args, **kwargs):
        """start etl avm
        """
        row_rot = self.get_aplastendtime(apname='ROT_Transform')
        row_avm = self.get_aplastendtime(apname=apname)

        lastendtime_rot = get_lastendtime(row=row_rot)
        lastendtime_avm = get_lastendtime(row=row_avm)

        if lastendtime_rot > lastendtime_avm:
            starttime = lastendtime_avm
            # endtime = lastendtime_rot

        while True:
            if starttime >= lastendtime_rot:
                break

            starttime += timedelta(seconds=86400)
            if starttime < lastendtime_rot:
                endtime = starttime
            else:
                endtime = lastendtime_rot

            # run rscript_avm
            ret = rscript_avm(
                r='TLCD_Nikon_VM_Fcn',
                starttime=starttime,
                endtime=endtime
            )

            # ????
            if ret:
                try:
                    # Update lastendtime table
                    self.fdc_psql.update_lastendtime(
                        toolid=self.toolid,
                        apname=apname,
                        last_endtime=endtime
                    )
                except Exception as e:
                    raise e

    def get_aplastendtime(self, apname, *args, **kwargs):
        row = self.fdc_psql.get_lastendtime(
            toolid=self.toolid,
            apname=apname
        )
        return row

    @logger.patch
    def status(self):
        """
        """
        pass

    def __str__(self):
        """
        """
        pass


@call_lazylog
def etlmain(*args, **kwargs):
    etl = ETL(toolid='NIKON')
    # etl.etl(apname='EDC_Import')
    etl.rot(apname='ROT_Transform')
    # etl.avm(apname='AVM_Process')


if __name__ == '__main__':
    etlmain()