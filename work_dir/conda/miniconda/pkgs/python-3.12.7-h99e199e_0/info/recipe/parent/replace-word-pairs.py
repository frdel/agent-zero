import sys
import re

# Reads from stdin line by line, writes to stdout line by line replacing
# each odd argument with the subsequent even argument.

def pairs(it):
    it = iter(it)
    try:
        while True:
            yield next(it), next(it)
    except StopIteration:
        return

def main():
    rep_dict = dict()
    for fro, to in pairs(sys.argv[1:]):
        rep_dict[fro] = to
    if len(rep_dict):
        regex = re.compile("(%s)" % "|".join(map(re.escape, rep_dict.keys())))
        for line in iter(sys.stdin.readline, ''):
            sys.stdout.write(regex.sub(lambda mo: rep_dict[mo.string[mo.start():mo.end()]], line))
    else:
        for line in iter(sys.stdin.readline, ''):
            sys.stdout.write(line)


if __name__ == '__main__':
    main()
