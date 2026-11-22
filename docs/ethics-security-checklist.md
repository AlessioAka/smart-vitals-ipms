# Output 3 · Ethics, security, privacy, sustainability, societal

**The argued paragraphs are yours.** Column 2 states honestly what this build does, so you do not claim more
than exists. Column 3 holds prompts for your critical discussion.

## Security (R5)
| Topic | What this build does | What you must argue |
|---|---|---|
| Access control | Every patient route checks the patient is assigned to the logged-in clinician (403 otherwise); tested | Is 403 vs 404 the right choice? (enumeration) |
| Authentication | Hashed passwords (PBKDF2), signed 8-hour tokens, session cookie (HttpOnly, SameSite=Lax) | What is missing? (MFA, lockout, rate limiting) |
| Device auth | One shared device key from `.env` | Per-device keys / certificates? |
| Web attacks | CSRF token on every dashboard form; Jinja auto-escaping; parameterised SQL | Threat model (STRIDE or similar): list threats, who, impact, mitigation, residual risk |
| Secrets | In `.env` (git-ignored), never in code | Secret rotation, vaults |
| Containers | Slim base image, non-root user | Image scanning, pinned digests |
| **Not implemented** | TLS, encryption at rest, audit log, rate limiting, MFA | Say so, and say what you would add first |

## Privacy and data protection (R7)
| Topic | What this build does | What you must argue |
|---|---|---|
| No real data | 100 % simulated; tested that the register has no names | Why this satisfies R7 for the prototype |
| UK GDPR | Nothing personal exists, but the *design* stores health data | Special category data, lawful basis, data minimisation, retention, DPIA, right of access/erasure: how would a real deployment comply? (cite ICO guidance) |
| Minimisation | Stores only the vitals needed | Do you need to keep every reading forever? |

## Ethics and responsible AI
| Topic | Evidence in the build | Prompts |
|---|---|---|
| Alarm fatigue | One alert per episode, repeat counter, escalation | Too few alerts is dangerous; too many is ignored: where is your line? |
| False negatives | Recall for Critical, T10 | Who is harmed by a missed Critical? |
| Transparency | Each alert lists the vitals that drove it | Is a rule-based explanation honest for a forest model? (see assumption A3) |
| Fairness | Simulated population only | What could go wrong with real data (pulse oximeters and skin tone, age, sex)? |
| Human in the loop | Model advises; clinician acknowledges | Automation bias |
| Label limitation | Labels made by a rule (A3) | What does this do to every performance claim you make? |

## Sustainability
| Topic | Evidence | Prompts |
|---|---|---|
| Compute per request | Notebook 03 timing table (model loaded once vs every request) | Cost and carbon of per-request waste |
| Edge filtering | Impossible values blanked before sending | What does the edge save in network traffic? Measure it. |
| Image size | Simulator image needs numpy only; API image carries scikit-learn, pandas, matplotlib | Run `docker images` and record the sizes |
| Retraining | Not scheduled | Carbon-aware retraining (GB Carbon Intensity API) |

## Societal
Digital exclusion, clinician workload, trust, over-reliance, who owns the data, effect on patient autonomy and
on health inequalities. *Your argument, with sources.*
