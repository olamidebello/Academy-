import unittest
from scripts.repair_routing import rename_conflicts
class RoutingTests(unittest.TestCase):
 def test_shared_names_preserved(self):
  s='server { server_name academy.africandroid.world sprintforge.example; location / { proxy_pass http://app; } }'
  out,n=rename_conflicts(s,'academy.africandroid.world');self.assertEqual(1,n);self.assertIn('sprintforge.example',out);self.assertNotIn('academy.africandroid.world',out);self.assertIn('proxy_pass http://app',out)
 def test_single_name_disabled(self):
  out,n=rename_conflicts('server_name "academy.africandroid.world";','academy.africandroid.world');self.assertIn('.invalid',out);self.assertEqual(1,n)
 def test_other_domains_comments_and_wildcard_preserved(self):
  s='# server_name academy.africandroid.world;\nserver_name *.africandroid.world sprintforge.example;'
  self.assertEqual((s,0),rename_conflicts(s,'academy.africandroid.world'))
 def test_idempotent(self):
  out,n=rename_conflicts('server_name academy.africandroid.world;','academy.africandroid.world');self.assertEqual((out,0),rename_conflicts(out,'academy.africandroid.world'))

class CertificateTests(unittest.TestCase):
 def check_certificate(self,results):
  from scripts.repair_routing import certificate_usable
  from unittest.mock import Mock,patch
  path=Mock();path.exists.return_value=True
  with patch('scripts.repair_routing.subprocess.run',side_effect=results):
   return certificate_usable(path,path,'academy.africandroid.world')
 def test_rejects_wrong_hostname(self):
  from subprocess import CompletedProcess as R
  self.assertFalse(self.check_certificate([R([],0),R([],1)]))
 def test_rejects_untrusted_chain(self):
  from subprocess import CompletedProcess as R
  self.assertFalse(self.check_certificate([R([],0),R([],0),R([],1)]))
 def test_rejects_mismatched_private_key(self):
  from subprocess import CompletedProcess as R
  self.assertFalse(self.check_certificate([R([],0),R([],0),R([],0),R([],0,b'one'),R([],0,b'two')]))
 def test_accepts_valid_chain_hostname_and_key(self):
  from subprocess import CompletedProcess as R
  self.assertTrue(self.check_certificate([R([],0),R([],0),R([],0),R([],0,b'one'),R([],0,b'one')]))

class ActivationTests(unittest.TestCase):
 def test_explicit_listeners_are_mirrored(self):
  from scripts.repair_routing import listen_directives
  dump='server { listen 154.16.170.86:80; listen 127.0.0.1:80; listen [::1]:443 ssl; } # listen 1.2.3.4:80;'
  http=listen_directives(dump,80);self.assertIn('listen 154.16.170.86:80;',http);self.assertIn('listen 127.0.0.1:80;',http);self.assertNotIn('1.2.3.4',http)
  self.assertIn('listen [::1]:443 ssl;',listen_directives(dump,443))
 def test_reload_grace_period(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  from scripts.repair_routing import verify_page
  with tempfile.TemporaryDirectory() as temp, patch('scripts.repair_routing.run',side_effect=['<title>SprintForge</title>','<title>Academy</title>']),patch('scripts.repair_routing.time.sleep') as sleep:
   self.assertIn('Academy',verify_page('http://academy.africandroid.world/','academy.africandroid.world',80,Path(temp),tries=2));sleep.assert_called_once()
 def test_failure_saves_response(self):
  import tempfile
  from pathlib import Path
  from unittest.mock import patch
  from scripts.repair_routing import verify_page
  with tempfile.TemporaryDirectory() as temp,patch('scripts.repair_routing.run',return_value='<title>Moved</title>'):
   with self.assertRaisesRegex(RuntimeError,'Unexpected page title: Moved'):verify_page('http://academy.africandroid.world/','academy.africandroid.world',80,Path(temp),tries=1)
   self.assertTrue((Path(temp)/'http-80-body.html').exists())
