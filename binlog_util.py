import time, argparse, sys, pymysql, datetime
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.row_event import WriteRowsEvent, UpdateRowsEvent, DeleteRowsEvent

#ʹ�õĵ�����ģ��
#pip install mysql-replication
#git��ַ��https://github.com/noplay/python-mysql-replication

#����ʾ��
#1.�鿴��ǰMasterʹ�õ�log-file����ͷ��ʼ��ȡ
#1.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310
#2.Ĭ�϶�ȡlog-file�ļ�����start-posλ�ö�ȡ�����pos����ȷ������
#2.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000009 --start-pos=123
#3.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000009 --start-pos=123 --databases=db1 --tables=t1
#4.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000009 --start-pos=123 --out-file=/opt/my.txt
#5�������ص�SQL���
#5.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000009 --start-pos=123 --out-file=/opt/my.txt -B
#6.����ʱ�����ɸѡ
#6.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000010 --start-datetime='2011-06-01 20:00:00'
#6.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000010 --end-datetime='2019-06-01 20:00:00'
#6.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000010 --start-datetime='2016-09-01 20:00:00' --end-datetime='2019-06-01 20:00:00'
#7.����start��end pos������binlog��־
#7.python binlog_util.py --host=192.168.11.128 --user=yancg --password=123456 --port=3310 --log-file=mysql_bin.000010 --start-pos=512 --end-pos=1228

#������
#Ĭ��sql��ŵ�·��Ϊ/tmp/binlog.sql
#��������һЩ���sql����Ҫ��дdatabases����
#�������log-file������Ĭ��ֵ��ȡlog-fileָ���Ķ�������־
#start-datetime��end-datetime���������������׽��ж�������־��ɸѡ

connection_settings = {}
insert_sql = "INSERT INTO `{0}`.`{1}` ({2}) VALUES ({3});"
update_sql = "UPDATE `{0}`.`{1}` set {2} WHERE {3};"
delete_sql = "DELETE FROM `{0}`.`{1}` WHERE {2};"

def sql_format(dic, split_value):
    list = []
    for key, value in dic.items():
        if(value == None):
            list.append("`%s`=null" % key)
            continue
        if(isinstance(value, int)):
            list.append("`%s`=%d" % (key, value))
        else:
            list.append("`%s`='%s'" % (key, value))
    return split_value.join(list)

def sql_format_for_insert(values):
    list = []
    for value in values:
        if (value == None):
            list.append("null")
            continue
        if (isinstance(value, int)):
            list.append('%d' % value)
        else:
            list.append('\'%s\'' % value)
    return ', '.join(list)

def check_arguments():
    global connection_settings
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, dest="host", help="mysql host")
    parser.add_argument("--port", type=int, dest="port", help="mysql port")
    parser.add_argument("--user", type=str, dest="user", help="mysql user")
    parser.add_argument("--password", type=str, dest="password", help="mysql password")
    parser.add_argument("--log-file", type=str, dest="log_file", help="")
    parser.add_argument("--start-file", type=str, dest="start_file", help="")
    parser.add_argument("--start-pos", type=int, dest="start_pos", help="")
    parser.add_argument("--end-pos", type=int, dest="end_pos", help="")
    parser.add_argument("--end-file", type=str, dest="end_file", help="")
    parser.add_argument("--out-file", type=str, dest="out_file", help="")
    parser.add_argument("--start-datetime", type=str, dest="start_datetime", help="")
    parser.add_argument("--end-datetime", type=str, dest="end_datetime", help="")
    parser.add_argument("-B", "--flashback", dest="flashback", help="", default=False, action='store_true')
    parser.add_argument('-d', '--databases', dest='databases', type=str, nargs='*', help='dbs you want to process', default='')
    parser.add_argument('-t', '--tables', dest='tables', type=str, nargs='*', help='tables you want to process', default='')
    args = parser.parse_args()

    if not args.host or not args.user or not args.password:
        print(parser.format_usage())
        sys.exit(1)
    if(not args.port):
        args.port = 3306
    if(not args.out_file):
        args.out_file = "/tmp/binlog.sql"
    if(not args.start_pos):
        args.start_pos = 0
    args.tables = args.tables if args.tables else None
    args.start_pos = args.start_pos if args.start_pos else 4
    args.end_pos = args.end_pos if args.end_pos else None
    args.databases = args.databases if args.databases else None
    args.start_datetime = datetime.datetime.strptime(args.start_datetime, "%Y-%m-%d %H:%M:%S") if args.start_datetime else None
    args.end_datetime = datetime.datetime.strptime(args.end_datetime, "%Y-%m-%d %H:%M:%S") if args.end_datetime else None
    connection_settings = {'host': args.host, 'port': args.port, 'user': args.user, 'passwd': args.password}

    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**connection_settings)
        cursor = conn.cursor()
        cursor.execute("select @@server_id;")
        args.server_id = cursor.fetchone()[0]
        if(not args.log_file):
            cursor.execute("show master status;")
            args.log_file = cursor.fetchone()[0]
    finally:
        if(cursor != None):
            cursor.close()
        if(conn != None):
            conn.close()
    return args

