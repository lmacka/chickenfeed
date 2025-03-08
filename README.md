# 🐔 Chicken Feed

<div align="center">
  <img src="docs/chickenfeed.webp" alt="Chicken Feed" width="400"/>
  <p><em>Live demonstration available at <a href="https://chook.cam">chook.cam</a></em></p>
  <p>
    <a href="https://github.com/lmacka/coopi">Related Project: Coopi (Automated Coop Controller)</a>
  </p>
</div>

## 📋 Overview

**Chicken Feed** is a high-performance video streaming proxy solution designed to overcome the bandwidth limitations of residential networks while broadcasting live video feeds to multiple concurrent viewers.

This project showcases expertise in:
- Distributed systems architecture
- Media streaming protocols and optimization
- Containerization and cloud deployment
- Network security and access control

## 🔍 Technical Challenge

The fundamental problem addressed by this project is the bandwidth bottleneck that occurs when multiple viewers attempt to access a video stream hosted on a residential internet connection:

- **Limited Upload Bandwidth**: Typical home connections have restricted upload capacity
- **Connection Multiplication**: Each viewer requires a separate video stream
- **Quality Degradation**: As viewer count increases, all streams suffer from buffering and quality issues

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────┐     ┌─────────────────┐
│                 │     │                                     │     │                 │
│  Local Network  │     │           Cloud Server              │     │    Viewers      │
│                 │     │                                     │     │                 │
│  ┌───────────┐  │     │  ┌───────────┐     ┌────────────┐  │     │  ┌───────────┐  │
│  │           │  │     │  │           │     │            │  │     │  │ Browser 1 │  │
│  │  IP Cam   │──┼─────┼─▶│ MediaMTX  │────▶│  Static    │  │     │  │           │  │
│  │  (RTSP)   │  │     │  │ (Docker)  │     │  Web Server│──┼─────┼─▶│ HLS.js    │  │
│  │           │  │     │  │           │     │  (Nginx)   │  │     │  │           │  │
│  └───────────┘  │     │  └───────────┘     └────────────┘  │     │  └───────────┘  │
│                 │     │        │                  │        │     │        ▲        │
│                 │     │        │                  │        │     │        │        │
│                 │     │        ▼                  ▼        │     │        │        │
│                 │     │  ┌────────────────────────────┐    │     │  ┌───────────┐  │
│  Single RTSP    │     │  │                            │    │     │  │ Browser 2 │  │
│  Connection     │     │  │  Transcoded HLS Segments   │    │     │  │           │  │
│                 │     │  │                            │    │     │  │ HLS.js    │  │
│                 │     │  └────────────────────────────┘    │     │  │           │  │
│                 │     │                  │                 │     │  └───────────┘  │
└─────────────────┘     └─────────────────┼─────────────────┘     │        ▲        │
                                          │                        │        │        │
                                          │                        │        │        │
                                          │                        │  ┌───────────┐  │
                                          │                        │  │ Browser N │  │
                                          └────────────────────────┼─▶│           │  │
                                                                   │  │ HLS.js    │  │
                                                                   │  │           │  │
                                                                   │  └───────────┘  │
                                                                   │                 │
                                                                   └─────────────────┘
```

### System Components

#### 1. Video Source Layer
- **RTSP-capable camera** on a local network (TP-Link Tapo C220)
- **Secured access** through IP-restricted port forwarding
- Raw RTSP stream exposed only to the proxy server

#### 2. Proxy & Transcoding Layer
- **Cloud-hosted server** with high-bandwidth connectivity
- **Docker containerization** for deployment and scaling
- **MediaMTX** for RTSP ingestion and protocol conversion
- **Transcoding** from RTSP to HTTP Live Streaming (HLS)
- Single persistent connection to the source camera

#### 3. Distribution Layer
- **Lightweight static HTML/JS frontend**
- **HLS.js** for client-side stream rendering
- **Horizontally scalable** to support numerous concurrent viewers
- Bandwidth requirements offloaded to cloud infrastructure

## 💡 Technical Implementation

### Key Technologies
- **Docker & Docker Compose**: Containerized deployment for consistency
- **MediaMTX**: High-performance RTSP server with protocol conversion
- **HLS (HTTP Live Streaming)**: Adaptive bitrate streaming protocol
- **RTSP (Real Time Streaming Protocol)**: Camera-native streaming format
- **Nginx**: Static content serving and optional caching
- **Network Security**: IP-based access control and traffic filtering

### Performance Optimizations
- **Single Upstream Connection**: Minimizes home bandwidth usage
- **Segment Caching**: Reduces redundant processing for multiple viewers
- **Adaptive Bitrate**: Adjusts quality based on viewer's connection
- **Cloud Scaling**: Handles viewer load independent of source connection

## 🔒 Security Considerations

- **Source Isolation**: Camera RTSP stream accessible only to proxy server
- **IP Restriction**: Firewall rules limit access to authorized servers
- **Protocol Conversion**: Removes direct access to source network
- **Content Separation**: Designed for non-sensitive content broadcasting

## 🚀 Technical Benefits

- **Bandwidth Optimization**: Single upstream connection regardless of viewer count
- **Format Conversion**: Transforms camera-native RTSP to web-friendly HLS
- **Scalability**: Cloud infrastructure handles viewer scaling, not home network
- **Containerization**: Docker-based deployment for consistency and portability
- **Minimal Client Requirements**: Works in any modern browser without plugins

---

<div align="center">
  <p><strong>Chicken Feed</strong> demonstrates practical application of streaming media protocols, containerization, proxy architecture, and bandwidth optimization techniques.</p>
</div>

