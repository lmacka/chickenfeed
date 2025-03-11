#  <img src="docs/chickenfeed.webp" alt="Chicken Feed" width="40"/> Chicken Feed

## A Smart Chicken Coop Monitoring System
Interactive chicken video stream; who woulda thunk it?

[![Live Demo](https://img.shields.io/badge/Live_Demo-chook.cam-ff9966?style=for-the-badge&logo=internetexplorer&logoColor=white)](https://chook.cam)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-a8d1ff?style=for-the-badge&logo=github&logoColor=black)](https://github.com/lmacka/chickenfeed)
[![Related](https://img.shields.io/badge/Related-Coopi_Controller-b3e6b3?style=for-the-badge&logo=github&logoColor=black)](https://github.com/lmacka/coopi)

![Docker](https://img.shields.io/badge/Docker-Powered-d8c1ff?style=flat-square&logo=docker&logoColor=white)
![Tailscale](https://img.shields.io/badge/Tailscale-Secured-ffb3d1?style=flat-square&logo=tailscale&logoColor=white)
![Node.js](https://img.shields.io/badge/Node.js-Powered-b3e6b3?style=flat-square&logo=node.js&logoColor=white)
![HLS](https://img.shields.io/badge/HLS-Streaming-ffd9b3?style=flat-square&logo=videojs&logoColor=white)
![IoT](https://img.shields.io/badge/IoT-Hardware-c1f0d9?style=flat-square&logo=raspberrypi&logoColor=white)

## 📋 What's This?

This is my little project that lets me keep an eye on my chickens from anywhere. It streams video from my backyard to the web and even lets visitors interact with the setup remotely. Pretty neat, right?

Under the hood, it's got some cool tech that I've put together to solve a bunch of interesting problems:

- Streaming video from a home network without killing my bandwidth
- Connecting home hardware to the internet (safely!)
- Controlling physical stuff remotely
- Making it all work together seamlessly

## 🏗️ How It Works

```mermaid
---
config:
  layout: dagre
  look: neo
---
flowchart TD
 subgraph Users["Internet Users"]
    direction LR
        Viewers["Web Browser"]
  end
 subgraph VPS["VPS (docker containers)"]
    direction LR
        VPSTailscale["Tailscale Client"]
        MediaMTX["MediaMTX (RTSP→HLS)"]
        SWAG["SWAG (Nginx + SSL)"]
        ChickyControl["Chicky Control Server"]
  end
 subgraph Hardware["Hardware Controls"]
    direction LR
        Servos["Servo Motors"]
        Lights["Lights"]
  end
 subgraph HomeNet["Home Network"]
    direction LR
        Router["Router with Tailscale"]
        Camera["IP Camera (RTSP)"]
        RaspPi["Raspberry Pi (Chicky)"]
        Hardware
  end
    RaspPi --> Hardware
    Users -- HLS stream (https) --> SWAG
    SWAG --> MediaMTX & ChickyControl
    MediaMTX --> VPSTailscale
    VPSTailscale --> Router & Router
    Router --> Camera & RaspPi
    Users -- HTML (https) --> SWAG
    Users -- Websocket (wss) --> SWAG
    ChickyControl --> VPSTailscale
     Viewers:::viewerNode
     VPSTailscale:::tailscaleNode
     MediaMTX:::mediaNode
     SWAG:::swagNode
     ChickyControl:::controlNode
     Servos:::hardwareNode
     Lights:::hardwareNode
     Router:::routerNode
     Camera:::cameraNode
     RaspPi:::raspberryNode
    classDef routerNode fill:#a8d1ff,stroke:#3a87ff,stroke-width:2px,color:#333,font-weight:bold
    classDef cameraNode fill:#ffccb3,stroke:#ff8c66,stroke-width:2px,color:#333
    classDef raspberryNode fill:#b3e6b3,stroke:#66cc66,stroke-width:2px,color:#333
    classDef hardwareNode fill:#c1f0d9,stroke:#7ad3a7,stroke-width:1px,color:#333
    classDef tailscaleNode fill:#d8c1ff,stroke:#b38aff,stroke-width:2px,color:#333,font-weight:bold
    classDef mediaNode fill:#ffd9b3,stroke:#ffb366,stroke-width:2px,color:#333
    classDef swagNode fill:#ffb3d1,stroke:#ff80ab,stroke-width:2px,color:#333
    classDef controlNode fill:#b3e6f2,stroke:#66ccdf,stroke-width:2px,color:#333
    classDef viewerNode fill:#d9d9d9,stroke:#a6a6a6,stroke-width:2px,color:#333
    style VPSTailscale fill:#d8c1ff
    style ChickyControl fill:#b3d1ff
    style Router fill:#a8d1ff
    linkStyle 0 stroke:#2962FF,fill:none
    linkStyle 1 stroke:#FF6D00,fill:none
    linkStyle 2 stroke:#FF6D00,fill:none
    linkStyle 3 stroke:#2962FF,fill:none
    linkStyle 4 stroke:#FF6D00,fill:none
    linkStyle 5 stroke:#FF6D00,fill:none
    linkStyle 6 stroke:#2962FF,fill:none
    linkStyle 7 stroke:#FF6D00,fill:none
    linkStyle 8 stroke:#2962FF,fill:none
    linkStyle 10 stroke:#2962FF,fill:none
    linkStyle 11 stroke:#2962FF,fill:none

```

## 🧩 The Pieces

### At Home
- A **Raspberry Pi** running Node.js to control everything
- An **IP Camera** (TP-Link Tapo C220) that can pan and tilt
- Some **servo motors** hooked up to a feed dispenser
- **Tailscale** running on the router for secure networking

### In The Cloud
- A VPS running **Docker** containers for all the services
- **MediaMTX** to handle the video streaming magic
- **SWAG** (Nginx with SSL) to serve up the web interface
- A **Node.js server** that handles all the control commands
- **Tailscale** to create a secure tunnel back to my home network

## 💡 Cool Technical Bits

- The whole setup uses just **one connection** from my home network, no matter how many people are watching
- **HLS streaming** means it works in any modern browser without plugins
- **Tailscale** creates an encrypted network between my home and the cloud server
- Everything runs in **Docker containers** for easy deployment and updates
- The **camera controls** work in real-time with minimal lag

## 🔒 Keeping Things Secure

```mermaid
---
config:
  layout: dagre
  look: neo
---
flowchart LR
    User["Internet User"]
    SSL["SSL Termination"]
    Auth["Auth Layer"]
    Tailscale["Tailscale Network"]
    Home["Home Network"]
    
    User -->|HTTPS| SSL
    SSL -->|HTTP| Auth
    Auth -->|If Authorized| Tailscale
    Tailscale -->|Encrypted| Home
    
    User:::viewerNode
    SSL:::swagNode
    Auth:::controlNode
    Tailscale:::tailscaleNode
    Home:::routerNode
    
    classDef routerNode fill:#a8d1ff,stroke:#3a87ff,stroke-width:2px,color:#333,font-weight:bold
    classDef tailscaleNode fill:#d8c1ff,stroke:#b38aff,stroke-width:2px,color:#333,font-weight:bold
    classDef swagNode fill:#ffb3d1,stroke:#ff80ab,stroke-width:2px,color:#333
    classDef controlNode fill:#b3e6f2,stroke:#66ccdf,stroke-width:2px,color:#333
    classDef viewerNode fill:#d9d9d9,stroke:#a6a6a6,stroke-width:2px,color:#333
    
    linkStyle 0 stroke:#FF6D00,fill:none
    linkStyle 1 stroke:#FF6D00,fill:none
    linkStyle 2 stroke:#2962FF,fill:none
    linkStyle 3 stroke:#2962FF,fill:none
```

I've set things up so that:
- All traffic is encrypted (HTTPS and Tailscale)
- My home devices aren't directly exposed to the internet
- You need special tokens to control anything
- Each component only has the permissions it absolutely needs

## 🚀 Why This Works Well

- Handles lots of viewers without breaking my home internet
- Converts camera video to a format that works well on the web
- Creates a secure tunnel between my home and the cloud
- Lets people interact with my chicken setup (which is just fun)
- Works on pretty much any device with a modern browser

## 📝 Todo List

- [ ] Add time restrictions around control interactions so the chooks get a good night's sleep
- [ ] Implement rate limiting on the API side of things
- [ ] Improve cooldown handling for controls
- [ ] Fix current viewer stats (currently broken)
- [ ] Redesign control panel for better user experience
