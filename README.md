# pterodactyl-backup-job

pterodactyl panel fetch latest backup and rename
uses systemd timer to run weekly, to setup configure install directory etc in `server-backup.service`.
config file `pt-backup-cfg.json` must be in the current working directory of wherever `pterodactyl-backup.py` is executed!

if you are using an administrator account, it is reccomended to make a user you invite to each server you want to backup, so that if your api key is ever found, it is limited in its capabilities.

## example config

```
{
    "api_key": "ptlc_yourapikey",
    "base_url": "http://panel.foo.org",
    "backups": "/srv/server-backups/",
    "file-format-string": "{node}.{server_name}.{shortuuid}.{checksum}.{year}-{month}-{day}_{hour}{minute}{second}.backup.tar.gz",
    "servers": [
        "d80eda9e",
        "f324fa5a-098b-47ef-bceb-85c140293ad5"
    ]
}
```