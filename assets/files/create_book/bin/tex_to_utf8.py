#!/usr/bin/env python3

import sys
import latexcodec, codecs, unicodedata
import lxml.etree as etree, html
import re
import collections
import logging

Entry = collections.namedtuple('Entry', ['open', 'close', 'tag', 'type', 'verbatim'], defaults=[False])
table = [Entry('{', '}', None, 'bracket'),
         Entry('$', '$', 'tex-math', 'bracket', True),
         Entry(r'\(', r'\)', 'tex-math', 'bracket', True),
         Entry(r'\textit', None, 'i', 'unary'),
         Entry(r'\it', None, 'i', 'setter'),
         Entry(r'\emph', None, 'i', 'unary'), # or <em>?
         Entry(r'\em', None, 'i', 'setter'),  # or <em>?
         Entry(r'\textbf', None, 'b', 'unary'),
         Entry(r'\bf', None, 'b', 'setter'),
         #Entry(r'\textsc', None, 'sc', 'unary'),
         #Entry(r'\sc', None, 'sc', 'setter'),
         Entry(r'\url', None, 'url', 'unary', True),
         Entry(r'root', None, 'root', None),
]
openers = {e.open:e for e in table}
closers = {e.close:e for e in table if e.type == 'bracket'}
tags = {e.tag:e for e in table}
            
token_re = re.compile(r'\\[A-Za-z]+\s*|\\.|.', re.DOTALL)

def parse_latex(s):
    """Parse LaTeX into a list of lists."""
    toks = token_re.findall(s)
    toks = collections.deque(toks)
    stack = [['root']]

    def close_implicit():
        # Implicitly close setters
        top = stack.pop()
        open = top[0].rstrip()
        if open == '$':
            logging.warning("unmatched $, treating as dollar sign")
            stack[-1].extend(top)
        else:
            if openers[open].type != 'setter':
                logging.warning("closing unmatched {}".format(open))
            stack[-1].append(top)

    math_mode = False
    while len(toks) > 0:
        tok = toks.popleft()
        tokr = tok.rstrip()

        if (tokr in openers and
            openers[tokr].type in ['bracket', 'setter'] and
            (tokr != '$' or not math_mode)):
            stack.append([tok])
            
        elif (tokr in closers and
              (tokr != '$' or math_mode)):
            open = stack[-1][0].rstrip()
            while open != closers[tokr].open:
                close_implicit()
                open = stack[-1][0].rstrip()
            top = stack.pop()
            stack[-1].append(top)
            
        else:
            stack[-1].append(tok)

        if tokr == '$':
            math_mode = not math_mode
        
        if len(stack[-1]) >= 3 and isinstance(stack[-1][-2], str):
            prev = stack[-1][-2].rstrip()
            if prev in openers and openers[prev].type == 'unary':
                last = stack[-1].pop()
                node = stack[-1].pop()
                stack[-1].append([node, last])

    while len(stack) > 1:
        close_implicit()
        
    return stack[0]

def unparse_latex(l):
    """Inverse of parse_latex."""
    def visit(l):
        if isinstance(l, str):
            return l
        elif isinstance(l, list):
            open = l[0].rstrip()
            close = openers[open].close or ''
            return ''.join(map(visit, l)) + close
    return ''.join(map(visit, l[1:]))

trivial_math_re = re.compile(r'@?[\d.,]*(\\%|%)?')

def xmlify_string(s):
    out = []
    
    def visit(node):
        if isinstance(node, str):
            out.append(node)
            return
        
        open = node[0].rstrip()
        tag = openers[open].tag
        if openers[open].verbatim:
            # Delete outer pair of braces if any, so that
            # \url{...} doesn't print braces
            if (len(node) == 2 and
                isinstance(node[1], list) and
                node[1][0] == '{'):
                node[1:] = node[1][1:]
            text = unparse_latex(node)
            
            # I don't know if this really belongs here, but there are some
            # formulas that should just be plain text
            if tag == 'tex-math' and trivial_math_re.fullmatch(text):
                out.append(text)
            else:
                out.append('<{}>{}</{}>'.format(tag, text, tag))
        else:
            if tag is None:
                close = openers[open].close
            elif tag == 'root':
                open = close = ''
            else:
                open, close = '<{}>'.format(tag), '</{}>'.format(tag)
            out.append(open)
            for child in node[1:]:
                visit(child)
            out.append(close)

    visit(parse_latex(s))
    return ''.join(out)

