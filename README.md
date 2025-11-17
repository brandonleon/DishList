## DishList

FastAPI-powered potluck planner where guests can log what they are bringing, show allergens, and mark dietary flags.

### Highlights

- Bootstrap UI with a toggle between card and table views so guests can scan long lists.
- Admin portal to update dish types/IP allowlist plus edit or delete any submission.
- File-backed SQLite database (`data/dishlist.db`) ready to map to a Docker volume later.

### Getting started

```bash
pip install -e .
python main.py
```

Visit http://127.0.0.1:8000/ to see the potluck board. Submissions are stored in `data/dishlist.db` (SQLite).

### Admin access

The configuration screen lives at `/pantry-admin`. Only IPs/networks listed in `data/config.json` may hit that route. Use it to:

- Control the dish types shown in the submission form
- Update which IP ranges may open the admin URL
- Edit or delete dishes without grabbing anyone's laptop

All data is file-based so it is easy to reset or version control.

### Data storage

- Dish submissions live in the SQLite database at `data/dishlist.db`, making it easy to mount the file in a Docker volume later.
- Admin settings continue to live in `data/config.json` for straightforward editing or seeding.
