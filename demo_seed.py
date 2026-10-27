"""Public synthetic demo fixtures; never grant a public account live privileges."""
import json
import app
PASSWORD='AcademyDemo!2026'
GROUPS=['preschool','primary','secondary','vocational','college','university','mixed']
ROLES=['superadmin','admin','teacher','student','parent','accountant','staff']
def seed():
 app.init()
 with app.connect() as c:
  for group in GROUPS:
   name='DEMO · '+group.title()+' Academy'
   existing=c.execute('SELECT t.id FROM tenants t JOIN demo_tenants d ON d.tenant=t.id WHERE t.level=?',(group,)).fetchone()
   if existing: tenant=existing[0]
   else:
    tenant=c.execute('INSERT INTO tenants(name,level) VALUES(?,?)',(name,group)).lastrowid
    c.execute('INSERT INTO demo_tenants VALUES(?)',(tenant,))
   for role in ROLES:
    email=f'{role}.{group}@demo.academy.example'
    u=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
    if u:
     if not c.execute('SELECT 1 FROM demo_users WHERE user=?',(u[0],)).fetchone(): raise ValueError('Reserved demo email already belongs to a non-demo user; no privileges changed')
     c.execute('UPDATE users SET role=?,tenant=? WHERE id=?',(role,tenant,u[0]))
    else:
     uid=c.execute('INSERT INTO users(tenant,email,password,role) VALUES(?,?,?,?)',(tenant,email,app.password(PASSWORD),role)).lastrowid
     c.execute('INSERT INTO demo_users VALUES(?)',(uid,))
   c.execute("UPDATE records SET data=replace(data,?,?) WHERE tenant=? AND module='announcements'",('Shared demo accounts are read-only.','Shared demo accounts are interactive within their role permissions.',tenant))
   if c.execute('SELECT 1 FROM records WHERE tenant=? LIMIT 1',(tenant,)).fetchone(): continue
   admin=c.execute('SELECT id FROM users WHERE tenant=? AND role=?',(tenant,'admin')).fetchone()[0]
   fixtures={
    'students':[dict(name='Alex Demo',email='student.'+group+'@demo.academy.example',level=group,guardian='Jordan Demo')],
    'staff':[dict(name='Taylor Demo',email='staff.'+group+'@demo.academy.example',title='Campus coordinator',salary='2500',hourly_rate='0')],
    'courses':[dict(name='Foundations of Learning',code='DEMO101',level=group,credits='3')],
    'lessons':[dict(name='Welcome lesson',course='DEMO101',content='Sample lesson: explore your learning goals and write three things you want to learn.',video_url='')],
    'assignments':[dict(name='Learning goals',course='DEMO101',instructions='Describe your three learning goals.',due_date='Sample assignment — no live deadline')],
    'grades':[dict(student='Alex Demo',course='DEMO101',assessment='Coursework',score='85',maximum='100',weight='40'),dict(student='Alex Demo',course='DEMO101',assessment='Final assessment',score='90',maximum='100',weight='60')],
    'progress':[dict(student='Alex Demo',period='Sample term',goals='Build confidence',observations='Steady progress and active participation',interventions='Weekly reading support')],
    'attendance':[dict(student='Alex Demo',date='2026-10-26',status='Present')],
    'invoices':[dict(student='Alex Demo',description='SAMPLE tuition — no payment required',amount='500',currency='USD',status='Demo only')],
    'announcements':[dict(name='Welcome to the demo',content='All records are fictional. Shared demo accounts are interactive within their role permissions. No real payments or purchases are available.')],
    'programs':[dict(name='Sample learning program',level=group,department='General Education',credits='30')],
    'library':[dict(name='Learning Together',author='Example Author',identifier='DEMO-001',status='Available')],
    'events':[dict(name='Sample open day',date='Example date',description='Explore the institution workspace.')],
   }
   for module,records in fixtures.items():
    for data in records:c.execute('INSERT INTO records(tenant,module,data,owner) VALUES(?,?,?,?)',(tenant,module,json.dumps(data),admin))
   questions=[dict(type='choice',prompt='Which action supports learning?',options=['Practice regularly','Never ask questions'],answer='Practice regularly',points=1)]
   c.execute('INSERT INTO exams(tenant,title,duration,questions,published) VALUES(?,?,?,?,1)',(tenant,'Sample practice assessment',10,json.dumps(questions)))
if __name__=='__main__':seed();print('Demo groups and accounts are ready')
