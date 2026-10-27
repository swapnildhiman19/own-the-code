# Debug first, and "let me write this part"

Both train the thinking that AI help erodes most (Anthropic's 2026 study: the "AI fixes my bugs" group scored
lowest of all). Both are short and never automatic for errors Claude hits on its own.

## Debug first - when the user reports a bug

Only when the user reports something broken ("Mia's Checkout button is grey", "the nightly export skipped a
store"). Never for test failures or errors you hit yourself while building in Auto mode.

1. **Urgent first:** if their message says it's urgent (production down, a demo in minutes, "just fix it"), skip
   all of this and investigate straight away.
2. Otherwise, read just enough code to know the 3 most likely places (real files and functions).
3. One AskUserQuestion, header "Debug":
   - Question: "Before I dig in: where would you look first?" + one line restating the symptom.
   - Options: the 3 real places (each one short line: `file` - what lives there), plus **"Not sure, just fix it"**.
   If they pick "Not sure, just fix it", go straight on - no more questions.
4. Investigate and fix as usual.
5. Close with one or two lines on how close their guess was: "Your guess was right: her cart total is saved as
   '0.00 ' with a trailing space." / "Close: the cart is read in `app/cart.py`, but the rule that greys the
   button is in `src/checkout.js`."
6. If the guide has a page for this flow, add the symptom to its "If it breaks, look here first".

## "Let me write this part" - only when the user asks

1. Pick a small, meaningful piece of the current work: 5-15 lines with a real decision in it (a condition, a
   query, an error case) - not boilerplate.
2. Prepare the place: the function signature, surrounding code, and a clear comment block:

```python
def may_checkout(cart, user):
    # YOUR PART (5-10 lines):
    # Return True when this person may pay for this cart.
    # You have: cart.items (a list), cart.total (a Decimal), user.is_blocked (a bool).
    # Think about: an empty cart; a cart whose total is 0 after a 100% coupon.
    raise NotImplementedError
```

3. Tell the user the file and what to think about, then wait. Don't write it for them.
4. When they're done, review like a kind senior: what works, one thing to improve and why, then run the tests.
5. Record the idea it practised in LEARNINGS if it's new to them.
