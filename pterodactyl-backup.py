# sloppy backup script for pterodactyl panel. see pt-backup-cfg.json.example for configuration.
# servers in config should be specified with short or full server uuid (see server settings)
# if you are an administrator, id reccomend making a seperate user to invite to each server you want to backup, so
# you can limit the capabilities of the key you are using.

# cinnamondev, licensed under apache 2.0 license

import requests
import json
import hashlib
import os
from pathlib import Path
from dateutil import parser


with open("pt-backup-cfg.json","r") as f:
    config = json.load(f)
    
base_url = config['base_url']

s = requests.Session()
s.verify = True
s.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + config['api_key']
})

# get api key info
r = s.get(base_url + "/api/client/account").json()

if "errors" in r:
    print("could not authenticate to panel. read following json response. script will NOT continue")
    print(r)
    exit()

if r['attributes']['admin'] == True:
    print("""warning: you probably should not set this up on an admin account, 
as admins can access all servers and have much more powers. setup a non-admin account
for your api keys and invite them as a user to each server you want to manage, ideally.""")

# available servers to the user.
r = s.get(base_url + "/api/client").json()
# all servers with backups available
server_list = [(server['attributes']['identifier'], server['attributes']['uuid'], server['attributes']['name'], server['attributes']['node']) for server in r['data'] if server['attributes']['feature_limits']['backups'] > 0]

# search config file and check if each server exists.
for server in config['servers']:
    found = False
    for lserv in server_list:
        if server in (lserv[0], lserv[1]):
            server = lserv
            found = True
    if not found: # server in config is not in server list, we will skip but emit an error.
        print("""error: server "{0}" either does not exist or does not have backups enabled.
in your config file, you should specify which server to use with the uuid of the server. (short or long identifier).""".format(server))
        continue

    
    r = s.get(base_url + "/api/client/servers/" + server[0] + "/backups").json()
    if len(r['data']) <= 0: # go no further if there are no backups
        print("""note: server "{0}" has no backups created. skipping...""".format(server))
        continue
    
        # sort by date & pull out attributes we find useful
    backups = sorted(
        [(data['attributes']['uuid'], parser.parse(data['attributes']['completed_at']), data['attributes']['checksum']) for data in r['data']],
        key=lambda t: t[1],
        reverse=True
    )

    latest = backups[0]
    # generate backup url
    r = s.get(base_url + "/api/client/servers/" + server[0] + "/backups/" + latest[0] + "/download").json()
    # filename
    filename = config['file-format-string'].format( # human readable filename
        node=server[3], 
        server_name=server[2],
        shortuuid=server[0],
        checksum=latest[2].strip("sha1:"),
        year=latest[1].year,
        month=latest[1].month,
        day=latest[1].day,
        hour=latest[1].hour,
        minute=latest[1].minute,
        second=latest[1].second,
    )
    Path(config['backups']).mkdir(parents=True,exist_ok=True)
    full_path = config['backups'] + filename

    downloaded = False
    validated = False
    if Path(full_path).is_file():
        downloaded = True # skip the download step if the file exists, but if its invalid we will retry.

    fail_count = 0
    while (not downloaded) or (not validated): # the download step will repeat up to 3 times before skipping. 
        if not downloaded:
            r = requests.get(r['attributes']['url'], stream=True)
            r.raise_for_status()
            chunk_size = 8192
            total_len = int(r.headers.get('content-length'))
            with open(full_path,'wb') as f:             # write backup in 8192 b chunks
                c=0
                for chunk in r.iter_content(chunk_size):
                    c+=chunk_size
                    percent = (c/float(total_len))*100.0
                    print(              # progress % display
                        "DOWNLOADING {server_name} ({shortuuid}): {0:0.2f} %".format(
                            percent, 
                            server_name=server[2], 
                            shortuuid=server[0],
                        ),
                        end='\r', flush=True)
                    f.write(chunk)
            downloaded = True # mark as downloaded, may be considered not downloaded in the next step

        chunk_size = 65536
        # validation step
        with open(full_path,'rb') as f:
            c=0
            size = os.path.getsize(full_path)
            sha1 = hashlib.sha1()
            while data := f.read(chunk_size): # update checksum in chunks
                c+=chunk_size
                percent = (c/float(size))*100.0
                print("VALIDATING {server_name} ({shortuuid}): {0:0.2f} %".format(
                            percent, 
                            server_name=server[2], 
                            shortuuid=server[0],
                        ),
                        end='\r',flush=True)
                sha1.update(data)

        if sha1.hexdigest() == latest[2].strip("sha1:"):  #     LOOP EXIT CONDITION - if the download can be validated, we will move on
            print("COMPLETE {server_name} ({shortuuid})".format(server_name=server[2],shortuuid=server[0],),end='\r',flush=True)
            print("\n")
            validated = True
        else: # increment failcount and invalidate download if 
            print("RETRY {server_name} ({shortuuid})".format(server_name=server[2],shortuuid=server[0],),end='\r',flush=True)
            fail_count+=1
            downloaded=False
            validated=False

        if fail_count == 3:                             # LOOP EXIT CONDITION - failed too many times.
            print("Failed checksum on {server_name} ({shortuuid}) 3 times, skipping!!".format(server_name=server[2], shortuuid=server[0]),end='\r', flush=True)
            print("\n")
            break
