# Tuning notes

Why each threshold has the value it has: what else was tried and how it scored. Read this before changing a number in
`talos/recognizers/` or `talos/features.py`, so you don't retry a value that already failed.

Scores come from `python tools/eval.py`, which replays the labeled clips in `tests/data/` ("collected clips") and four
older free-form recordings. "12/30" means 12 of 30 prompts recognized.

## Hand features (`features.py`, `vision.py`)

- **THUMB_TUCKED = 0.5** hand sizes, thumb tip to middle knuckle. Measured: tucked 0.16–0.35, thumb alongside the hand
  ~0.75, thumb hanging out ~1.07.
- **Tilt is measured to the middle fingertip**, not along the knuckle line: the knuckle line showed only ~30° of a ~50°
  lean.
- **Handedness is swapped** because the image is mirrored. Before the swap, the first live recording showed a right hand
  as "Left", which also flipped every palm direction.

## Twist (`twist.py`)

- Real twists turn ~150°.
- **ROLL_OUT = 35°.** At 20°, tracking jitter on an edge-on hand faked twists.
- **ROLL_BACK = 15°.** Roll jitters ~±7°.
- **QUICK = 0.6 s** per half of the roll. 0.4 s missed most real twists.
- **UPRIGHT = 25°, LEAN_FRAMES = 2.** Swipe leans read as Twist-4 without the lean limit. Mid-roll, an edge-on hand's
  lean reads wildly off for single frames (−86° in a collected twist_2), so the lean must last 2 frames.
- **Thumb rule only for Twist-4.** For Twist 1–3 it rejected real poses (thumb resting on the curled fingers, or hidden
  edge-on). For Twist-4, thumb out is the open palm of Brush Off and Burst.
- **Arms only while holding still.** Arming mid-roll (after a reset) counted the way back as a twist (collected twist_2).
- **No "palm to camera" start rule.** The twist_1 sessions start edge-on.
- **Mid-roll only the finger count must hold.** Turning the hand hides the thumb, which reset half the twists in the
  twist1 recording.
- **MID_SLACK = 1, upward only.** Edge-on, a curled finger reads as up for a few frames at the peak of the roll
  (Twist-3s read 4 fingers there). Allowing one fewer let Twist-2 steal Twist-1's rolls after a brief 2-finger reading.

## Swipes (`wrist.py`)

- Leans have |palm x| 0.65–0.90 (edge-on); flips have 0.13–0.15 (flat). That's what keeps Swipe Left/Right apart from
  Swipe Up.
- FLAT and FLAT_POSE sit mid-way in ranges that scored the same on every recording:
  - **FLAT = 0.3** (0.25–0.4 all equal).
  - **FLAT_POSE = 0.45** (0.35–0.5 all equal).
- **LEAN = 30°.** Real leans measured 33–56°.
- **REST_LEAN = 65°.** Collected rests lean up to ~55°.
- **Arms at the resting lean, not upright.** Collected swipes start from a rest already leaning ~40° and flick ~45° from
  there and back. Requiring upright missed most of them, and armed mid-flick instead, counting the way back as the
  other direction.
- **Leans are measured from the most upright moment of the last QUICK seconds.** In swipedemo, leans crept −11, −18,
  −28, −44°; measuring frame to frame never reached the threshold.
- **Home (HOME_TIME = 1.5 s).** In swipeandpush, the return lean fired Swipe Left between every pair of Swipe Rights. A
  fixed time window didn't fix it: at 15 fps the lean back took longer than any window. Home must be the hand's rest,
  not the most extreme recent lean. Back to back, that lean was the far end of the previous swipe, so the next swipe
  fell short and its way back fired instead.
- **Must stay in front of the face with ≥3 fingers up.** Collected "nothing" clips fired swipes on hands at the hair or
  face, fingers curling.
- **Score 5.** A lean also nudges the roll, so Twist-4 (score 4) completes on the same motion. Swipeandpush's leans
  fired Twist-4 thirteen times before this.
- **DWELL = 0.4 s.** In a run, the dwell is really "as long as it stayed flat" (~0.3 s); the cap matters when starting
  from a long rest. 0.3–0.6 all work.
- **Swipe Up's "in front" check applies only to start.** The flat hand looks smaller, its hand/head ratio dips to
  ~0.78, right at the cutoff, and frames dropped out at random.
- **Upright time keeps counting through "unclear" frames.** Going straight on from a Swipe Up into Point reads as
  neither pose. In collected sequences, 9 of 15 Swipe Ups were lost waiting for an upright hand.
- **No Swipe Down.** Every Swipe Up's preparation looks like one, and a mid-run lingering flat hand read as Swipe Down.

