# CI/CD — Automated Deploy on `develop`

A cron job on the server checks for new commits on `develop` every hour and runs `just deploy` only when something has changed.

---

## Step 1 — Create the deploy script

Save as `/home/brandonleon/dishlist-deploy.sh`:

```bash
#!/bin/bash
set -e

cd /home/brandonleon/DishList

git fetch origin develop

if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/develop)" ]; then
    just deploy
fi
```

Make it executable:

```bash
chmod +x /home/brandonleon/dishlist-deploy.sh
```

---

## Step 2 — Add the cron job

```bash
crontab -e
```

Add:

```
0 * * * * /home/brandonleon/dishlist-deploy.sh >> /home/brandonleon/dishlist-deploy.log 2>&1
```

Runs at the top of every hour. Output is appended to `dishlist-deploy.log` for review.

---

## Troubleshooting

**Script ran but didn't deploy.**
No new commits were found — expected behavior.

**`just: command not found`.**
Use the full path in the script: replace `just deploy` with `/usr/bin/just deploy`.

**`git fetch` fails.**
Check that the server has SSH access to GitHub (or HTTPS credentials) from the `brandonleon` user: `ssh -T git@github.com`.