def unicodify_string(s):
    # BibTeX sometimes has HTML escapes
    #s = html.unescape(s)

    # Do a few conversions in the reverse direction first
    # We don't want unescaped % to be treated as a comment character, so escape it
    s = re.sub(r'(?<!\\)%', r'\%', s)

    # Use a heuristic to escape some ties (~)
    s = re.sub(r'(?<=[ (])~(?=\d)', r'\\textasciitilde', s)
    
    s = s.replace('–', '--') # an old bug converts --- to –-; this undoes it
    s = s.replace(r'\&', '&amp;') # to avoid having an unescaped & in the output
    
    # A group with a single char should be equivalent to the bare char.
    # Also, this avoids a latexcodec bug for \"{\i}, etc.
    s = re.sub(r'(\\[A-Za-z]+ |\\.)\{([.]|\\i)}', r'\1\2', s)
    
    leading_space = len(s) > 0 and s[0].isspace()
    s = codecs.decode(s, "ulatex+utf8")
    if leading_space: s = " " + s

    # It's easier to deal with control sequences if followed by a space.
    s = re.sub(r'(\\[A-Za-z]+)\s*', r'\1 ', s)

    # Missed due to bugs in latexcodec
    s = s.replace("---", '—')
    s = s.replace("--", '–')
    s = s.replace("``", '“')
    s = s.replace("''", '”')
    s = re.sub(r'(?<!\\)~', ' ', s)
    # In latest version of latexcodec, but not the one I have
    s = re.sub(r'\\r ([Aa])', '\\1\u030a', s)   # ring
    # Not in latexcodec yet
    s = re.sub(r'\\cb ([SsTt])', '\\1\u0326', s) # comma-below
    s = s.replace(r'\dh ', 'ð')
    s = s.replace(r'\DH ', 'Ð')
    s = s.replace(r'\th ', 'þ')
    s = s.replace(r'\TH ', 'Þ')
    s = s.replace(r'\textregistered ', '®')
    s = s.replace(r'\texttrademark ', '™')
    s = s.replace(r'\textasciigrave ', "‘")
    s = s.replace(r'\textquotesingle ', "’")

    # Normalize some characters
    s = s.replace('\u00ad', '') # soft hyphen
    # NFKC normalization would get these, but also others we don't want
    s = s.replace('ﬁ', 'fi') 
    s = s.replace('ﬂ', 'fl')
    s = s.replace('ﬀ', 'ff')
    s = s.replace('ﬃ', 'ffi')
    s = s.replace('ﬄ', 'ffl')
    
    s = s.replace(r'\$', '$')
    
    # Double quotes
    # If preceded by a word (possibly with intervening
    # punctuation), it's a right quote.
    s = re.sub(r'(\w[^\s"]*)"', r'\1”', s)
    # Else, if followed by a word, it's a left quote
    s = re.sub(r'"(\w)', r'“\1', s)

    # Single quotes
    s = s.replace("`", '‘')
    # Exceptions for apostrophe at start of word
    s = re.sub(r"'(em|round|n|tis|twas|cause|scuse|\d0s)\b", r'’\1', s, flags=re.IGNORECASE)
    s = re.sub(r"(\w[^\s']*)'", r'\1’', s)
    s = re.sub(r"'(\w)", r'‘\1', s)
    
    # Convert combining characters when possible
    s = unicodedata.normalize('NFC', s)

    # Clean up remaining curly braces
    s = re.sub(r'(?<!\\)[{}]', '', s)
    s = re.sub(r'\\([{}])', r'\1', s)

    def repl(m):
        logging.warning("deleting remaining control sequence {}".format(m.group(1)))
        return ""
    s = re.sub(r'(\\[A-Za-z]+\s*|\\.)', repl, s)
    
    return s

def unicodify_node(t):
    """Convert all text in XML tree from LaTeX to Unicode. Destructive."""
    def visit(node):
        if node.tag in tags and tags[node.tag].verbatim:
            return
        if node.text is not None:
            node.text = unicodify_string(node.text)
        for child in node:
            visit(child)
            if child.tail is not None:
                child.tail = unicodify_string(child.tail)
    visit(t)

