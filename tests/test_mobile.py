import unittest,io,json,tempfile,sqlite3,pathlib
import app
from scripts.register_store import register
class MobileTests(unittest.TestCase):
 def get(self,path):
  out=[];body=b''.join(app.application({'PATH_INFO':path,'REQUEST_METHOD':'GET','wsgi.input':io.BytesIO()},lambda s,h:out.extend([s,dict(h)])))
  self.assertEqual('200 OK',out[0]);return out[1],body
 def test_install_manifest_and_icons(self):
  h,b=self.get('/install');self.assertIn(b'Install Academy',b)
  h,b=self.get('/manifest.webmanifest');manifest=json.loads(b);self.assertEqual('standalone',manifest['display']);self.assertEqual('/',manifest['scope'])
  for icon in manifest['icons']:
   h,b=self.get(icon['src']);self.assertEqual('image/png',h['Content-Type']);self.assertTrue(b.startswith(b'\x89PNG'))
 def test_worker_does_not_cache_private_data(self):
  h,b=self.get('/sw.js');self.assertEqual('/',h['Service-Worker-Allowed']);self.assertNotIn(b'caches.open',b);self.assertNotIn(b'cache.put',b)
 def test_listing_update_preserves_other_apps_and_visibility(self):
  with tempfile.TemporaryDirectory() as t:
   db=pathlib.Path(t)/'store.db'
   with sqlite3.connect(db) as c:
    c.execute('CREATE TABLE hosted_apps(domain TEXT PRIMARY KEY,metadata TEXT,visible INTEGER,updated INTEGER)');c.execute("INSERT INTO hosted_apps VALUES('other.example','{}',1,0)")
   listing=pathlib.Path(__file__).resolve().parents[1]/'mobile/store-listing.json';backup=register(db,listing);self.assertTrue(pathlib.Path(backup).exists())
   with sqlite3.connect(db) as c:c.execute("UPDATE hosted_apps SET visible=0 WHERE domain='academy.africandroid.world'")
   register(db,listing)
   with sqlite3.connect(db) as c:
    self.assertEqual(2,c.execute('SELECT count(*) FROM hosted_apps').fetchone()[0]);self.assertEqual(0,c.execute("SELECT visible FROM hosted_apps WHERE domain='academy.africandroid.world'").fetchone()[0])
 def test_missing_store_database_is_not_created(self):
  with tempfile.TemporaryDirectory() as t:
   db=pathlib.Path(t)/'absent.db'
   with self.assertRaises(ValueError):register(db,'unused')
   self.assertFalse(db.exists())
