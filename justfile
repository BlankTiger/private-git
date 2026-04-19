run:
    #!/usr/bin/bash
    source .env
    sudo docker-compose up -d
    cp cloudflared/config.yml ~/.cloudflared/config.yml
    cp cloudflared/ssh-forgejo.yml ~/.cloudflared/ssh-forgejo.yml
    cloudflared tunnel run forgejo & cloudflared tunnel run ssh-forgejo &
