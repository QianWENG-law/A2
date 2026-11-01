# Test case 3: PROTOX vs BOTOX (s 44)

Based on *Self Care IP Holdings Pty Ltd v Allergan Australia Pty Ltd* [2023] HCA 8.

## Inputs

Choose this case in the "Load an example" drop-down, or copy the inputs into the form.

- **Trade mark:** `PROTOX`
- **Type of mark:** Word mark
- **Logo / stylisation description:** *(leave blank)*
- **Applicant:** `Self Care IP Holdings Pty Ltd`
- **Goods/services:** `Cosmetic skin care creams and serums for reducing the appearance of fine lines and wrinkles`
- **Has the mark already been used in Australia?:** Used for less than 2 years
- **Earlier trade marks (one line):**

```
BOTOX | Pharmaceutical preparations for the treatment of wrinkles, glabellar lines | Allergan Inc
```

- **Sidebar:** reflection on, asked 3 times

## Court's outcome

The High Court held that PROTOX was **not** deceptively similar to BOTOX (the case concerned
infringement under s 120, which uses the same deceptive similarity test as s 44). The shared
"-OX" ending and similar goods were not enough, and the reputation of BOTOX was not relevant
to the comparison.

## What this tests

An evaluative "imperfect recollection" judgement. The tool may rate the s 44 risk HIGH because of
the shared "-OX" ending and BOTOX's fame, which would differ from the High Court and show a
limitation of the tool. Watch the agreement rate: a split vote shows the model is unstable.

## Variation: recall vs reasoning

Run again with invented names of the same structure:

- **Trade mark:** `DERMAX`
- **Earlier trade marks:** `VELMAX | Pharmaceutical preparations for the treatment of wrinkles | Velmax Pharma Inc`

If the result differs from the PROTOX run, the model may be relying on what it "remembers" about
the real case rather than on applying the test.

## Observed results

| Run | Marks | Overall risk | s 44 risk | s 44 agreement | Matches court? | Notes |
|---|---|---|---|---|---|---|
| 1 | PROTOX/BOTOX | | | | | |
| 2 | PROTOX/BOTOX | | | | | |
| 3 | DERMAX/VELMAX | | | | n/a | |
