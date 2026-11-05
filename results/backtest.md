# Back-test summary

Sample actually evaluated: 1 flagged firms, 3 control firms, 12 firm-years (window E-3..E-1). Flag threshold: 3 points.

| Method | AUC | Detection rate | False-positive rate | Median lead (years) |
|---|---|---|---|---|
| Numbers only | 0.72 | 100% | 67% | 1.00 |
| Numbers + text | 0.72 | 100% | 67% | 1.00 |

Small-sample warning: with so few firms these figures are illustrative, not statistically reliable. Weights were fixed before seeing results; nothing was tuned on this sample.
