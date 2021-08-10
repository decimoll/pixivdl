import sys
import argparse
import time
import os
import json
from pixivpy3 import *
import zipfile
from PIL import Image
import subprocess
import glob
import cv2

os.getcwd()
with open(os.path.dirname(os.path.abspath(__file__)) + '/conf.json', 'r') as f:
    json_load = json.load(f)
    USERNAME = json_load['username']
    PASSWORD = json_load['password']
    MY_USER_ID = json_load['my_user_id']
    REFRESH_TOKEN = json_load['refresh_token']
    ROOT_DIR = json_load['root_dir']
    WAIT = json_load['wait']

EXIFTOOL = '/usr/bin/exiftool'

# クールダウン
def wait():
    print('Waiting ' + str(WAIT) + ' second...', end='', flush=True)
    time.sleep(WAIT)

# 禁則文字の処理
def replace_prohibited_chars(s):
    pc = [['/', '／'], [':', '：'], ['.', '．'], ['*', '＊'], ['<', '＜'], ['>', '＞'], ['|', '｜'], ['?', '？'], ['\"', '”'], ['(', '（'], [')', '）'], ['[', '［'], [']', '］']]
    r = s
    for c in pc:
        r = r.replace(c[0], c[1])
    return r

# 削除されたか或は非公開か
def is_available(json_result):
    #print(json_result)
    if 'error' in json_result:
        print('This work has been deleted.')
        return False
    if 'visible' in json_result:
        if not json_result['visible']:
            print('This work is not available.' )
            return False
    elif not json_result.illust['visible']:
        print('This work is not available.')
        return False
    return True

# filesをmp4に変換する
def convert_mp4(out_dir, mp4_path, delay, width, height, files):
    fps = 1000 / delay
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    mp4 = cv2.VideoWriter(mp4_path, fourcc, fps, (width, height))
    if not mp4.isOpened:
        print('Could not convert to mp4.')
        return
    for f in files:
        img = cv2.imread(out_dir + f)
        if img is None:
            print('An error occured while cv2.imread(' + out_dir + f + ') in def convert_mp4. Could not read an image.')
            return
        mp4.write(img)
    mp4.release()

# fileにタグ付けをする
def tag(file_path, tags):
    with open('/dev/null', 'w') as devnull:
        cmd = [EXIFTOOL, file_path, '-overwrite_original']
        for t in tags:
            cmd.append('-Subject=' + t)
        subprocess.Popen(cmd, stdout=devnull, stderr=devnull)

# イラストをDL
def dl_illust(out_dir, url, work_title, work_id, work, tags):
    if api.download(url, path=out_dir, prefix=work_title+'_'):
        json_path = out_dir + work_title + '_' + work_id + '.json'
        if not os.path.isfile(json_path):
            with open(json_path, 'w') as f:
                json.dump(work, f, indent=2, ensure_ascii=False)
    else:
        print('\r' + out_dir + ' already exists.')
        return False
    return True

# うごイラをDL
def dl_ugoira(out_dir, work_title, work, tags):
    # メタデータダウンロード
    ugoira_metadata = api.ugoira_metadata(work['id'])
    delays = []
    for f in ugoira_metadata.ugoira_metadata.frames:
        delays.append(f['delay'])
    delay = sum(delays) / len(delays)
    #print(ugoira_metadata)
    url = ugoira_metadata.ugoira_metadata.zip_urls['medium']
    url = url.replace('600x600', '1920x1080')
    file_name = url.split('/')[-1]
    base_name = file_name.split('.')[0] # 横着
    width = work['width']
    height = work['height']
    #  ダウンロード 
    api.download(url, path=out_dir, prefix=work_title+'_')
    new_name = out_dir + work_title + '_' + base_name + '.ugoira'
    os.rename(out_dir + work_title + '_' + file_name, new_name)
    file_list = []
    with zipfile.ZipFile(new_name) as z:
        file_list = z.namelist()
        z.extractall(out_dir)
    # mp4変換
    mp4_path = out_dir + work_title + '_' + base_name + '.mp4'
    convert_mp4(out_dir, mp4_path, delay, width, height, file_list)
    # タグ付け用に先頭画像のみ残して他は削除
    f0 = out_dir + work_title + '_' + base_name + '_0.' + file_list[0].split('.')[-1]
    os.rename(out_dir + file_list[0], f0)
    file_list.pop(0)
    for i in file_list:
        os.remove(out_dir + i)
    # タグ付け
    tag(f0, tags)
    # metadataの保存
    with open(out_dir + work_title + '_' + base_name + '.ugoira_metadata', 'w') as f:
        json.dump(ugoira_metadata, f, indent=2)

