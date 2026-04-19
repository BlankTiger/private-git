#!/usr/bin/bash

FORGEJO_URL="https://git.maciejurban.dev"
FORGEJO_OWNER="BlankTiger"
container=$(sudo docker ps -qf "name=forgejo")

repos=$(git --git-dir=forgejo/git/repositories/blanktiger/homecfg.git grep -rhoP '["'"'"'][a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+["'"'"']' HEAD | grep -oP '[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+')
repos+="
ghostty-org/ghostty
neovim/neovim
hyprwm/Hyprland"
my_repos=$(gh repo list --limit 1000 | cut -f1)
repos+="
$my_repos"
repos=$(echo "$repos" | sort -u)

while IFS=/ read -r user repo; do
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "Authorization: token $FORGEJO_TOKEN" \
        "$FORGEJO_URL/api/v1/repos/$user/$repo")

    if [ "$status" -eq 200 ]; then
        echo "$user/$repo already exists on forgejo."
        continue
    fi

    if ! curl -f "https://api.github.com/repos/$user/$repo"; then
        echo "$user/$repo doesn't exist"
        continue
    fi

    sudo docker exec --user git "$container" forgejo admin user create --username "$user" --email "$user@local" --password $FAKE_USER_PASS --must-change-password=false 2>/dev/null || true

    curl -s -X POST "$FORGEJO_URL/api/v1/repos/migrate" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"clone_addr\": \"https://github.com/$user/$repo.git\",
        \"repo_name\":  \"$repo\",
        \"repo_owner\": \"$user\",
        \"mirror\":     true,
        \"private\":    false,
        \"service\":    \"github\"
    }"
done <<< "$repos"


