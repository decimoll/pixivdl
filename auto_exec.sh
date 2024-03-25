#!/bin/bash

progra_name=pixivdl
logmail=/home/decimoll/sh/logmail.sh

/usr/bin/python3 /home/decimoll/pixivdl/pixivdl.py -o'/mnt/data/decimoll/pixivdl/' -b
res=$?

$logmail "[     ]" "$progra_name exit with status ${res}." "$progra_name: EXITED" "$progra_nameはステータス${res}で終了しました。"

