# Sibling sites: slice2 dev

Static checks of each fix the benchmark runs (scripts/bench/siblings.py, M11 S0): no
model, no Docker, no repo code run. A cell is fixes the signal fires on / fixes
measured. replaced_code: the code a hunk replaced is still elsewhere at head (block);
replaced_line: the same for single lines of 30+ characters; same_name: an untouched
namesake of a changed function; constant_reads: a test of that fix reads a value
the fix assigns.

Tasks excluded (base commit not fetched, or a setup error): 2

| group | fixes | replaced_code | replaced_line | same_name | constant_reads |
|---|---|---|---|---|---|
| gold | 52 | 10/52 (19%) | 13/52 (25%) | 12/52 (23%) | 0/52 (0%) |
| partial | 29 | 6/29 (21%) | 8/29 (28%) | 6/29 (21%) | 0/29 (0%) |
| agent_wrong | 21 | 1/21 (5%) | 0/21 (0%) | 7/21 (33%) | 0/21 (0%) |
| agent_ok | 37 | 4/37 (11%) | 3/37 (8%) | 9/37 (24%) | 4/37 (11%) |

Partial fixes with a replaced_code flag in the dropped hunk: 1
