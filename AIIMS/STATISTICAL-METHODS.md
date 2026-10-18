# Clinical Statistical Assessment · implementation 1.0

This is an extension of the AIIMS doctor dashboard. Authentication, Google Drive permissions, patient records, patient forms and existing exports are unchanged. There is no clinical database migration: `care.js` exposes the same authorized, in-memory records already loaded for the doctor overview. The analysis module creates only an ephemeral de-identified projection of selected snapshot fields. Neither records nor reports are uploaded to an analysis service.

## Data contract

`care-stats-data.js` derives selectable categories from saved entries and the existing patient form's field contract. The available fields are pain (ordinal integer 0–10), explicitly ordered sleep quality and disease duration, derived age bands, sleep hours, sex, diagnoses and diagnosis status, unordered mood, food habit, exact recorded medication text, food and medication category combinations, individual category selections, period status and pain location. Free-text clinical notes and unstructured dose/medicines-taken descriptions are not automatically interpreted. There are no structured yoga, flare, stress severity, anxiety severity or disease severity fields; these are not invented.

An empty category list is missing. An unselected checkbox within a nonempty recorded list is labelled **Not selected**, not **No use**. Combinations are exact sorted sets, without imputing ingredients or medicine doses. Age bands are Under 18, 18–29, 30–44, 45–59, 60 and above; no continuous age measurement is substituted for them. Mood has no ordinal ranking.

Historical entry snapshots are never backfilled from the current profile. Cohort filters use those snapshots. A newly edited profile therefore enters this longitudinal analysis when a pain entry containing that updated profile is saved and synced. No historical diagnoses or treatment exposures are retrospectively rewritten. Patient fields absent from historical records are reported as missing. Text categories require clinical review for spelling variants and possible identifiers; the module does not silently normalize different diagnoses or drug names into one condition.

The representative daily entry is either the highest recorded pain rating or the last saved entry that day, chosen explicitly. Every selected variable comes from that same entry. One location can be selected. All-location maximum pain is the maximum *reported* rating, not a standardized full-body assessment; changing reported locations can affect comparisons. Independent tests use the latest eligible date per patient, before complete-case exclusion; they never search back for an older complete entry. Daily units are reserved for repeated methods. Duplicate files for the same patient ID are not counted twice.

Matched tests use explicitly selected exact dates and complete patients. GEE uses patient clusters. No repeated row is accepted by an independent-patient test. Filters combine sex, age, selected patient files, disease, medication, location and dates; within disease/medication lists the rule is any selected category. All available recorded sex categories are derived from actual data. UI fields have no fabricated third sex category.

## Runtime and methods

Pinned Pyodide **0.27.7**, Python **3.12.7**, SciPy **1.14.1**, statsmodels **0.14.4**, NumPy **2.0.2**, pandas **2.2.3**. Packages load from jsDelivr when first needed; PDF export additionally loads the matching Pyodide Matplotlib package. Software versions are read at runtime into every report. Calculations run in a worker and can be cancelled by terminating it. An in-flight run is cancelled when source data changes. The completed result stays visible as a dated snapshot with a Use updated data button, until Run stats replaces it successfully. Selection changes also retain the prior result with a notice. Sign-out, account switch or loss of source-record access clears it.

- Spearman, Kendall tau-b and directional Somers D use SciPy estimates and pairing permutation inference. Gamma uses concordant/discordant pair counts, excluding ties. Jonckheere–Terpstra uses the pairwise U statistic with half weight for ties and a prespecified increasing alternative. Rank association permutations use `scipy.stats.permutation_test`; randomized runs use seed 20261018 and up to 9,999 requested permutations. SciPy may enumerate all permutations when fewer are available. These methods are limited to 2,000 independent patients per browser run.
- Pearson and likelihood-ratio chi-square use `scipy.stats.chi2_contingency` without continuity correction. Fisher uses SciPy's two-sided 2×2 exact test. Larger tables use the **fixed-margin Monte Carlo Pearson independence alternative**, not an incorrectly labelled exact Fisher–Freeman–Halton calculation: `scipy.stats.random_table` samples 9,999 tables with the observed margins, and p=(extreme+1)/(replicates+1). Monte Carlo standard error is reported. Phi and conventional Cramér V use the Pearson statistic and explicitly ordered table labels. Expected counts are checked: asymptotic independence inference is blocked if any expected count is below one or more than 20% are below five.
- CMH uses statsmodels `StratifiedTable`, pooled odds ratio, log-odds interval and Breslow–Day/Tarone homogeneity diagnostic. Independent strata with nonempty margins are required. Fisher's sample OR can be infinite; no fabricated finite estimate is substituted. When all cells are positive, its optional OR interval is explicitly identified as a log-Wald interval, not an exact interval.
- Mann–Whitney uses SciPy's permutation method and rank-biserial effect. Kruskal–Wallis uses SciPy's tie-corrected H and epsilon-squared. Dunn uses the standard pooled rank-variance and tie correction, tested against scikit-posthocs. The Cochran–Armitage trend is statsmodels `Table.test_ordinal_association` with explicit ordered row scores and binary event scores.
- Proportional odds is a single multivariable ordinal logistic model (`OrderedModel`), not two duplicated model buttons. Nominal and ordinal predictors are reference-category dummy coded; only sleep hours is optionally numeric. Binary and multinomial regression use statsmodels Logit and MNLogit. Multinomial exponentiated coefficients are labelled relative-risk ratios, not odds ratios. Two-predictor full interactions are available; collinearity and parameter count are checked. Optional stratification fits each eligible disease/cohort stratum separately and adjusts the combined within-run p-value family.
- Ordinal proportional-odds diagnostics compare threshold-specific slopes using stacked cumulative binary regressions with patient-cluster robust covariance and a joint Wald restriction. It is not a likelihood-ratio test that treats stacked thresholds as independent. Singular, insufficient or rejected diagnostics block common-odds reporting. A non-rejection does not establish proportional odds. This diagnostic is not offered as a validated diagnostic for correlated ordinal GEE.
- Binary GEE uses an exchangeable working correlation; ordinal GEE uses working independence with robust patient-cluster covariance. At least 30 clusters, including 20 repeated clusters, are required. Ordinal GEE assumes common cumulative slopes and reports the lack of a formal correlated proportional-odds test. GEE estimates population-average associations, not patient random effects.
- Friedman, paired sign, Wilcoxon, exact McNemar and Cochran Q use SciPy or statsmodels. Wilcoxon is limited to numeric pain or sleep-hour differences and requires explicit confirmation of meaningful spacing and approximate symmetry; otherwise the sign test is offered. Stuart–Maxwell and Bowker use statsmodels `SquareTable` with zero shifting disabled and sparse discordant-pair guards. Complete matched patients, not all candidate rows, determine final sample sizes.
- MCA uses complete one-hot indicators and SciPy SVD of standardized correspondence residuals. Uncorrected eigenvalues, inertia and category coordinates are descriptive only and are tested against Prince MCA. Log-linear analysis uses statsmodels Poisson GLM and a nested main-effects vs all two-way interaction likelihood-ratio test. Sparse joint cells are blocked.

