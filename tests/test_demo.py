import unittest,tempfile,os,json,shutil
import app
from demo_seed import seed,GROUPS,ROLES,PASSWORD
class DemoTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.database=os.path.join(cls.tmp.name,'demo.db');app.DB=cls.database;seed()
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  app.DB=os.path.join(self.tmp.name,'case.db');shutil.copyfile(self.database,app.DB)
 def user(self,c,role='superadmin'):
  return dict(c.execute('SELECT id,tenant,email,role FROM users WHERE email=?',(role+'.primary@demo.academy.example',)).fetchone())
 def test_all_roles_and_groups_authenticate(self):
  with app.connect() as c:
   rows=c.execute('SELECT * FROM users JOIN demo_users ON demo_users.user=users.id').fetchall();self.assertEqual(49,len(rows))
   for u in rows:self.assertTrue(app.verify(PASSWORD,u['password']))
 def test_seed_is_idempotent(self):
  seed()
  with app.connect() as c:self.assertEqual(49,c.execute('SELECT count(*) FROM demo_users').fetchone()[0]);self.assertEqual(7,c.execute('SELECT count(*) FROM demo_tenants').fetchone()[0])
 def test_demo_superadmin_cannot_see_live_tenants(self):
  with app.connect() as c:
   c.execute("INSERT INTO tenants(name,level) VALUES('Private institution','primary')")
   rows=app.api('/api/tenants','GET',{},self.user(c),c)
   self.assertEqual(7,len(rows));self.assertTrue(all(r['name'].startswith('DEMO') for r in rows))
 def test_admin_can_create_and_read_sample_records(self):
  with app.connect() as c:
   u=self.user(c,'admin');rows=app.api('/api/records/students','POST',{'name':'New fictional pupil'},u,c)
   self.assertTrue(any(r['name']=='New fictional pupil' for r in rows))
 def test_superadmin_can_create_demo_tenant_but_not_enter_live(self):
  with app.connect() as c:
   u=self.user(c);rows=app.api('/api/tenants','POST',{'name':'Sandbox','level':'primary'},u,c)
   tid=next(r['id'] for r in rows if 'Sandbox' in r['name']);self.assertTrue(c.execute('SELECT 1 FROM demo_tenants WHERE tenant=?',(tid,)).fetchone())
   app.api('/api/switch-tenant','POST',{'tenant':tid},u,c)
   live=c.execute("INSERT INTO tenants(name,level) VALUES('Live','primary')").lastrowid
   with self.assertRaises(PermissionError):app.api('/api/switch-tenant','POST',{'tenant':live},u,c)
 def test_created_users_cannot_escape_demo(self):
  with app.connect() as c:
   u=self.user(c,'admin');data={'email':'fictional@demo.academy.example','password':'TestingDemo123!','role':'teacher'}
   app.api('/api/users','POST',data,u,c);new=dict(c.execute('SELECT * FROM users WHERE email=?',(data['email'],)).fetchone())
   self.assertTrue(app.api('/api/me','GET',{},new,c)['is_demo'])
   data['email']='real@example.com'
   with self.assertRaises(ValueError):app.api('/api/users','POST',data,u,c)
 def test_student_can_submit_exam_and_reset(self):
  with app.connect() as c:
   u=self.user(c,'student');exam=c.execute('SELECT id FROM exams WHERE tenant=?',(u['tenant'],)).fetchone()[0]
   a=app.api('/api/attempt','POST',{'exam':exam,'answers':{'0':'Practice regularly'},'submit':True},u,c)
   self.assertTrue(a['submitted']);self.assertEqual(1,a['score'])
   app.api('/api/demo-reset-attempts','POST',{},u,c)
   self.assertFalse(app.api('/api/attempt','POST',{'exam':exam},u,c)['submitted'])
 def test_role_permissions_and_live_payments_stay_blocked(self):
  with app.connect() as c:
   for role in ROLES:
    u=self.user(c,role)
    with self.assertRaises(PermissionError):app.api('/api/payment','POST',{},u,c)
   u=self.user(c,'student')
   with self.assertRaises(PermissionError):app.api('/api/records/staff','POST',{},u,c)
   app.api('/api/records/submissions','POST',{'assignment':'Demo','answer':'My sample submission'},u,c)
 def test_demo_clock_and_payroll(self):
  with app.connect() as c:
   admin=self.user(c,'admin');staff=self.user(c,'staff');accountant=self.user(c,'accountant')
   app.api('/api/settings','POST',{'geofence':{'lat':0,'lon':0,'radius':100}},admin,c)
   for action in ['in','out']:app.api('/api/clock','POST',{'lat':0,'lon':0,'accuracy':5,'action':action},staff,c)
   rows=app.api('/api/payroll','POST',{'start':1,'end':9999999999},accountant,c);self.assertEqual(1,len(rows))
 def test_demo_records_scoped_and_identified(self):
  with app.connect() as c:
   u=self.user(c,'admin');self.assertTrue(app.api('/api/me','GET',{},u,c)['is_demo'])
   rows=app.api('/api/records/students','GET',{},u,c);self.assertEqual('Alex Demo',rows[0]['name'])
 def test_role_matrix_blocks_unassigned_modules_and_features(self):
  endpoints={'exams':'/api/exams','clock':'/api/clock','payroll':'/api/payroll','users':'/api/users','settings':'/api/settings','audit':'/api/audit','institutions':'/api/tenants','report':'/api/report'}
  with app.connect() as c:
   for role in ROLES:
    u=self.user(c,role);perms=app.permissions(role)
    self.assertEqual(perms,app.api('/api/me','GET',{},u,c)['permissions'])
    for module in app.MODULES:
     if module not in perms['read']:
      with self.assertRaises(PermissionError,msg=role+' read '+module):app.api('/api/records/'+module,'GET',{},u,c)
     if module not in perms['write']:
      with self.assertRaises(PermissionError,msg=role+' write '+module):app.api('/api/records/'+module,'POST',{},u,c)
    for feature,path in endpoints.items():
     if feature not in perms['features']:
      with self.assertRaises(PermissionError,msg=role+' '+feature):app.api(path,'GET',{},u,c)
 def test_staff_leave_records_are_personal(self):
  with app.connect() as c:
   teacher=self.user(c,'teacher');staff=self.user(c,'staff')
   for u in [teacher,staff]:app.api('/api/records/leave','POST',{'staff':u['email'],'reason':'Sample personal leave'},u,c)
   rows=app.api('/api/records/leave','GET',{},staff,c);self.assertEqual(1,len(rows));self.assertEqual(staff['email'],rows[0]['staff'])
 def test_seed_restores_canonical_demo_roles(self):
  with app.connect() as c:c.execute("UPDATE users SET role='admin' WHERE email='student.primary@demo.academy.example'")
  seed()
  with app.connect() as c:self.assertEqual('student',self.user(c,'student')['role'])
