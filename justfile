systemd:
    sudo cp private-git.service /etc/systemd/system/private-git.service
    sudo systemctl daemon-reload
    sudo systemctl enable --now private-git.service

run:
    #!/usr/bin/bash
    (crontab -l 2>/dev/null | grep -v 'plugin-sync.sh'; echo "0 0,12 * * * source /home/blanktiger/private-git/.env && /home/blanktiger/private-git/scripts/plugin-sync.sh >> /home/blanktiger/logs/mirror-sync.log 2>&1") | crontab -

    source .env
    sudo docker-compose up -d
    cp cloudflared/config.yml ~/.cloudflared/config.yml
    cp cloudflared/ssh-forgejo.yml ~/.cloudflared/ssh-forgejo.yml
    cloudflared tunnel run forgejo & cloudflared tunnel run ssh-forgejo &
