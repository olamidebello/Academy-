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
