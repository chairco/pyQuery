# rot_db.R
# Query and Insert Postgresql's command

# load necessary package
library(RPostgreSQL)


# load necessary function
source("env.R")


drv_psql.etl_rot <- dbDriver("PostgreSQL")
con_psql.etl_rot <- dbConnect(drv_psql.etl_rot, 
    dbname = psql.dbname, host = psql.host, 
    port = psql.port, user = psql.username, 
    password = psql.password)
#on.exit(dbDisconnect(con_oracle.etl_rot, force = TRUE))

get_rawdatas <- function(toolid, update_starttime, update_endtime) {
    sql <- sprintf(
        "
        SELECT * 
        FROM %s 
        WHERE tstamp >= '%s' 
        AND tstamp < '%s'
        ",paste0(toolid,"_rawdata"), 
            update_starttime, 
            update_endtime
    )
    rawdata <- dbGetQuery(con_psql.etl_rot, sql)
    return (rawdata)
}


get_rotcols <- function() {
    sql <- sprintf(
        "
        SELECT col_name
        FROM %s
        WHERE 1 = 1
        AND category = 'tp_al'  
        ", "tlcd_avm_col"
    )
    rot_cols <- dbGetQuery(con_psql.etl_rot, sql)[, 1]
    rot_cols <- rot_cols[order(substring(rot_cols, 10, 10), substring(rot_cols, 8, 8))]
    return (rot_cols)
}


get_prodwithdv <- function() {
    sql = sprintf( 
        "
        SELECT DISTINCT product 
        FROM %s 
        ","tlcd_nikon_main_v"
    )
    prod_with_dv <- dbGetQuery(con_psql.etl_rot, sql)[, 1]
    return (prod_with_dv)
}


insert_rot_value <- function(rot_log_ht_record, rot_data_record) {
    sql <- sprintf(
        "
        WITH insert_rot_ht AS (
          INSERT INTO %s(%s)
          Values
          %s
        RETURNING rot_id
        ), insert_rot_data AS (
          INSERT INTO %s(item_name, rot_rs, rot_id)
          Values
          %s
        )
        SELECT TRUE
        ",
        "tlcd_nikon_rot_log_ht",
        "tstamp, glassid, toolid, operation, product, flag",
        rot_log_ht_record,
        "tlcd_nikon_rot_bt",
        rot_data_record
    )
    ret <- dbGetQuery(con_psql.etl_rot, sql)
    return (ret)
}


insert_mea_value <- function(rot_log_ht_record, rot_data_record) {
    sql <- sprintf(
        "
        WITH insert_rot_ht AS (
          INSERT INTO %s(%s)
          Values
          %s
        RETURNING rot_id
        ), insert_rot_data AS (
          INSERT INTO %s(item_name, rot_rs, rot_id)
          Values
          %s
        )
        SELECT TRUE
        ",
        "tlcd_nikon_rot_log_ht",
        "tstamp, glassid, operation, product, flag",
        rot_log_ht_record,
        "tlcd_nikon_rot_bt",
        rot_data_record
    )
    ret <- dbGetQuery(con_psql.etl_rot, sql)
    return (ret)
}


insert_error <- function(rot_error_record) {
    sql <- sprintf(
        "
        INSERT INTO %s(%s)
        Values %s
        ","tlcd_nikon_rot_log_ht", 
        "tstamp, glassid, toolid, operation, product, flag, descr", 
        rot_error_record
    )
    ret <- dbGetQuery(con_psql.etl_rot, sql)
    return (ret)
}


insert_error_mea <- function(rot_error_record) {
    sql <- sprintf(
        "
        INSERT INTO %s(%s)
        Values %s
        ","tlcd_nikon_rot_log_ht", 
        "tstamp, glassid, operation, product, flag, descr", 
        rot_error_record
    )
    ret <- dbGetQuery(con_psql.etl_rot, sql)
    return (ret)
}


get_designvalue <- function(prodt, dvtable) {
    sql = sprintf(
        "
        SELECT
          s.pos_no, s.x_coord AS x, s.y_coord AS y
        FROM
          %s s,
          (
          SELECT
          cfg_id
          FROM
          %s t
          WHERE 1 = 1
          AND product = '%s'
          ) a
        WHERE 1 = 1
        AND s.cfg_id = a.cfg_id;
        ", dvtable, "tlcd_nikon_main_v", prodt
    )
    DV_cord <- dbGetQuery(con_psql.etl_rot, sql)
    return (DV_cord)
}


psql_disconnectdb <- function() {
    #dbDisconnect(con_psql.etl_rot, force = TRUE)
    on.exit(dbDisconnect(con_psql.etl_rot, force = TRUE))
}