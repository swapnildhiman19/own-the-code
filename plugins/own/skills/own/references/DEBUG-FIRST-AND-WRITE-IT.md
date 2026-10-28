# Debug first, and "let me write this part"

Both train the thinking that AI help erodes most (Anthropic's 2026 study: the "AI fixes my bugs" group scored
lowest of all). But a guess only trains anything when the user has a picture of the code in their head. Asked
about code they've never seen, they can only toss a coin. In two real cases the user answered "Not sure, just fix
it" both times, and felt like an outsider in their own project. So the guess comes **only for code they've
walked**. Everywhere else Own fixes first and **shows** what broke.

## Debug first - when the user reports a bug

Only when the user reports something broken ("Mia's Pay button is grey", "the nightly export skipped a store").
Never for test failures or errors you hit yourself while building.

1. **Straight to the fix** when: they say it's urgent (production down, a demo in minutes, "just fix it"); status
   says `busy_today`; or they reported it while answering another card (they're in "fix it" mode). Go to step 5.
2. Otherwise read just enough code to know the 3 most likely places (real files and functions).
3. Ask the tool whether the user has seen that code:

   ```bash
   python3 -I ~/code-guides/.bin/own-guide seen app/cart.py:52 src/checkout.js app/payments.py
   ```

   `"ask_guess": true` means each file is on a flow page they have walked, and none of them changed since that
   page was checked. Anything else (`unseen` not empty): skip the guess, go to step 5.
4. Only with `"ask_guess": true`: one AskUserQuestion, header "Debug":
   - Question: "Before I dig in: where would you look first?" + one line restating the symptom.
   - Options: the 3 places (each one short line: `file` - what lives there, in the words of the walk they did),
     plus **"Not sure, just fix it"**. If they pick that, go straight on, no more questions.
5. Investigate and fix as usual.
6. **Show what broke**: the code walk ([CODE-WALK.md](CODE-WALK.md), `moment: bug`) of the steps from what they
   saw on screen back to the cause. The step where it broke is marked `broken`, its bad value is visible ("This
   coupon has expired" because `row.expires < today` was `True` an hour after midnight), and `after` holds the fix. If they guessed, say how close they
   were in one or two lines, with `file:line`: "Your guess was right: her cart total is saved as '0.00 ' with a
   trailing space." / "Close: the cart is read in `app/cart.py`, but the rule that greys the button is in
   `src/checkout.js:88`."
7. Save one question about it for tomorrow (never ask it now; they just watched the answer):

   ```bash
   python3 -I ~/code-guides/.bin/own-guide add-question --kind debug \
     --tests "why SPRING10 was refused the morning after it expired" \
     --answer "app/cart.py:53 apply_coupon() compared row.expires, not the 24-hour grace, with now" \
     --source flow:<page> --feature "Bug: <one line>" --ask-tomorrow
   ```

8. If the guide has a page for this flow, add the symptom to its "If it breaks, look here first" and refresh the
   page (FLOW-FORMAT.md, then `stamp`).

## "Let me write this part" - only when the user asks

This is **Your line** ([OWNERSHIP.md](OWNERSHIP.md)) with a bigger gap: pick a small, meaningful piece of the
current work, 5-15 lines with a real decision in it (a condition, a query, an error case), not boilerplate.
Prepare the place with the function signature, the surrounding code and a clear comment block:

```python
def may_checkout(cart, user):
    # YOUR PART (5-10 lines):
    # Return True when this person may pay for this cart.
    # You have: cart.items (a list), cart.total (a Decimal), user.is_blocked (a bool).
    # Think about: an empty cart; a cart whose total is 0 after a 100% coupon.
    raise NotImplementedError
```

Tell the user the file and what to think about, show that part's code walk step with its values, then wait.
Don't write it for them. When they're done, run the tests and help until they pass (hints, not the answer), review
like a kind senior (what works, one thing to improve and why), and record it with
`owned line --who you --what "..." --file <file>`. Record any new idea it practised in LEARNINGS.