Polychoric correlation, partial proportional odds, CLMM and frequentist mixed-effects logistic regression are **not enabled**: no validated fitting-plus-diagnostics implementation has been integrated for this pinned browser runtime. They are listed separately with reasons and are never presented as functioning placeholders. Ordinal/binary GEE is an explicitly different available estimand, not a renamed mixed model. There is no automatic NLP or AI coding of notes.

Regression guardrails require at least max(30,10×parameter count) patients, minimum outcome category counts, full-rank design matrices, convergence, finite nonsingular covariance and non-extreme coefficients/standard errors. These are conservative exploratory engineering checks, not a formal prospective sample-size calculation. A sparse or nonconverged model returns an explicit reason instead of releasing unstable estimates. Confidence intervals where calculated are 95% unadjusted Wald intervals. No unspecified confidence intervals are invented.

Holm or Benjamini–Hochberg corrections cover the p-values generated **within one run** (including requested post-hoc comparisons, coefficients and strata). Model-assumption diagnostics are excluded. Separate exploratory runs are not automatically one corrected study family; prespecification remains necessary. Observational associations never imply causation or a treatment recommendation.

## Reports and privacy

CSV is UTF-8 and formula-neutralized. XLSX is an Open XML workbook with inline text (never formulas). PDF uses the pinned Matplotlib PDF backend and includes an adjusted-estimate forest plot when available. Reports include cohort filters, model settings, missingness, software, source-projection SHA-256, correction scope and analysis date. Selected patient counts replace patient file IDs. Names, emails, original patient IDs, dates of birth, clinical notes and patient-level data rows are never sent to the statistical worker or included in reports. Reports remain health information and should be handled appropriately.

If a count table has any positive cell below five, the entire count table and expected table are suppressed in downloaded reports, preventing simple complementary recovery within that table. Descriptive distributions use the same whole-distribution rule. This limited export safeguard does not constitute formal anonymization or prevent inference from overlapping reports. Authorized doctors can inspect their patient records and detailed counts in the dashboard. Statistical exports do not change the existing explicitly identifiable clinical CSV download.

## Validation

Run:

```sh
node --test AIIMS/tests/*.test.cjs
python AIIMS/tests/stats_engine_test.py
```

The reference tests need the pinned SciPy/statsmodels versions plus scikit-posthocs, Prince, openpyxl and pypdf for independent checks; these test-only packages are not application dependencies. Pyodide was also exercised directly to verify the actual WebAssembly runtime, engine import and a documented Fisher reference result. UI interaction tests use a DOM environment; no browser/mobile rendering verification is claimed when the supported browser tooling is unavailable.

Official implementation references:
- https://pyodide.org/en/0.27.7/usage/packages-in-pyodide.html
- https://docs.scipy.org/doc/scipy-1.14.1/reference/stats.html
- https://docs.scipy.org/doc/scipy-1.14.1/reference/generated/scipy.stats.permutation_test.html
- https://www.statsmodels.org/v0.14.4/contingency_tables.html
- https://www.statsmodels.org/v0.14.4/gee.html
- https://www.statsmodels.org/v0.14.4/generated/statsmodels.miscmodels.ordinal_model.OrderedModel.html

For optional DOM and pinned WebAssembly QA:

```sh
npm install --prefix /tmp/pain-gauge-testdeps jsdom@26.1.0 pyodide@0.27.7 --no-audit --no-fund
NODE_PATH=/tmp/pain-gauge-testdeps/node_modules node AIIMS/tests/stats-ui.cjs
NODE_PATH=/tmp/pain-gauge-testdeps/node_modules node AIIMS/tests/stats-wasm.cjs
```

The native reference environment uses `AIIMS/tests/stats-requirements.txt`; the WebAssembly test uses the actual distribution's pinned compiled packages. Native Matplotlib may be newer for NumPy 2 compatibility; the deployed PDF backend remains the Pyodide-built 3.8.4 package.
