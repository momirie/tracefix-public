# Sibling sites: slice1 dev

Static checks of each fix the benchmark runs (scripts/bench/siblings.py, M11 S0): no
model, no Docker, no repo code run. A cell is fixes the signal fires on / fixes
measured. replaced_code: the code a hunk replaced is still elsewhere at head (block);
replaced_line: the same for single lines of 30+ characters; same_name: an untouched
namesake of a changed function; constant_reads: a test of that fix reads a value
the fix assigns.

Tasks excluded (base commit not fetched, or a setup error): 0

| group | fixes | replaced_code | replaced_line | same_name | constant_reads |
|---|---|---|---|---|---|
| gold | 14 | 1/14 (7%) | 2/14 (14%) | 2/14 (14%) | 1/13 (8%) |
| partial | 11 | 1/11 (9%) | 2/11 (18%) | 2/11 (18%) | 1/10 (10%) |
| agent_wrong | 0 | 0/0 | 0/0 | 0/0 | 0/0 |
| agent_ok | 0 | 0/0 | 0/0 | 0/0 | 0/0 |

Partial fixes with a replaced_code flag in the dropped hunk: 0
