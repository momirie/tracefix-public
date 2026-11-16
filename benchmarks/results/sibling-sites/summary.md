# Sibling sites: every slice measured

Static checks of each fix the benchmark runs (scripts/bench/siblings.py, M11 S0): no
model, no Docker, no repo code run. A cell is fixes the signal fires on / fixes
measured. replaced_code: the code a hunk replaced is still elsewhere at head (block);
replaced_line: the same for single lines of 30+ characters; same_name: an untouched
namesake of a changed function; constant_reads: a test of that fix reads a value
the fix assigns.

Tasks excluded (base commit not fetched, or a setup error): 2

| group | fixes | replaced_code | replaced_line | same_name | constant_reads |
|---|---|---|---|---|---|
| gold | 66 | 11/66 (17%) | 15/66 (23%) | 14/66 (21%) | 1/65 (2%) |
| partial | 40 | 7/40 (18%) | 10/40 (25%) | 8/40 (20%) | 1/39 (3%) |
| agent_wrong | 21 | 1/21 (5%) | 0/21 (0%) | 7/21 (33%) | 0/21 (0%) |
| agent_ok | 37 | 4/37 (11%) | 3/37 (8%) | 9/37 (24%) | 4/37 (11%) |

Partial fixes with a replaced_code flag in the dropped hunk: 1

## The plan's rule

Build a sibling signal (report only) if wrong fixes (partial + agent_wrong) fire at least 15% points more often than correct fixes (gold + agent_ok) and correct fixes at most 10%; constant reads if they fire in at least 3 fixes.

- replaced_code: wrong 8/61, correct 15/103: **do not build**
- same_name: wrong 15/61, correct 23/103: **do not build**
- constant_reads: fires 6/162: **build**
