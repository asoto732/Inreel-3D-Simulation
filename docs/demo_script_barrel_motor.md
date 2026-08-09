# Demo script — barrel & motor physics update

Covers commit `b2ca5ad` on `reel-command-indicator`: real Sandvik motor spec,
real torque-driven drum dynamics, and a cable capacity interlock. Verified
live against the running sim before writing this, not just read off the diff.

Where to look: scroll to the bottom of the right-hand column in
`docs/gimbal_axis_simulator.html` — three stacked panels, in this order:
**Cable capacity interlock** (green border) → **Motor & drum torque check**
(red border) → the reel command indicator above them.

---

## 1. The drum used to fake it — now it doesn't

**Say:** "Before this change, the barrel spinning in the 3D view was
cosmetic — it spun at a rate proportional to duty cycle, full stop. Now it's
a real equation of motion: `I(L) × dω/dt = net torque`, integrated every
frame using actual elapsed time."

**Show:** Drive the Y (directional) slider toward its max, watch the
**"Drum speed"** and **"Drum inertia I(L)"** readouts in the torque check
panel update live, and watch the barrel's spin rate visibly lag behind the
duty change rather than snapping to it.

**The concrete result of this:** a heavily spooled drum (high inertia)
accelerates more sluggishly than a nearly-empty one at the same commanded
duty — that lag simply didn't exist in the old model. It also means the
drum can now **fail to move at all** if available torque can't overcome the
load — a real, demonstrable failure mode, not something clamped away.

---

## 2. The motor spec is now real, not illustrative

**Say:** "Every torque number up to this point was a round placeholder —
50 Nm, 30:1 gear ratio, made up so the mechanism was visible. That's gone.
This is now sourced from a real Sandvik vendor hydraulic calc sheet."

**Show:** Click **"Load Sandvik reel motor (theoretical, from vendor calc
sheet)"** in the torque check panel.

**The numbers, and why they're trustworthy — verified live, not just quoted
from a comment:**

| Value | Number | Where it comes from |
|---|---|---|
| Motor torque | **432.4 Nm** | pressure (1000 PSI) × displacement (393.9 cc) / 2π — matches the vendor sheet's own 432.4 Nm |
| Gear ratio | **1.4545** (32:22) | real sprocket-chain reduction on the rig — a **20× correction** from the old 30:1 placeholder |
| Efficiency | **1.0** | the theoretical column assumes an ideal, lossless chain — confirmed exactly: 432.4 × 32/22 = **628.9 Nm**, matching the sheet's peak reel torque to the decimal |
| Peak reel speed | **13.9 RPM** | flow-limited cap from the sheet, used as the drum's hard speed ceiling |

**One number that's worth saying out loud in the room:** the sheet also has
a real *Eaton catalog spec* column that runs *higher* than the theoretical
one (520 Nm / 15.0 RPM / 756.4 Nm at the reel) — because a catalog rating
already includes real motor losses an ideal calc doesn't capture. The
theoretical column was chosen deliberately as the **more conservative**
default, not because it's the only real number available.

**One open item, say it plainly if asked:** the calc sheet's own cable
diameter (2.2 in) doesn't quite match the Nexans spec the drum model uses
(2.12 in) — about 4% off, not rounding noise. Flagged, not silently
reconciled. Worth asking whoever owns that sheet which one is authoritative.

---

## 3. Why unwind couldn't move at all — and the fix

This is the most concrete "we found a real bug via physics, not
guesswork" moment in the whole update, worth telling as a story rather than
just stating the fix.

**Say:** "When we first wired the real motor spec into the real inertia
model, unwind stopped working entirely — the drum simply wouldn't move in
that direction, at any duty. That wasn't a UI bug, it was the physics
telling us something true: the real Sandvik motor (629 Nm at the drum)
literally cannot out-pull the real 200 lbf vendor-recommended cable tension
(725–772 Nm at this drum's radius) if you model tension as a symmetric
resistive force in both directions."

**The fix, and why it's not a fudge:** cable tension isn't friction — it
doesn't flip sign to oppose whatever the drum happens to be doing. It has a
**fixed physical direction**, toward unwind, because it's the rig pulling
cable off the reel. So:

- **REEL IN** — tension genuinely opposes the motor. If tension ever wins,
  the drum gets dragged into unwinding *despite* the wind command — a real
  failure mode this sim now shows rather than clamps away.
- **UNREEL** — tension now *assists* the commanded torque, because that's
  physically what's happening: the rig is pulling cable out, the motor is
  mostly just controlling the release rate, not fighting the load.
- **HOLD** — unchanged: a stationary, uncommanded drum is still treated as
  fully held (no counterbalance/holding-valve spec exists to model creep,
  flagged as an open item, not invented).

**Show:** drive the Y slider to make the reel unwind, and point out it now
actually moves — that literally didn't work before this fix.

---

## 4. The cable capacity interlock

**Say:** "This started as a question during an LLM council review: should
we add a drum encoder so the rig knows how much cable is left before it
tries to tram away? The council flagged a specific, subtle danger in how
you'd naively build that — turns × circumference isn't a valid way to
convert 'turns of the drum' into 'meters of cable,' because each layer
winds at a larger radius than the one before it. The naive math drifts
worst exactly where an interlock threshold lives — near empty."

**Show:** point at the **Turns remaining**, **Layer**, and **Spooled
length** readouts, and the capacity bar underneath them.

**The verified numbers:** this drum holds cable across exactly **2
layers**, **68 turns** total (34 wraps per layer — width ÷ cable OD), and
the layer-by-layer model reconciles to **359.40 m** — matching the drum's
known real capacity (359.4 m) to within a tenth of a meter. That
reconciliation check is deliberate: confirm the model agrees with known
reality before trusting it for anything downstream.

**Also worth mentioning:** during the council review, one advisor estimated
roughly 8–9 layers by eyeballing it; another (correctly) estimated around 2
by working from the flange/core radius gap. The exact model settled it —
worth saying, since it's a good example of why you build the real model
instead of trusting either guess.

**The TRAM ALLOWED / TRAM BLOCKED indicator:**

- Two independent thresholds — **warn** and **block** — not one, so there's
  a visible "getting close" state before an actual lockout.
- **Hysteresis via a rearm margin**: once blocked, capacity has to climb
  back *above* block+margin before it clears — a single hard threshold
  chatters right at the boundary, which is exactly the kind of nuisance
  lockout that gets routed around by operators in the field. This was also
  a specific council-flagged failure mode.
- **Simulate encoder fault** checkbox: forces BLOCKED regardless of actual
  capacity — fails closed, matching the DS-SF-02 posture already used
  elsewhere in this project for sensor faults.

**Caveat to state plainly:** this box is informational only — the sim has
no actual tramming/drive feature for it to gate. It's a live readout of
what a real interlock built this way *would* report.

---

## Closing line, if you need one

"Everything in this update replaced a placeholder with something either
measured or derived from a real vendor spec, and where the physics
disagreed with an earlier assumption — like the symmetric tension model
that made unwind impossible — the fix came from taking the disagreement
seriously rather than clamping it away. The two open items — the 4% cable
diameter mismatch and the missing holding-valve spec — are named, not
buried."
