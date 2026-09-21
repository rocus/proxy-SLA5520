This repository describes a proxy for old radio streamers. 

I have several Philips SLA5520 radio streamers. They are quite old and in some respects are a bit obsolete:

- Wifi has only PSK WPA
- Only http streaming
- UPnP based (I consider that a plus)
 
With an old router the first point maybe not so serious. 
HTTP only is a real problem.
UPnP did not really get widely adopted.

The HTTP only streaming I solved with a proxy program. Many radio stations are HTTPS based (some don't even offer a http stream). The SLA5520 does not support HTTPS (or support old vesions of TLS) and immediately discards a choice for the stream. If you let the SLA5520 ask for a http stream it mostly works fine. Fortunately the SLA5520 has an option for a proxy (address and port). The proxy.py program I made expects a http stream and when that stream does not work it makes a https connection with the same url.

So if you have a radio stream like https:/.......mp3 you must give the SLA5520 the stream http:......mp3 and it makes a connection with https:/.....mp3 and translates the stream to an http stream.

The program (proxy.py) needs only one parameter the port nr. 

It is best to make a proxy.service so that this program always runs. You can inspect the output of the program with journalctl -u  proxy.service: there you see if connection succeeds and possible redirections. 
  