def convert_string(s, tags=False):
    if tags:
        s = html.escape(s)
        s = xmlify_string(s)
        s = "<root>{}</root>".format(s)
        t = xml_fromstring(s)
        unicodify_node(t)
        return xml_tostring(t, delete_root=True)
    else:
        return unicodify_string(s)

def convert_node(t, tags=False):
    """Converts an XML node. Nondestructive."""
    if tags:
        # This roundabout path handles things like \emph{foo <b>bar</b> baz} correctly
        s = xml_tostring(t)
        s = xmlify_string(s)
        t = xml_fromstring(s)
    unicodify_node(t)
    return t

def xml_tostring(t, delete_root=False):
    if delete_root:
        out = []
        if t.text is not None:
            out.append(html.escape(t.text))
        for child in t:
            out.append(xml_tostring(child))
            if child.tail is not None:
                out.append(html.escape(child.tail))
        return ''.join(out)
    else:
        return etree.tostring(t, with_tail=False, encoding='utf8').decode('utf8')

def xml_fromstring(s):
    try:
        t = etree.fromstring(s)
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logging.error("XML parser raised exception {}".format(e))
        logging.debug(s)
        t = etree.Element('error')
    return t
    
def replace_node(old, new):
    save_tail = old.tail
    old.clear()
    old.tag = new.tag
    old.attrib.update(new.attrib)
    old.text = new.text
    old.extend(new)
    old.tail = save_tail

if __name__ == "__main__":
    import sys
    import argparse
    
    ap = argparse.ArgumentParser(description='Convert LaTeX to Unicode (and some XML).')
    ap.add_argument('infile', nargs='?', help="file to read (default stdin)")
    ap.add_argument('-o', '--outfile', help="file to write (default stdout)")
    ap.add_argument('-f', '--format', default='plain', choices=['plain', 'db', 'meta', 'xml', 'start'], help="file format")
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

    if args.format == 'xml':
        root = etree.parse(infile).getroot()
        for paper in root.findall('paper'):
            fullid = "{}-{}".format(root.attrib['id'], paper.attrib['id'])
            for oldnode in paper:
                location = "{}:{}".format(fullid, oldnode.tag)

                if oldnode.tag in ['url', 'href', 'mrf', 'doi', 'bibtype', 'bibkey',
                                   'revision', 'erratum', 'attachment', 'paper',
                                   'presentation', 'dataset', 'software', 'video']:
                    continue

                newnode = convert_node(oldnode, True)

                oldstring = xml_tostring(oldnode)
                oldstring = " ".join(oldstring.split())
                newstring = xml_tostring(newnode)
                newstring = " ".join(newstring.split())

                if newstring != oldstring:
                    replace_node(oldnode, newnode)

        print(etree.tostring(root, encoding="UTF-8", xml_declaration=True, with_tail=True).decode("utf8"))

    else:
        for li, line in enumerate(infile):
            location = li+1
            line = line.rstrip()

            if args.format == 'plain':
                print(convert_string(line, True))
                
            elif args.format == 'db':
                m = re.fullmatch(r'([A-Z]):\s*(.*)', line)
                if m and m.group(1) in "AHOST":
                    newvalue = convert_string(m.group(2), True)
                    print("{}: {}".format(m.group(1), newvalue))
                else:
                    print(line)

            elif args.format == 'meta':
                m = re.fullmatch(r'(\S+)\s+(.*)', line)
                if m and m.group(1) not in ['url', 'bib_url']:
                    newvalue = convert_string(m.group(2), True)
                    print("{} {}".format(m.group(1), newvalue))
                else:
                    print(line)

            elif args.format == 'start':
                # This is currently not used, but is here just in case
                # we want db files to contain Unicode instead of TeX
                m = re.fullmatch(r'(.*)(#=%?=#)(.*)', line)
                if m and not re.fullmatch(r'Author\{\d+}\{Email}', m.group(1)):
                    key, sep, oldvalue = m.groups()
                    newvalue = convert_string(oldvalue, True)
                    print("{}{}{}".format(key, sep, newvalue))
                else:
                    print(line)
