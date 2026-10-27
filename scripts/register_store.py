"""Update one hosted-app listing in an existing African Apps Store installation."""
import argparse,json,pathlib,sqlite3,time

def register(database,listing):
 p=pathlib.Path(database)
 if not p.is_file():raise ValueError('Existing store database not found; refusing to create a new one')
 data=json.loads(pathlib.Path(listing).read_text())
 if data['domain']!='academy.africandroid.world' or data['install_url']!='https://academy.africandroid.world/install':raise ValueError('Unexpected listing')
 with sqlite3.connect(p) as c:
  if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='hosted_apps'").fetchone():raise ValueError('Expected hosted_apps table is absent')
  backup=p.with_name(p.name+'.academy-backup-'+str(time.time_ns()))
  with sqlite3.connect(backup) as b:c.backup(b)
  backup.chmod(0o600)
  c.execute('INSERT INTO hosted_apps(domain,metadata,visible,updated) VALUES(?,?,1,?) ON CONFLICT(domain) DO UPDATE SET metadata=excluded.metadata,updated=excluded.updated',(data['domain'],json.dumps(data),int(time.time())))
 return str(backup)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--listing',required=True);a=p.parse_args();print('Store listing saved; backup: '+register(a.db,a.listing))