# def download()の前半使い回し 本当はクラスとかにしたはうが良い気がするけどとりあへず
def is_duplicate(work):
    user_id = str(work.user['id'])
    user_name = work.user['name']
    work_title = work['title']
    work_id = str(work['id'])
    user_name = replace_prohibited_chars(user_name)
    work_title = replace_prohibited_chars(work_title)
    # ユーザ毎のフォルダ
    users_dir = user_name + '_'  + user_id + '/'
    # その下の作品ごとのフォルダ
    works_dir = work_title + '_' + work_id + '/'
    # 出力フォルダ
    out_dir = ROOT_DIR + users_dir + works_dir
    # たまにユーザ名を變へる人がいるからそれの対応
    # ユーザ毎のフォルダをリストアップ
    files = os.listdir(ROOT_DIR)
    dirs = [f for f in files if os.path.isdir(os.path.join(ROOT_DIR, f))]
    for d in dirs:
        # 名前が變はってもユーザIDは變はらないと思ふからIDでフォルダを検索
        if user_id == d.split('_')[-1]:
            # フォルダ名のユーザ名が現在のユーザ名と異なるならば
            if d != user_name + '_' + user_id:
                os.rename(ROOT_DIR + d, ROOT_DIR + user_name + '_' + user_id)
            break
    # 存在チェック && mkdir -pの意
    if os.path.isdir(out_dir):
        print('Directory ' + out_dir + ' already exists. Duplicate.')
        return True
    return False

# 指定したIDの作品をDL
def download(work):
    user_id = str(work.user['id'])
    user_name = work.user['name']
    work_title = work['title']
    work_id = str(work['id'])
    user_name = replace_prohibited_chars(user_name)
    work_title = replace_prohibited_chars(work_title)
    # ユーザ毎のフォルダ
    users_dir = user_name + '_'  + user_id + '/'
    # その下の作品ごとのフォルダ
    works_dir = work_title + '_' + work_id + '/'
    # 出力フォルダ
    out_dir = ROOT_DIR + users_dir + works_dir
    print('\r' + out_dir + ' downloading...', end='', flush=True)
    # たまにユーザ名を變へる人がいるからそれの対応
    # ユーザ毎のフォルダをリストアップ
    files = os.listdir(ROOT_DIR)
    dirs = [f for f in files if os.path.isdir(os.path.join(ROOT_DIR, f))]
    for d in dirs:
        # 名前が變はってもユーザIDは變はらないと思ふからIDでフォルダを検索
        if user_id == d.split('_')[-1]:
            # フォルダ名のユーザ名が現在のユーザ名と異なるならば
            if d != user_name + '_' + user_id:
                os.rename(ROOT_DIR + d, ROOT_DIR + user_name + '_' + user_id)
            break
    # 存在チェック && mkdir -pの意
    if os.path.isdir(out_dir):
        print('Directory ' + out_dir + ' already exists. Duplicate.')
        return 1
    os.makedirs(out_dir)
    json_path = out_dir + work_title + '_' + work_id + '.json'
    with open(json_path, 'w') as f:
        json.dump(work, f, indent=2, ensure_ascii=False)
    tags = [user_name, user_id]
    for t in work.tags:
        tags.append(t['name'])

    if work['type'] == 'ugoira':
        dl_ugoira(out_dir, work_title, work, tags)                       
    else:
        if work.page_count == 1:
            if not dl_illust(out_dir, work.meta_single_page['original_image_url'], work_title, work_id, work, tags):
                return 1
        elif work.page_count > 1:
            for meta_page in work.meta_pages:
                if not dl_illust(out_dir, meta_page.image_urls['original'], work_title, work_id, work, tags):
                    return 1
        files = glob.glob(out_dir + '*.png') + glob.glob(out_dir + '*.jpg')
        for f in files:
            tag(f, tags)
    print('\r' + out_dir + ' complete.     ')
    return 0

