# Back-test summary

Sample actually evaluated: 2 flagged firms, 6 control firms, 24 firm-years (window E-3..E-1). Flag threshold: 3 points.

| Method | AUC | Detection rate | False-positive rate | Median lead (years) |
|---|---|---|---|---|
| Numbers only | 0.63 | 50% | 50% | 1.00 |
| Numbers + text (v1, fixed in advance) | 0.53 | 50% | 50% | 1.00 |
| Numbers + text (v2, post-hoc meaning rules) | 0.63 | 50% | 50% | 1.00 |

Small-sample warning: with so few firms these figures are illustrative, not statistically reliable. v1 weights were fixed before seeing results. v2 applies keyword rules written after looking at v1's false positives on this same sample, so treat it as illustrative, not as a test.
