"""Academy: dependency-free, tenant-scoped school operations server."""
from pathlib import Path
import os, sqlite3, json, secrets, hashlib, hmac, time, math, html, re
from datetime import datetime, timezone
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
DB=os.environ.get('ACADEMY_DB','academy.db')
ROLES={'admin','teacher','student','parent','accountant','staff'}
MODULES={'students':['name','email','level','guardian'], 'staff':['name','email','title','salary','hourly_rate'], 'courses':['name','code','level','credits'], 'lessons':['name','course','content','video_url'], 'assignments':['name','course','instructions','due_date'], 'submissions':['assignment','answer'], 'attendance':['student','date','status'], 'grades':['student','course','assessment','score','maximum','weight'], 'progress':['student','period','goals','observations','interventions'], 'invoices':['student','description','amount','currency','status'], 'library':['name','author','identifier','status'], 'transport':['name','route','driver'], 'hostels':['name','room','capacity'], 'inventory':['name','quantity','location'], 'announcements':['name','content'], 'leave':['staff','start','end','reason','status'], 'promotions':['staff','title','salary','effective_date','reason'], 'programs':['name','level','department','credits'], 'timetable':['course','teacher','day','start','end','room'], 'admissions':['name','email','level','status'], 'events':['name','date','description']}
READ={'teacher':set(MODULES)-{'staff','promotions'},'student':{'courses','lessons','assignments','announcements','timetable','events','programs'},'parent':{'announcements','events'},'accountant':{'staff','invoices','promotions'},'staff':{'announcements','events','timetable'}}
WRITE={'teacher':{'lessons','assignments','attendance','grades','progress'},'accountant':{'invoices'},'student':{'submissions'},'staff':set(),'parent':set()}
def connect():
 c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
 with connect() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS tenants(id INTEGER PRIMARY KEY,name TEXT,level TEXT,settings TEXT DEFAULT '{}');
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,tenant INTEGER,email TEXT UNIQUE,password TEXT,role TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user INTEGER,expires REAL);
CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY,tenant INTEGER,module TEXT,data TEXT,owner INTEGER);
CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY,tenant INTEGER,title TEXT,duration INTEGER,questions TEXT,published INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,tenant INTEGER,exam INTEGER,user INTEGER,started REAL,answers TEXT DEFAULT '{}',submitted INTEGER DEFAULT 0,score REAL,UNIQUE(exam,user));
CREATE TABLE IF NOT EXISTS punches(id INTEGER PRIMARY KEY,tenant INTEGER,user INTEGER,action TEXT,at REAL,lat REAL,lon REAL,accuracy REAL);
CREATE TABLE IF NOT EXISTS payroll(id INTEGER PRIMARY KEY,tenant INTEGER,start REAL,end REAL,data TEXT,created REAL);
CREATE TABLE IF NOT EXISTS demo_tenants(tenant INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS demo_users(user INTEGER PRIMARY KEY);
CREATE TABLE IF NOT EXISTS legal_acceptances(user INTEGER,version TEXT,accepted REAL);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,tenant INTEGER,user INTEGER,action TEXT,at REAL);
''')
def password(p,salt=None):
 salt=salt or secrets.token_hex(16); return salt+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),salt.encode(),310000).hex()
def verify(p,encoded): return hmac.compare_digest(password(p,encoded.split(':')[0]),encoded)
def audit(c,u,action): c.execute('INSERT INTO audit(tenant,user,action,at) VALUES(?,?,?,?)',(u['tenant'],u['id'],action,time.time()))
def distance(a,b,c,d):
 x,y=math.radians(c-a),math.radians(d-b); return 6371000*2*math.asin(math.sqrt(math.sin(x/2)**2+math.cos(math.radians(a))*math.cos(math.radians(c))*math.sin(y/2)**2))
def api(path,method,d,u,c):
 tenant=u['tenant']; role=u['role']
 demo=bool(c.execute('SELECT 1 FROM demo_users WHERE user=?',(u['id'],)).fetchone())
 if demo:
  if not c.execute('SELECT 1 FROM demo_tenants WHERE tenant=?',(tenant,)).fetchone(): raise PermissionError('Demo account is outside its sandbox')
  if method!='GET' or path in {'/api/switch-tenant','/api/attempt'}: raise PermissionError('Public demo accounts are read-only. Create your own institution to save changes.')
 def admin():
  if role not in {'admin','superadmin'}: raise PermissionError('Administrator access required')
 if path=='/api/me': return {**dict(u),'is_demo':demo}
 if path=='/api/tenants':
  if role!='superadmin': raise PermissionError('Platform administrator required')
  if method=='POST': c.execute('INSERT INTO tenants(name,level) VALUES(?,?)',(d['name'],d['level'])); audit(c,u,'create institution')
  return [dict(r) for r in c.execute('SELECT * FROM tenants'+(' WHERE id IN (SELECT tenant FROM demo_tenants)' if demo else ''))]
 if path=='/api/switch-tenant':
  if role!='superadmin': raise PermissionError('Platform administrator required')
  if method!='POST' or not c.execute('SELECT 1 FROM tenants WHERE id=?',(d.get('tenant'),)).fetchone(): raise ValueError('Valid institution required')
  c.execute('UPDATE users SET tenant=? WHERE id=?',(d['tenant'],u['id'])); audit(c,u,'switch institution'); return {'ok':True}
 if path=='/api/users':
  admin()
  if method=='POST':
   if d['role'] not in ROLES: raise ValueError('Invalid role')
   if len(d['password'])<12: raise ValueError('Password must have at least 12 characters')
   c.execute('INSERT INTO users(tenant,email,password,role) VALUES(?,?,?,?)',(tenant,d['email'].lower(),password(d['password']),d['role'])); audit(c,u,'create user')
  return [dict(r) for r in c.execute('SELECT id,email,role FROM users WHERE tenant=?',(tenant,))]
 if path=='/api/settings':
  admin()
  if method=='POST':
   if 'geofence' in d:
    g=d['geofence']; assert -90<=float(g['lat'])<=90 and -180<=float(g['lon'])<=180 and 10<=float(g['radius'])<=100000
   c.execute('UPDATE tenants SET settings=? WHERE id=?',(json.dumps(d),tenant)); audit(c,u,'update settings')
  return json.loads(c.execute('SELECT settings FROM tenants WHERE id=?',(tenant,)).fetchone()[0])
 if path.startswith('/api/records/'):
  mod=path.split('/')[3]
  if mod not in MODULES: raise ValueError('Unknown module')
  own=mod in {'submissions','leave'} and role not in {'admin','superadmin','teacher','accountant'}
  if role not in {'admin','superadmin'} and mod not in READ.get(role,set()) and not own: raise PermissionError('Module access denied')
  if method=='POST':
   if role not in {'admin','superadmin'} and mod not in WRITE.get(role,set()) and mod!='leave': raise PermissionError('Write access denied')
   data={k:str(d.get(k,''))[:20000] for k in MODULES[mod]}
   if mod=='grades':
    if float(data['maximum'])<=0 or not 0<=float(data['score'])<=float(data['maximum']) or float(data['weight'])<=0: raise ValueError('Invalid grade')
   c.execute('INSERT INTO records(tenant,module,data,owner) VALUES(?,?,?,?)',(tenant,mod,json.dumps(data),u['id'])); audit(c,u,'create '+mod)
  rows=c.execute('SELECT * FROM records WHERE tenant=? AND module=?'+(' AND owner=?' if own else ''),(tenant,mod,u['id']) if own else (tenant,mod))
  return [{'id':r['id'],**json.loads(r['data'])} for r in rows]
 if path=='/api/report':
  if role not in {'admin','superadmin','teacher'}: raise PermissionError('Report access denied')
  groups={}
  for r in c.execute("SELECT data FROM records WHERE tenant=? AND module='grades'",(tenant,)):
   g=json.loads(r[0]); k=(g['student'],g['course']); groups.setdefault(k,[]).append(g)
  settings=json.loads(c.execute('SELECT settings FROM tenants WHERE id=?',(tenant,)).fetchone()[0]); scale=settings.get('grade_scale',[[90,'A'],[80,'B'],[70,'C'],[60,'D'],[0,'F']])
  result=[]
  for (student,course),gs in groups.items():
   score=sum(float(g['score'])/float(g['maximum'])*float(g['weight']) for g in gs)/sum(float(g['weight']) for g in gs)*100
   letter=next((label for floor,label in sorted(scale,reverse=True) if score>=float(floor)),'F'); result.append(dict(student=student,course=course,percentage=round(score,2),grade=letter))
  return result
 if path=='/api/exams':
  if method=='POST':
   if role not in {'admin','superadmin','teacher'}: raise PermissionError('Exam author access required')
   qs=d['questions']
   if not qs or not 1<=int(d['duration'])<=1440: raise ValueError('Questions and valid duration required')
   for q in qs:
    if q['type'] not in {'choice','essay'} or float(q['points'])<=0: raise ValueError('Invalid question')
    if q['type']=='choice' and q['answer'] not in q['options']: raise ValueError('Answer must match an option')
   c.execute('INSERT INTO exams(tenant,title,duration,questions,published) VALUES(?,?,?,?,?)',(tenant,d['title'],int(d['duration']),json.dumps(qs),int(bool(d.get('published'))))); audit(c,u,'create exam')
  rows=c.execute('SELECT * FROM exams WHERE tenant=?',(tenant,)); return [dict(id=r['id'],title=r['title'],duration=r['duration'],published=r['published']) for r in rows if r['published'] or role in {'admin','superadmin','teacher'}]
 if path=='/api/attempt':
  if role!='student': raise PermissionError('Student account required')
  e=c.execute('SELECT * FROM exams WHERE id=? AND tenant=? AND published=1',(int(d['exam']),tenant)).fetchone()
  if not e: raise ValueError('Exam unavailable')
  c.execute('INSERT OR IGNORE INTO attempts(tenant,exam,user,started) VALUES(?,?,?,?)',(tenant,e['id'],u['id'],time.time()))
  a=c.execute('SELECT * FROM attempts WHERE exam=? AND user=?',(e['id'],u['id'])).fetchone(); qs=json.loads(e['questions']); expired=time.time()>a['started']+e['duration']*60
  if method=='POST' and 'answers' in d and not a['submitted'] and not expired:
   c.execute('UPDATE attempts SET answers=? WHERE id=?',(json.dumps(d['answers']),a['id']))
  if (d.get('submit') or expired) and not a['submitted']:
   answers=json.loads(c.execute('SELECT answers FROM attempts WHERE id=?',(a['id'],)).fetchone()[0]); score=sum(float(q['points']) for i,q in enumerate(qs) if q['type']=='choice' and answers.get(str(i))==q['answer'])
   c.execute('UPDATE attempts SET submitted=1,score=? WHERE id=?',(score,a['id']))
  a=c.execute('SELECT * FROM attempts WHERE id=?',(a['id'],)).fetchone()
  return dict(id=a['id'],deadline=a['started']+e['duration']*60,submitted=bool(a['submitted']),score=a['score'],questions=[{k:v for k,v in q.items() if k!='answer'} for q in qs],answers=json.loads(a['answers']),note='Essay answers require teacher review; score is provisional.')
 if path=='/api/clock':
  if method=='POST':
   settings=json.loads(c.execute('SELECT settings FROM tenants WHERE id=?',(tenant,)).fetchone()[0]); g=settings.get('geofence')
   if not g: raise ValueError('Administrator must configure campus geofence first')
   lat,lon,acc=float(d['lat']),float(d['lon']),float(d['accuracy'])
   if not -90<=lat<=90 or not -180<=lon<=180 or not 0<=acc<=100: raise ValueError('Location accuracy must be within 100 metres')
   if distance(lat,lon,float(g['lat']),float(g['lon']))>float(g['radius']): raise ValueError('Outside permitted campus area; ask administrator to review')
   last=c.execute('SELECT action FROM punches WHERE tenant=? AND user=? ORDER BY id DESC LIMIT 1',(tenant,u['id'])).fetchone(); action=d['action']
   if action not in {'in','out'} or (last and last[0]==action) or (not last and action=='out'): raise ValueError('Clock in and out must alternate')
   c.execute('INSERT INTO punches(tenant,user,action,at,lat,lon,accuracy) VALUES(?,?,?,?,?,?,?)',(tenant,u['id'],action,time.time(),lat,lon,acc)); audit(c,u,'clock '+action)
  return [dict(r) for r in c.execute('SELECT * FROM punches WHERE tenant=? AND user=? ORDER BY id DESC',(tenant,u['id']))]
 if path=='/api/payroll':
  if role not in {'admin','superadmin','accountant'}: raise PermissionError('Payroll access required')
  if method=='POST':
   start,end=float(d['start']),float(d['end'])
   if not start<end: raise ValueError('Invalid payroll period')
   if c.execute('SELECT 1 FROM payroll WHERE tenant=? AND start<? AND end>?',(tenant,end,start)).fetchone(): raise ValueError('Overlapping payroll period already exists')
   output=[]
   for r in c.execute("SELECT data FROM records WHERE tenant=? AND module='staff'",(tenant,)):
    s=json.loads(r[0]); user=c.execute('SELECT id FROM users WHERE tenant=? AND email=?',(tenant,s['email'].lower())).fetchone(); hours=0
    if user:
     pending=None
     for p in c.execute('SELECT * FROM punches WHERE tenant=? AND user=? AND at<? ORDER BY at',(tenant,user[0],end)):
      if p['action']=='in': pending=p['at']
      elif pending is not None: hours+=max(0,min(p['at'],end)-max(pending,start))/3600; pending=None
    gross=round(hours*float(s.get('hourly_rate') or 0) if float(s.get('hourly_rate') or 0)>0 else float(s.get('salary') or 0),2)
    output.append(dict(name=s['name'],hours=round(hours,2),gross=gross,status='draft; administrator must review deductions and approve payment'))
   c.execute('INSERT INTO payroll(tenant,start,end,data,created) VALUES(?,?,?,?,?)',(tenant,start,end,json.dumps(output),time.time())); audit(c,u,'generate draft payroll')
  return [dict(r) for r in c.execute('SELECT * FROM payroll WHERE tenant=? ORDER BY id DESC',(tenant,))]
 if path=='/api/audit':
  admin(); return [dict(r) for r in c.execute('SELECT * FROM audit WHERE tenant=? ORDER BY id DESC LIMIT 200',(tenant,))]
 raise ValueError('Unknown endpoint')
def register_institution(c,d):
 email=str(d.get('email','')).strip().lower()
 name=str(d.get('institution','')).strip()
 level=str(d.get('level','')).strip()
 pw=d.get('password','')
 if not 2<=len(name)<=200: raise ValueError('Enter an institution name (2–200 characters)')
 if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email) or len(email)>254: raise ValueError('Enter a valid email address')
 if not isinstance(pw,str) or not 12<=len(pw)<=256: raise ValueError('Password must contain 12–256 characters')
 if pw!=d.get('confirm_password'): raise ValueError('Passwords do not match')
 if level not in {'preschool','primary','secondary','vocational','college','university','mixed'}: raise ValueError('Select an educational level')
 if d.get('accept_terms') not in (True,'on'): raise ValueError('Accept the terms and acknowledge the privacy notice')
 if c.execute('SELECT 1 FROM users WHERE email=?',(email,)).fetchone(): raise ValueError('This email is already registered. Sign in or contact your administrator.')
 tenant=c.execute('INSERT INTO tenants(name,level) VALUES(?,?)',(name,level)).lastrowid
 uid=c.execute('INSERT INTO users(tenant,email,password,role) VALUES(?,?,?,?)',(tenant,email,password(pw),'admin')).lastrowid
 c.execute('INSERT INTO legal_acceptances VALUES(?,?,?)',(uid,'2026-10-26',time.time()))
 audit(c,{'tenant':tenant,'id':uid},'institution self-registration and legal acceptance')
 return {'ok':True,'message':'Institution created. You can now sign in.'}

def application(env,start):
 status='200 OK'; headers=[('Content-Type','application/json'),('X-Content-Type-Options','nosniff'),('X-Frame-Options','DENY'),('Cache-Control','no-store'),('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'")]
 try:
  path=env.get('PATH_INFO','/'); method=env['REQUEST_METHOD']
  if path in {'/','/signup','/demo','/terms','/privacy','/copyright','/static/app.js','/static/style.css'}:
   file={'/':'index.html','/signup':'index.html','/demo':'demo.html','/terms':'terms.html','/privacy':'privacy.html','/copyright':'copyright.html','/static/app.js':'app.js','/static/style.css':'style.css'}[path]; body=(Path(__file__).parent/'static'/file).read_bytes(); headers[0]=('Content-Type','text/html; charset=utf-8' if file.endswith('.html') else 'text/javascript' if path.endswith('js') else 'text/css')
  elif path=='/health': body=b'{"status":"ok"}'
  else:
   size=int(env.get('CONTENT_LENGTH') or 0)
   if size>1000000: raise ValueError('Request too large')
   d=json.loads(env['wsgi.input'].read(size) or b'{}') if method=='POST' else {k:v[0] for k,v in parse_qs(env.get('QUERY_STRING','')).items()}
   with connect() as c:
    cookies=dict(pair.strip().split('=',1) for pair in env.get('HTTP_COOKIE','').split(';') if '=' in pair); token=cookies.get('academy','')
    u=c.execute('SELECT u.id,u.tenant,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user WHERE s.token=? AND s.expires>?',(token,time.time())).fetchone()
    if path=='/api/signup':
     if method!='POST' or env.get('HTTP_X_ACADEMY_REQUEST')!='1': raise PermissionError('Request validation failed')
     bucket='signup:'+env.get('REMOTE_ADDR',''); now=time.time(); recent=[t for t in LOGIN.get(bucket,[]) if t>now-3600]; LOGIN[bucket]=recent
     if len(recent)>=5: raise PermissionError('Too many registration attempts; please try again later')
     recent.append(now); result=register_institution(c,d)
    elif path=='/api/login':
     if method!='POST': raise ValueError('POST required')
     bucket=env.get('REMOTE_ADDR',''); now=time.time(); recent=[t for t in LOGIN.get(bucket,[]) if t>now-300]; LOGIN[bucket]=recent
     if len(recent)>=10: raise PermissionError('Too many attempts; wait five minutes')
     recent.append(now); found=c.execute('SELECT * FROM users WHERE email=?',(d.get('email','').lower(),)).fetchone()
     if not found or not verify(d.get('password',''),found['password']): raise PermissionError('Invalid credentials')
     token=secrets.token_hex(32); c.execute('INSERT INTO sessions VALUES(?,?,?)',(token,found['id'],now+28800)); headers.append(('Set-Cookie',f'academy={token}; HttpOnly; SameSite=Strict; Path=/'+('; Secure' if os.environ.get('ACADEMY_SECURE_COOKIE')=='1' else ''))); result={'ok':True}
    else:
     if not u: raise PermissionError('Please sign in')
     if method=='POST' and env.get('HTTP_X_ACADEMY_REQUEST')!='1': raise PermissionError('Request validation failed')
     if path=='/api/logout': c.execute('DELETE FROM sessions WHERE token=?',(token,)); result={'ok':True}
     else: result=api(path,method,d,u,c)
    body=json.dumps(result).encode()
 except PermissionError as e: status='403 Forbidden'; body=json.dumps({'error':str(e)}).encode()
 except (ValueError,KeyError,TypeError,AssertionError,sqlite3.IntegrityError) as e: status='400 Bad Request'; body=json.dumps({'error':str(e) or 'Invalid input'}).encode()
 except Exception: status='500 Internal Server Error'; body=b'{"error":"Internal server error"}'
 start(status,headers); return [body]
LOGIN={}
if __name__=='__main__':
 init(); make_server('127.0.0.1',int(os.environ.get('PORT','18840')),application).serve_forever()
