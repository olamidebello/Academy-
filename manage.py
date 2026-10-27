import argparse,getpass
import app
p=argparse.ArgumentParser(); p.add_argument('command',choices=['init','create-superadmin']); p.add_argument('email',nargs='?'); a=p.parse_args(); app.init()
if a.command=='create-superadmin':
 if not a.email: p.error('email required')
 pw=getpass.getpass('New password (12+ characters): ')
 if len(pw)<12: p.error('Password too short')
 with app.connect() as c:
  t=c.execute('SELECT id FROM tenants ORDER BY id LIMIT 1').fetchone()
  if not t: c.execute("INSERT INTO tenants(name,level) VALUES('Academy Headquarters','all')"); tid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
  else: tid=t[0]
  c.execute('INSERT INTO users(tenant,email,password,role) VALUES(?,?,?,?)',(tid,a.email.lower(),app.password(pw),'superadmin'))
 print('Super administrator created')