# 指定したIDの作品
def work(work_id):
    json_result = api.illust_detail(work_id)
    #print(json_result)
    if not is_available(json_result):
        return
    work = json_result.illust
    download(work)

# 指定したユーザの全作品
def user_works(user_id):
    json_result = api.user_illusts(user_id, type='illust')
    for work in json_result.illusts:
        if not is_available(work):
            return
        download(work)
        wait()
    json_result = api.user_illusts(user_id, type='manga')
    for work in json_result.illusts:
        if not is_available(work):
            return
        download(work)
        wait()

# 我がブックマークした全作品
def bookmarks():
    #MY_USER_ID = 926140
    json_user_bookmarks_work = api.user_bookmarks_illust(MY_USER_ID, restrict='public')
    json_user_detail = api.user_detail(MY_USER_ID)
    bookmark_work_num = json_user_detail.profile['total_illust_bookmarks_public']
    #print(json_user_detail)
    works = []
    is_dup = False
    while not is_dup:
        #print(json_user_bookmarks_work)
        for work in json_user_bookmarks_work.illusts:
            if not is_available(work):
                continue
            if is_duplicate(work):
                print('Duplicate. Fetch end.')
                is_dup = True
                break
            works.append(work)
            print(work['title'])
        next_url = json_user_bookmarks_work['next_url']
        if next_url is None:
            break
        next_qs = api.parse_qs(next_url)
        json_user_bookmarks_work = api.user_bookmarks_illust(**next_qs)
        wait()
    if args.reverse:
        works.reverse()
    for w in works:
        if download(w) == 1 and not args.duplicate:
            print('Duplicate')
            return
        wait()
             

###__MAIN__###
parser = argparse.ArgumentParser(prog='pixivdl', 
        usage='pixivdl.py [-h] [-w ARTWORK_ID ...] [-u USER_ID ...] [-b] [-o OUTDIR] [-d] [-r]', 
        description='Download pixiv artworks including manga.')
parser.add_argument('-w', '--works', type=int, nargs='*', help='Some artworks')
parser.add_argument('-u', '--userworks', type=int, nargs='*', help='Some user\'s all artworks')
parser.add_argument('-b', '--bookmarks', action='store_true', help='My bookmarks')
parser.add_argument('-o', '--outdir', default=ROOT_DIR, help='Output dir')
parser.add_argument('-d', '--duplicate', action='store_true', help='Ignore duplicate while downloading bookmarks')
parser.add_argument('-r', '--reverse', action='store_true', help='Reverse order while downloading bookmarks')
args = parser.parse_args()

if len(sys.argv) == 1:
    parser.print_help()
    exit(0)

api = AppPixivAPI()
for i in range(10):
    try:
        api.auth(refresh_token=REFRESH_TOKEN)
    except Exception as e:
        print(e)
        if i < 9:
            print('Retrying...')
            wait()
            api = AppPixivAPI()
            print()
            continue
        else:
            print('Tried 10 times but failed. exit(1)')
            exit(1)
    break
print('pixivdl...')
ROOT_DIR = args.outdir

if args.works != None:
    for work_id in args.works:
        if work_id > 0:
            work(work_id)
        else:
            print('ERROR: work id must be larger than 0.')
        wait()

if args.userworks != None:
    for user_id in args.userworks:
        if user_id > 0:
            user_works(user_id)
        else:
            print('ERROR: User id must be larger than 0.')
        wait()

if args.bookmarks:
    if MY_USER_ID > 0:
        bookmarks()
    else:
        print('ERROR: MY_USER_ID must be larger than 0.')

print('')

