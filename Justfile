# DishList deployment tasks
# Run from the dev server where this repo is cloned.

# Pull latest changes and rebuild the container
deploy:
    git pull
    docker compose up --build --detach

# Stop the running container
stop:
    docker compose down

# Rebuild without pulling (useful for local changes)
rebuild:
    docker compose up --build --detach

# Follow container logs
logs:
    docker compose logs --follow

# Show container status
ps:
    docker compose ps
