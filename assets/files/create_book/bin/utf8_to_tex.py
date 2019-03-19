#!/usr/bin/env python3

import latexcodec, codecs, unicodedata
import re
import fileinput
import logging

# A few cases that latexcodec doesn't have yet
table = {
    'Ș': '\cb S',
    'ș': '\cb s',
    'Ț': '\cb T',
    'ț': '\cb t',
}

def convert_string(s):
    s = unicodedata.normalize('NFC', s)
    out = []
    for c in s:
        if c in table:
            c1 = table[c]
        else:
            try:
                c1 = codecs.encode(c, "ulatex")
            except KeyboardInterrupt:
                raise
            except:
                logging.warning("couldn't convert {} to TeX".format(c))
                c1 = c
                
        # Wrap every special character in curly braces, because
        # - BibTeX wants it (including @)
        # - the latexcodec decoder likes '{\o} {\o}' but not '\o\ \o'
        if c1.startswith('\\') or c1 == '@':
            c1 = '{' + c1 + '}'
        # Undo conversions that result in math
        elif c1.startswith('$') and c1 != c:
            c1 = c
        out.append(c1)
    return ''.join(out)

if __name__ == "__main__":
    import sys
    import argparse
    
    ap = argparse.ArgumentParser(description='Convert Unicode (and some XML tags) to LaTeX.')
    ap.add_argument('infile', nargs='?', help="file to read (default stdin)")
    ap.add_argument('-o', '--outfile', help="file to write (default stdout)")
    ap.add_argument('-f', '--format', default='plain', choices=['plain', 'start'], help="file format")
    args = ap.parse_args()

    # Set up logging
    logging.basicConfig(format='%(levelname)s:%(location)s %(message)s', level=logging.WARNING)
    location = ""
    def filter(r):
        r.location = location
        return True
    logging.getLogger().addFilter(filter)
    
    infile = open(args.infile) if args.infile else sys.stdin
    outfile = open(args.outfile) if args.outfile else sys.stdout

    for li, line in enumerate(infile):
        location = li+1
        line = line.rstrip()
        newvalue = None
        
        if args.format == 'plain':
            oldvalue = line
            newvalue = convert_string(oldvalue)
            print(newvalue)
            
        elif args.format == 'start':
            m = re.fullmatch(r'(.*)(#=%?=#)(.*)', line)
            if m and not re.fullmatch(r'Author\{\d+}\{Email}', m.group(1)):
                key, sep, oldvalue = m.groups()
                newvalue = convert_string(oldvalue)
                print("{}{}{}".format(key, sep, newvalue))
        
