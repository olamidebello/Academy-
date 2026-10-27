import unittest,tempfile,os,io,json
import app
class SignupTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();app.DB=os.path.join(self.tmp.name,'test.db');app.init();app.LOGIN.clear()
  self.data=dict(institution='Test School',level='primary',email='Admin@school.example',password='long-password-123',confirm_password='long-password-123',accept_terms='on')
 def tearDown(self):self.tmp.cleanup()
 def request(self,path,data=None):
  payload=json.dumps(data).encode() if data else b'';result=[]
  body=b''.join(app.application(dict(PATH_INFO=path,REQUEST_METHOD='POST' if data else 'GET',CONTENT_LENGTH=str(len(payload)),HTTP_X_ACADEMY_REQUEST='1',REMOTE_ADDR='test',**{'wsgi.input':io.BytesIO(payload)}),lambda status,headers:result.extend([status,headers])))
  return result[0],body,result[1]
 def test_signup_login_and_policy_acceptance(self):
  self.assertEqual('200 OK',self.request('/api/signup',self.data)[0])
  with app.connect() as c:
   u=c.execute('SELECT * FROM users').fetchone();self.assertEqual('admin',u['role']);self.assertEqual('admin@school.example',u['email']);self.assertNotEqual(self.data['password'],u['password']);self.assertEqual(1,c.execute('SELECT count(*) FROM legal_acceptances').fetchone()[0])
  self.assertEqual('200 OK',self.request('/api/login',dict(email=self.data['email'],password=self.data['password']))[0])
 def test_duplicate_does_not_create_tenant(self):
  self.request('/api/signup',self.data);self.assertEqual('400 Bad Request',self.request('/api/signup',self.data)[0])
  with app.connect() as c:self.assertEqual(1,c.execute('SELECT count(*) FROM tenants').fetchone()[0])
 def test_terms_required(self):
  self.data['accept_terms']=False;self.assertEqual('400 Bad Request',self.request('/api/signup',self.data)[0])
 def test_password_confirmation(self):
  self.data['confirm_password']='wrong';self.assertEqual('400 Bad Request',self.request('/api/signup',self.data)[0])
 def test_public_pages(self):
  for page in ['/signup','/terms','/privacy','/copyright']:
   status,body,headers=self.request(page);self.assertEqual('200 OK',status);self.assertIn(b'Olamide Olatayo Bello Corporation',body)