def binlog_process(args):
    file = None
    stream = None
    sql_list = []
    try:
        file = open(args.out_file, "w+")
        stream = BinLogStreamReader(connection_settings=connection_settings, log_file=args.log_file, log_pos=args.start_pos,
                                    resume_stream=True, only_schemas=args.databases, only_tables=args.tables, server_id=args.server_id)

        for binlogevent in stream:
            if(args.log_file != stream.log_file):
                break

            if(args.end_pos != None):
                if(binlogevent.packet.log_pos > args.end_pos):
                    break

            if(args.start_datetime != None):
                if(datetime.datetime.fromtimestamp(binlogevent.timestamp) < args.start_datetime):
                    continue

            if(args.end_datetime != None):
                if(datetime.datetime.fromtimestamp(binlogevent.timestamp) > args.end_datetime):
                    break

            if (isinstance(binlogevent, WriteRowsEvent)):
                for row in binlogevent.rows:
                    if(args.flashback):
                        sql_list.append(delete_to_sql(row, binlogevent) + "\n")
                    else:
                        sql_list.append(insert_to_sql(row, binlogevent) + "\n")
            elif (isinstance(binlogevent, DeleteRowsEvent)):
                for row in binlogevent.rows:
                    if(args.flashback):
                        sql_list.append(insert_to_sql(row, binlogevent) + "\n")
                    else:
                        sql_list.append(delete_to_sql(row, binlogevent) + "\n")
            elif (isinstance(binlogevent, UpdateRowsEvent)):
                for row in binlogevent.rows:
                    sql_list.append(update_to_sql(row, binlogevent, args.flashback) + "\n")
        file.writelines(sql_list)
    finally:
        if(stream != None):
            stream.close()
        if(file != None):
            file.close()

def insert_to_sql(row, binlogevent):
    return insert_sql.format(binlogevent.schema, binlogevent.table, ', '.join(map(lambda k: '`%s`' % k, row['values'].keys())), sql_format_for_insert(row["values"].values()))

def delete_to_sql(row, binlogevent):
    return delete_sql.format(binlogevent.schema, binlogevent.table, sql_format(row['values'], " AND "))

def update_to_sql(row, binlogevent, flashback):
    if (flashback):
        return update_sql.format(binlogevent.schema, binlogevent.table, sql_format(row['before_values'], ", "), sql_format(row['after_values'], " AND "))
    else:
        return update_sql.format(binlogevent.schema, binlogevent.table, sql_format(row['after_values'], ", "), sql_format(row['before_values'], " AND "))

if(__name__ == "__main__"):
    args = check_arguments()
    start_time = time.time()
    print("Start process binlog.....")
    binlog_process(args)
    end_time = time.time()
    print("Complete ok, total time: %d" % (end_time - start_time))
    print("Binlog save file path is: %s" % args.out_file)