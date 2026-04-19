systemd:
    mkdir -pv ~/.config/systemd/user/
    cp private-git.service ~/.config/systemd/user/private-git.service
    loginctl enable-linger $USER
    systemctl --user daemon-reload
    systemctl --user enable --now private-git.service

run:
    #!/usr/bin/bash
    source .env
    sudo docker-compose up -d
    cp cloudflared/config.yml ~/.cloudflared/config.yml
    cp cloudflared/ssh-forgejo.yml ~/.cloudflared/ssh-forgejo.yml
    cloudflared tunnel run forgejo & cloudflared tunnel run ssh-forgejo &
