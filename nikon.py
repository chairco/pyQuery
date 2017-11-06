import time

import db


class FdcPgSQL:
    """ETL PostgreSQL DB
    """

    def get_lastendtime(self, equipment):
        """get apname last insert time
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT apname, last_end_time, virtual_recipe
            FROM "lastendtime"
            WHERE TOOLID = %(equipment)s
            AND enabled = "TRUE"
            """,
            {'equipment: self.equipment.upper()'},
        )
        rows = cursor.fetchall()
        return rows

    def get_pgclass(self, toolid, rownum=1):
        """get pglass rownum data
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT %(rownum)s
            FROM "pg_class"
            WHERE 1=1
            AND relname = %(toolid_rawdata)s
            """,
            {
                'rownum': rownum,
                'toolid_rawdata': '{}_rawdata'.fomart(toolid)
            }
        )
        rows = cursor.fetchall()
        return rows

    def get_schemacolnames(self, toolid):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT "column_name"
            FROM "information_schemd.columns"
            WHERE 1=1
            AND table_name = %(toolid_rawdata)s
            """,
            {
                toolid_rawdata: '{}_rawdata'.fomart(toolid)
            }
        )
        rows = cursor.fetchall()
        return rows

    def delete_tlcd(self, endtime, num=01):
        """default num = 01
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            DELETE 
            FROM "index_glassout"  
            WHERE toolid 
            LIKE %(tlcd)s
            AND endtime > %(endtime)s 
            AND endtime <= %(endtime)s
            """,
            {
                'endtime': endtime,
                'tlcd': 'TLCD__{}'.format(num)
            }
        )

    def delete_toolid(self, toolid, psql_lastendtime, ora_lastendtime):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            DELETE
            FROM %(toolid_rawdata)s
            WHERE tstamp > to_timestamp('%(psql_lastendtime)s', 'YYYY-MM-DD HH24:MI:SS.FF3')
            AND tstamp <= to_timestamp('%(ora_lastendtime)s', 'YYYY-MM-DD HH24:MI:SS.FF3')
            """,
            {
                "toolid_rawdata": "{}_rawdata".format(toolid),
                "psql_lastendtime": psql_lastendtime,
                "ora_lastendtime": ora_lastendtime
            }
        )

    def save_endtime(self, endtimes):
        """Insert many rows at a times
        """
        cursor = db.get_cursor()
        cursor.executemany(
            """
            INSERT INTO "index_glassout"
            VALUES %(endtimes)s
            """,
            {'endtimes': endtimes}
        )

    def save_edcdata(self, toolid, edcdata):
        """
        """
        cursor = db.get_cursor()
        cursor.executemany(
            """
            INSERT INTO %(toolid_rawdata)s
            VALUES %(edcdata)s
            """,
            {
                "toolid_rawdata": "{}_rawdata".format(toolid),
                "edcdata": edcdata
            }
        )

    def update_aplastendtime(self, toolid, apname, last_endtime):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            UPDATE lastendtime
            SET last_endtime = :last_endtime, update_time = now()
            WHERE apname = :apname
            AND toolid = :toolid
            """,
            {
                "ap_lastendtimetblname": "lastendtime",
                "last_endtime": last_endtime,
                "apname": apname,
                "toolid": toolid
            }
        )


class FdcOracle:
    """InnoLux Oracle DB
    """

    def get_lastendtime(self):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT to_date(to_char(max(endtime),'yyyy-mm-dd hh24:mi:ss'),'yyyy-mm-dd hh24:mi:ss') as ora_last_end_time 
            FROM fdc.index_glassout
            WHERE toolid 
            LIKE 'TLCD__01'
            """
        )
        rows = cursor.fetchall()
        return rows

    def get_endtimedata(self, psql_lastendtime, ora_lastendtime):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT *
            FROM fdc.index_glassout
            WHERE toolid LIKE 'TLCD__01'
            AND endtime > to_timestamp(':psql_lastendtime', 'YYYY-MM-DD HH24:MI:SS.FF3')
            AND endtime <= to_timestamp(':ora_lastendtime', 'YYYY-MM-DD HH24:MI:SS.FF3')
            """,
            {
                'ora_proc_endtime_tablename': 'fdc.index_glassout',
                'psql_lastendtime': psql_lastendtime,
                'ora_lastendtime': ora_lastendtime
            }
        )
        rows = cursor.fetchall()
        return rows

    def get_edcdata(self, colname, toolid, psql_lastendtime, ora_lastendtime):
        """
        """
        cursor = db.get_cursor()
        cursor.execute(
            """
            SELECT :colname
            FROM :fdc_rawdata
            WHERE tstamp > to_timestamp(' :psql_lastendtime', 'YYYY-MM-DD HH24:MI:SS.FF3')
            AND tstamp <= to_timestamp(' :ora_lastendtime', 'YYYY-MM-DD HH24:MI:SS.FF3')
            """,
            {
                'colname': colname,
                'fdc_rawdata': "fdc.{}_rawdata".format(toolid),
                'psql_lastendtime': psql_lastendtime
                'ora_lastendtime': ora_lastendtime
            }
        )