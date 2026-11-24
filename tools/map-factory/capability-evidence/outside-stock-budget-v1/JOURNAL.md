# PL-1294 native run log

Source: raw per-opening GPU CSV and session observations. Blade, RTX 2080 Ti at 05:00.0.

| Opening | Wall seconds | Total GPU peak MiB | Game menu MiB | Peak W | Peak C | Result |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| budget-01 | 264.3 | 10821 | [1574] | 129.74 | 58 | complete |
| budget-02 | 172.9 | 10821 | [1574] | 126.50 | 51 | complete |
| holdout-01 | 190.9 | 10821 | [1574] | 116.89 | 50 | complete |
| holdout-02 | 194.7 | 10821 | [1574] | 122.07 | 52 | complete |
| holdout-03 | 187.7 | 10821 | [1574] | 119.69 | 53 | complete |
| holdout-04 | 155.8 | 10821 | [1574] | 114.88 | 46 | complete |
| holdout-05 | 155.2 | 10821 | [1592] | 115.36 | 46 | complete |
| stock-1 | 158.8 | 10821 | [1592] | 108.62 | 38 | pre-query guard failure |
| stock-2 | 169.1 | 10821 | [1574] | 115.00 | 46 | complete |

GPU totals include other workloads. Game VRAM is sampled at menu readiness, not a measured per-game peak. The CSV reports a 200 W power limit; this study changes no power setting. No live page or recording is started. Every opening releases the slot.
