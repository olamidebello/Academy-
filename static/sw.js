// No caching of account, student, exam or payroll data.
self.addEventListener('install',event=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{if(event.request.mode==='navigate')event.respondWith(fetch(event.request).catch(()=>new Response('<!doctype html><meta name="viewport" content="width=device-width"><h1>Academy is offline</h1><p>Reconnect to access your institution. Records and exam submissions require an internet connection.</p>',{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store'}})))});
