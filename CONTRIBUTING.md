# Contributing to Property Finder Bot

## 🚨 Branch Protection — NEVER Push Directly to Main

We follow a **feature branch workflow**. All changes must go through a child branch.

### Quick Start

```bash
# 1. Create your feature branch
git checkout main
git pull origin main
git checkout -b yourname/feature-name

# 2. Make changes, commit, push
git add -A
git commit -m "feat: your changes"
git push -u origin yourname/feature-name

# 3. Test thoroughly
python bot/main.py     # Run bot, test in Telegram
python check_db.py     # Verify database

# 4. Merge to main ONLY after successful testing
git checkout main
git pull origin main
git merge yourname/feature-name --no-ff -m "Merge feature-name"
git push origin main
```

### Rules
1. **NEVER** commit directly to `main`
2. Always create a child branch from `main`
3. Test your changes before merging
4. Use descriptive branch names: `yourname/what-you-changed`
5. Use descriptive commit messages: `feat:`, `fix:`, `docs:`

### Branch Naming
- `marutatmaj/add-search-filters`
- `friend/fix-onboarding`
- `yourname/update-docs`
