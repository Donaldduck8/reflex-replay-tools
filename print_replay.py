import re
import os
import sys

import collections.abc

from replay import *


def print_to_file(p, replay):
    with open(p, "w+") as sys.stdout:
        print_good(replay)

    sys.stdout = sys.__stdout__

    print("Done!")


def print_good(root, lvl=0):
    prefix = "\t" * lvl

    if isinstance(root, dict):
        for k,v in root.items():
            if k.startswith("_") or v == None:
                continue

            # ULTRA HACK to avoid printing masks
            if re.match(r"m\d+$", k):
                continue

            if k == "faceTable":
                print(prefix + k)
                print(prefix + "\t" + " ".join([str(x) for x in v]))
            elif isinstance(v, collections.abc.Container) and not isinstance(v, str):
                print(prefix + k)
                print_good(v, lvl+1)
            else:
                print(prefix + k, str(v))
    elif isinstance(root, list):
        for i,v in enumerate(root):
            if isinstance(v, collections.abc.Container) and not isinstance(v, str):
                print_good(v, lvl)

                # I wanna print a newline here if there's another entry after this one
                if i != len(root) - 1:
                    print()
            else:
                print(prefix + str(v))


if __name__ == "__main__":
    print("Make sure to avoid spaces in your file paths!")

    if len(sys.argv) == 2:
        replay_p = sys.argv[1]
    else:
        replay_p = input("Path to replay: ")

    replay_p = replay_p.strip("\"")

    print("Parsing", replay_p)

    with open(replay_p, "rb") as replay_f:
        replay_b = bytearray(replay_f.read())

    replay = Replay.parse(replay_b)

    dump_p = os.path.splitext(replay_p)[0] + ".txt"
    print("Dumping to", dump_p)

    print_to_file(dump_p, replay)
