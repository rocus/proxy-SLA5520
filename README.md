This repository describes a proxy for old radio streamers. 

I have several Philips SLA5520 radio streamers. They are not bound to a specific vendor (the Philips radio backend was clunky from the beginning). They are quite old (more than 20 years) and in some respects are a bit obsolete:

- Wifi has only WPA WEP
- Only WMA and MP3
- Only HTTP streaming
- UPnP based (I consider that a plus)
 
With an old router the first point may be not so serious. 
Fortunately mp3 is still the dominant audio stream format.
HTTP only is a real problem.
UPnP did not really get widely adopted. But because of UPnP you can still use it as an mp3 player and radio station player. See also my ushare repository.

The HTTP only streaming I solved with a proxy program. Many radio stations are HTTPS based (some don't offer a HTTP stream), I don't know why that is (I suspect it is to protect our kids). The SLA5520 does not support HTTPS (or supports old vesions of TLS) and immediately discards a choice for a HTTPS stream. If you let the SLA5520 ask for a HTTP stream it mostly works fine. Fortunately the SLA5520 has an option for a proxy (address and port). The proxy.py program I made expects a HTTP stream and when that stream does not work it makes a HTTPS connection with the same url and possibly follows some redirects.

So if you have a radio stream like https:/.......mp3 you must give the SLA5520 the stream http:......mp3 and the proxy makes a connection with https:/.....mp3 and translates the stream to an http stream.

The program (proxy.py) needs only one parameter: the port nr on which it listens. At the moment that is constant (8080) in the program.

It is best to make a proxy.service so that the program always runs. You can inspect the output of the program with journalctl -u  proxy.service: there you see if the connection succeeds and if there are possible redirections. 

Maybe I will make a C version of this program so that it can run on a router (with openwrt): in this test phase it runs well on a PC with Python3.


  
