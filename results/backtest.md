# Back-test summary

Sample actually evaluated: 2 flagged firms, 6 control firms, 23 firm-years (window E-3..E-1). Flag threshold: 3 points.

| Method | AUC | Detection rate | False-positive rate | Median lead (years) |
|---|---|---|---|---|
| Numbers only | 0.74 | 50% | 33% | 1.00 |
| Numbers + text | 0.69 | 50% | 33% | 1.00 |

Small-sample warning: with so few firms these figures are illustrative, not statistically reliable. Weights were fixed before seeing results; nothing was tuned on this sample.
