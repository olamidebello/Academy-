import unittest,tempfile,os,json,time
import app
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); app.DB=os.path.join(self.tmp.name,'test.db'); app.init(); self.c=app.connect()
  self.c.execute("INSERT INTO tenants VALUES(1,'School A','primary','{}')"); self.c.execute("INSERT INTO tenants VALUES(2,'School B','college','{}')")
  self.u=dict(id=1,tenant=1,role='admin'); self.student=dict(id=2,tenant=1,role='student')
 def tearDown(self):self.c.close();self.tmp.cleanup()
 def call(self,p,d=None,u=None):return app.api('/api/'+p,'POST' if d is not None else 'GET',d or {},u or self.u,self.c)
 def test_isolation(self):
  self.call('records/students',dict(name='Alice')); self.assertEqual([],self.call('records/students',u=dict(id=3,tenant=2,role='admin')))
 def test_permissions(self):
  with self.assertRaises(PermissionError):self.call('records/staff',u=self.student)
 def test_weighted_grades(self):
  for score,weight in [(80,40),(60,60)]: self.call('records/grades',dict(student='Alice',course='Math',assessment='exam',score=score,maximum=100,weight=weight))
  self.assertEqual(68,self.call('report')[0]['percentage'])
 def test_exam_answers_hidden_and_immutable(self):
  self.call('exams',dict(title='Math',duration=10,published=True,questions=[dict(type='choice',prompt='2+2',options=['3','4'],answer='4',points=5)]))
  a=self.call('attempt',dict(exam=1),self.student); self.assertNotIn('answer',a['questions'][0]); self.assertEqual(5,self.call('attempt',dict(exam=1,answers={'0':'4'},submit=True),self.student)['score']); self.assertEqual(5,self.call('attempt',dict(exam=1,answers={'0':'3'}),self.student)['score'])
 def test_geofence(self):
  self.call('settings',{'geofence':{'lat':0,'lon':0,'radius':100}})
  with self.assertRaises(ValueError):self.call('clock',dict(lat=1,lon=1,accuracy=10,action='in'))
  self.call('clock',dict(lat=0,lon=0,accuracy=10,action='in'))
  with self.assertRaises(ValueError):self.call('clock',dict(lat=0,lon=0,accuracy=10,action='in'))
 def test_password(self):
  h=app.password('strong password');self.assertTrue(app.verify('strong password',h));self.assertFalse(app.verify('wrong',h))
 def test_overlapping_payroll(self):
  self.call('payroll',dict(start=100,end=200))
  with self.assertRaises(ValueError):self.call('payroll',dict(start=150,end=250))
if __name__=='__main__': unittest.main()
