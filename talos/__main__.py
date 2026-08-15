"""Talos entry point.

  python -m talos                   watch the camera and run bound actions
  python -m talos --debug           same, with the debug window (q or Esc to quit)
  python -m talos --record F.jsonl.gz   also save the tracked points to a file
  python -m talos --dry-run         print the actions instead of running them
  python -m talos replay F.jsonl.gz print the events a recording produces and the actions they'd run
  python -m talos action NAME [ARG] run one action now
  python -m talos app               the menu-bar app: camera on/off, event popup, misfire log
  python -m talos collect [GESTURE ...] [--count 10] [--slot 2] [--auto]
                                    guided session: do each prompted gesture; labeled clips go to tests/data
"""
import argparse
import time

import cv2

from talos import actions
from talos.bindings import Bindings
from talos.events import Event
from talos.pipeline import process, simulate, stop_on_ctrl_c, user_config


def dry(name, event, arg):
    pass  # process() already printed what would run


def live(args):
    from talos import debug, vision
    from talos.actions import overview
    bindings = Bindings(user_config(), run=dry if args.dry_run else actions.submit)
    recorder = None
    if args.record:
        from talos.record import Recorder
        recorder = Recorder(args.record)
    stats, stop = debug.Stats(), stop_on_ctrl_c()

    def on_frame(frame, f, found, log):
        if stop:
            return False
        if recorder:
            recorder.write(frame)
        text = stats.tick()
        overview.draw()
        if args.debug:
            return debug.show(frame, f, found, log, text)
        cv2.waitKey(1)  # lets the overview window draw

    frames = vision.frames()
    try:
        process(frames, bindings, on_frame)
    except KeyboardInterrupt:
        pass
    finally:
        frames.close()  # shut the camera and models down now, not during Python's exit
        cv2.destroyAllWindows()
        actions.drain()
        if recorder:
            recorder.close()
            print(f"saved {args.record}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", choices=["replay", "action", "collect", "app"])
    p.add_argument("target", nargs="*")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--record")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--count", type=int, default=10, help="collect: number of prompts (10 x 3s = 30s)")
    p.add_argument("--slot", type=float, default=2.0, help="collect: seconds to do each prompt")
    p.add_argument("--auto", action="store_true", help="collect: start with autoplay on (A toggles it)")
    args = p.parse_args()
    if args.command == "collect":
        from talos.collect import collect
        collect(args)
    elif args.command == "app":
        from talos.app import run
        run()
    elif args.command == "replay":
        from talos.record import read
        process(read(args.target[0]), Bindings(user_config(), run=simulate))  # Burst opens the overview for Point
    elif args.command == "action":
        Bindings(user_config(), run=dry)  # loads the actions and settings
        name, arg = args.target[0], " ".join(args.target[1:]) or None
        fn, phases = actions.REGISTRY[name]
        if "end" in phases:  # an ongoing action, e.g. hold_key: hold for 3 seconds, then release
            fn(Event(name, "begin", 0), arg)
            time.sleep(3)
            fn(Event(name, "end", 3), arg)
        else:
            fn(Event(name, "once", 0), arg)
    else:
        live(args)


if __name__ == "__main__":
    main()
