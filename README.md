# Chicken Feed 🐔

A demo of this in action can be seen at https://chook.cam
Note that this is still very much in alpha stages and might be turned off or broken.

For other cool chook stuff, check out my door controller [here](https://github.com/lmacka/coopi).

## Problem
Let's say you have a bunch of baby chickens and for some reason you've put a camera in their brooder.  You want to world to see your chooks, but you've only got a mediocre residential internet connection.  More than a couple of viewers and your fancy video stream will start buffering.

## Solution
We use an RTSP proxy running on a cloud server/VM somewhere to ingest your video feed, convert it to a more user-friendly format (HLS for now) and publishe a very simple static HTML page that reads the proxied feed.  This means you can have as many viewers as your public server can handle, but there's only a single connection to your crappy eBay camera on your underwhelming home internet connection.

## Assumptions
 - You have a basic camera on your home network that can publish an RTSP feed (I'm using a cheap [TP-Link Tapo C220](https://www.tp-link.com/au/home-networking/cloud-camera/tapo-c220/))
 - You have a router capable of port forwarding
 - You have a server somewhere out there with decent bandwidth and a public IP
 - You're not publishing private or confidential videos (this isn't exactly secure)

## Quickstart
1.  Make your camera available to your public server.  The quick & dirty way to do this is to use NAT on your router to forward incoming TCP/554 from your server's IP to TCP/554 on your camera's local IP.  Make sure you limit this to ONLY your server's IP address as the most basic of security measures, lest you inadvertently publish your raw RTSP feed.
2.  Log into your server and clone this repo
3.  Edit `mediamtx.yml` and update the source.  Eg:

    `rtsp://tapocam:ChickenL0ve@<your home IP/dyndns>:554/stream1`

4. Run `docker compose up -d`
5. Visit http://yourserver:24665 and enjoy a public live stream of your chickens 🐔

