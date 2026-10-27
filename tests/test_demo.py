import unittest,tempfile,os,json
import app
from demo_seed import seed,GROUPS,ROLES,PASSWORD
class DemoTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.database=os.path.join(cls.tmp.name,'demo.db');app.DB=cls.database;seed()
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):app.DB=self.database
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
 def test_demo_writes_and_exam_attempts_blocked(self):
  with app.connect() as c:
   u=self.user(c)
   for path in ['/api/tenants','/api/users','/api/settings','/api/switch-tenant','/api/payroll','/api/records/students','/api/clock']:
    with self.assertRaises(PermissionError):app.api(path,'POST',{},u,c)
   with self.assertRaises(PermissionError):app.api('/api/attempt','GET',{'exam':1},self.user(c,'student'),c)
 def test_demo_records_scoped_and_identified(self):
  with app.connect() as c:
   u=self.user(c,'admin');self.assertTrue(app.api('/api/me','GET',{},u,c)['is_demo'])
   rows=app.api('/api/records/students','GET',{},u,c);self.assertEqual('Alex Demo',rows[0]['name'])
