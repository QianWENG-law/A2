# Australian Trade Mark Registrability Pre-Check

**LAWS90286 Legal AI — Assignment 2**

**Deployed application:** https://amlsktfakztyd3ncmhjac6.streamlit.app/  

## What the tool does

A person who wants to register a trade mark in Australia enters their mark, the goods/services
it will be used for and (optionally) any earlier trade marks they know of. Before they pay the
filing fee, the tool assesses whether the mark is likely to face an objection under the
*Trade Marks Act 1995* (Cth). It then produces a downloadable report rating the risk under each
ground and suggesting how to reduce it.

The legal task is broken into discrete steps. Each step is a separate AI call that receives only
the legal notes relevant to that step (see `law_notes.py`):

| Step | Sub-process | Legal basis | AI calls |
|---|---|---|---|
| 1 | Interpret the application: meaning of the words, Nice classes, target consumers | Nice Classification | 1 |
| 2 | Prohibited signs; scandalous matter; use contrary to law | ss 39, 42 | 1 |
| 3 | Capacity to distinguish | s 41; *Clark Equipment*; *Cantarella* | 1 |
| 4 | Deceptive or confusing connotation | s 43 | 1 |
| 5 | Conflict with earlier marks (one call per earlier mark; if none are entered, s 44 is marked "not assessed" and a search plan is given) | s 44; *Shell v Esso*; *Australian Woollen Mills*; *Self Care v Allergan* | 1+ |
| ↳ | **Self-consistency (steps 3 and 5):** the evaluative questions are asked N times independently (default 3, adjustable in the sidebar); the majority risk rating is used and the agreement rate is shown as a confidence score | — | ×N |
| 6 | **Reflection:** a "reviewing partner" checks steps 1–5; any step it flags is re-run once with its comments | — | 1 (+ re-runs) |
| ⚖ | **Rule-based conclusion (code, no AI):** if any ground is HIGH → overall HIGH; else if any is MEDIUM → MEDIUM; otherwise LOW. Extra rules flag s 41(4) evidence of use and an unassessed s 44 | ss 41(4), 44 | 0 |
| 7 | Final report in plain English, following the rule-based conclusion | — | 1 |

Each run makes **at least 6 AI calls** (about 11 with the default settings and one earlier mark).
The "AI call log" tab shows every call, and the "Reviewer" tab shows what changed after reflection.

**Why self-consistency?** Whether a mark is "inherently adapted to distinguish" (s 41) or
"deceptively similar" (s 44) is an evaluative judgement, and a language model can give different
answers to the same question. Asking several times and taking the majority makes the result more
stable. The agreement rate (e.g. "2 of 3 assessments rated this HIGH") also tells the user
how confident the tool is: low agreement flags a borderline mark that needs a professional opinion.


## Running the app

1. Open the deployed URL above.
2. Enter your own OpenAI API key in the sidebar. 
3. Fill in the form and click **Run pre-check** .

## Test cases

Each test case is based on the facts of a decided Australian case, so the tool's output can be
compared with the court's actual conclusion. The app has no file upload, so no files need to be
uploaded. **Quickest way:** choose the test case in the "Load an example" drop-down at the top of
the page, which fills in the form; or copy the inputs below into the form. 
Use the default settings (reflection on, asked 3 times) unless stated.

### Test case 1:  *Cantarella Bros v Modena Trading* [2014] HCA 48

| Field | Input |
|---|---|
| Trade mark | `ORO` |
| Type of mark | Word mark |
| Goods/services | `Coffee, coffee beans, ground coffee and espresso coffee blends sold to cafes, restaurants and retailers` |
| Prior use | Used for 2+ years |
| Earlier trade marks | *(leave blank)* |

Court’s outcome: Registrable. “Oro” (Italian for “gold”) has no descriptive meaning to Australian consumers of coffee.
What this tests: whether the tool follows a counter-intuitive High Court authority. Observed: the tool reasoned from the translation (“oro” = “gold”) and rated s 41 MEDIUM, giving an overall MEDIUM, which differs from the High Court. It did correctly flag that 2+ years of use may help under s 41(4). With no earlier marks entered, s 44 was marked “not assessed” and a search plan was given. This shows a limitation: the model applies the translation instead of the “ordinary signification to Australian consumers” test, even though the law notes describe that test.

### Test case 2:  *Clark Equipment Co v Registrar of Trade Marks* (1964) 111 CLR 511

| Field | Input |
|---|---|
| Trade mark | `MICHIGAN` |
| Type of mark | Word mark |
| Goods/services | `Earthmoving machinery, tractors, loaders and parts for them` |
| Prior use | Not yet used |
| Earlier trade marks | *(leave blank)* |

Court’s outcome: Not registrable. Other traders may legitimately want to use a well-known place name.
What this tests: a straightforward s 41 case. Observed: the tool correctly rated s 41 HIGH (geographic name, not inherently adapted to distinguish), matching the court. This shows a strength. However, it also rated s 43 HIGH (deceptive geographic origin) and gave a confused suggestion to limit the goods to those not made in Michigan. It also rated s 39/42 MEDIUM while saying “no issues identified”. This shows the tool can over-flag issues and be internally inconsistent.

### Test case 3:  *Self Care IP Holdings v Allergan Australia* [2023] HCA 8

| Field | Input |
|---|---|
| Trade mark | `PROTOX` |
| Type of mark | Word mark |
| Goods/services | `Cosmetic skin care creams and serums for reducing the appearance of fine lines and wrinkles` |
| Prior use | Used for less than 2 years |
| Earlier trade marks | `BOTOX \| Pharmaceutical preparations for the treatment of wrinkles, glabellar lines \| Allergan Inc` |

Court’s outcome: Not deceptively similar to BOTOX; the shared “-OX” ending was not enough.
What this tests: an evaluative “imperfect recollection” judgement. Observed: the tool rated s 44 HIGH (deceptively similar to BOTOX), differing from the High Court. It also rated s 41 and s 43 HIGH, apparently influenced by the reputation of BOTOX, which the High Court held is not relevant to deceptive similarity. This shows a limitation: on evaluative tests, the model follows intuition and a famous mark’s reputation rather than the binding authority.

For each test, also check the agreement rate under the s 41 / s 44 ratings, low agreement shows the model is unsure.

## Files

| File | Purpose |
|---|---|
| `home.py` | Streamlit application and the 7-step pipeline |
| `law_notes.py` | Legal knowledge base: summaries of ss 39, 41, 42, 43, 44 and leading cases, given to each step |
| `sidebar.py` | API Credentials sidebar: the user enters their own OpenAI key |
| `requirements.txt` | Python dependencies |