## Burst / Unburst (`hand_moves.py`)

- **FIST_TILT = 65°, FIST_DOWN = 0.4.** A Swipe Up's flat hand also shows zero fingers and fired Burst/Unburst on every
  flip in recordings. Those "fists" lean 55–150° with palm y 0.4–0.7; real fists (60 collected) lean under 56°, y under
  0.35.
- **FIST_HOLD = 4 frames** for Unburst. Curling an open hand into a pointing finger passes through a fist.
- Raising a fist into the Twist-4 pose fired Burst (demo1). The open shape requires the thumb out.
- **Fist rule (pinch mode only): the index must be folded in, FIST_REACH = 0.55.**
  - Index tip to knuckle measures ~0.36 in fists (95% under 0.51) and ~0.59 in pinches.
  - A fist's thumb lies near the index tip too: 6% of fist frames are under PINCH_ON.
  - At 0.55, no picks fired in any Burst/Unburst clip; at 0.45, one did. Hits were the same.
  - The other three fingers can't tell a pinch from a fist, because pinches curl them too. That rule blocked every
    collected pinch.
  - Without the rule, opening the hand after a pinch (into a swipe) fired Burst. The rule costs Burst 11 loose fists in
    the collected sequences, so it's only on when Point chooses with a pinch.

## Point (`hand_moves.py`)

- **POINT_DEAD = 0.4** hand sizes. A finger pointing straight up or sideways measures ~0.8.
- **The finger aims, not the whole hand.** In recordings the hand stayed upright and the finger did the aiming.
- **PINCH_ON = 0.3.** Collected point sequences: 0.25 got 12/30, 0.3 got 18/30, 0.35 got 19/30. Pointing down shrinks
  the hand-size measure, so pinches there read 0.25–0.3.
- **3D pinch check rejected.** Also requiring the tips to touch in MediaPipe's world landmarks (against tips that only
  overlap in the image) lost real pinches: Burst+Point right picks went from 10/16 to 7/16 at 4 cm, 5/16 at 3 cm.
- **Pinky option.** A raised pinky is easier for the camera to see than two touching tips. The index doesn't bend, and
  the hand never looks like Burst's fist. Not tuned yet: record `python -m talos collect sequences pinky`.

## Flick (`hand_moves.py`)

- **SNAP = 0.4.** Collected flick sequences: 0.4 got 18/30, 0.5 got 15/30.
- **BACK = 0.35.** 0.25 gave one more wrong pick.
- **Open hand, not one finger.** Collected flicks were done with the open hand (4 fingers up in ~80% of frames), so a
  one-finger Flick never armed.

## Brush Off (`hand_moves.py`)

- **BRUSH_OUT = 0.25.** 0.5 missed wrist flips done in place (those travel ~0.39).
- **START_Z = 0.05.** Held start poses measured palm z 0.07–0.6 (edge-on to angled). −0.25, to allow edge-on starts,
  gained nothing and fired in a swipe_left clip.
- **Palm only partly toward you.** Collected starts are angled (palm x −0.8, z +0.6), which reads as facing "left".
- **Start pose held 0.25 s.** A twist's roll turns the palm toward you for ~0.1 s; collected twist_3/4 fired Brush Off
  21 times without the hold. The real start pose is held ~1 s.
- **Score 6.** The flip changes the lean too, so Swipe Left/Right match the same motion; a swipe keeps the palm
  sideways.

## Ear gestures (`ear.py`)

- Tuned on the collected ear and "nothing" clips. Visits last 0.2–1.8 s, and the finger count flickers 0–2 at the ear
  (the index hides behind the head), so pointing is judged over the whole visit.
- **MIN_POINTING = 0.5.** 0.4 gave 4 false taps in "nothing" clips.
- **UP_POINTING = 0.1.** Ear Up clips pointed only 13–20% of frames.
- **AT_EAR_DEPTH = 0.9.** Collected ear visits measure 0.55–0.85 (36/37 under 0.9); hands in front of the face that only
  overlap the ear in the image have a median of 1.16. The pose model's z didn't separate them at all. Without this
  rule, Twist-1 and Burst clips fired Ear Up. It replaced a rule based on the share of frames beside the head, and
  scored 2 more ear hits with no new misfires.
- An early recording fired Ear Tap ~30 times on fingertip jitter at the ear, before visits were judged as a whole.

## Hand Swipe / Lens Wipe (`frame.py`)

- **MOVING = 0.12.** Wrist swipes peak at 0.07 of the image changing, so they can't trigger it.
- Not tested against someone walking behind you.
