# -*- coding: utf-8 -*-

'''
#自动创建从库
#一丶mysqldump创建
    1.首先从主库进行备份，备份在本地
    2.然后导入到从库

#二丶xtrabackup备份
    1.首先检测有没有安装
    2.slave机器进行备份
    3.把安装包同步到本地机器
    4.数据库恢复
    5.启动
'''
