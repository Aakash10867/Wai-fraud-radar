# Back-test summary

Sample actually evaluated: 2 flagged firms, 4 control firms, 18 firm-years (window E-3..E-1). Flag threshold: 3 points.

| Method | AUC | Detection rate | False-positive rate | Median lead (years) |
|---|---|---|---|---|
| Numbers only | 0.62 | 50% | 50% | 1.00 |
| Numbers + text | 0.60 | 50% | 50% | 1.00 |

Small-sample warning: with so few firms these figures are illustrative, not statistically reliable. Weights were fixed before seeing results; nothing was tuned on this sample.
