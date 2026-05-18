# ADR-0001: Warning-based tagging rule

**Status:** Accepted  
**Date:** 2026-05-18

## Context

DishList allows Guests to tag their Submissions with dietary and allergen information. Two philosophies are possible:

1. **Claim-based ("free-of")** — tags assert what a dish lacks: "Peanut-free", "Dairy-free", "Gluten-free".
2. **Warning-based ("contains")** — tags assert what a dish contains: "Contains peanuts", "Contains dairy", "Contains gluten / wheat".

Potluck food is prepared in home kitchens by non-professionals. Cross-contamination is common and largely invisible to the preparer. A Guest who tags their dish "Peanut-free" may genuinely believe it, but cannot guarantee it was prepared in a nut-free environment or that every ingredient was verified.

## Decision

Tags in DishList describe what a Dish *contains* or *is*, never what it lacks. Negative claims ("free-of") are not representable as Tags in the system. The Tag Keyword auto-detection system explicitly ignores negation patterns (e.g. "peanut free", "no nuts") to prevent accidental negative-claim tags from being suggested.

## Consequences

- Guests with allergies must read the allergen tags present on a dish and make their own judgment — the app does not assert safety, only presence.
- The tag library focuses on "Contains X" for allergens and positive assertions ("Vegan", "Halal") for dietary preferences.
- Future contributors must not add "free-of" tags to the default tag library. Custom tags added via admin tools should follow the same rule, though the system cannot technically enforce it.
- This reduces liability: DishList does not claim any dish is safe for any dietary need, only that certain ingredients are declared present.
