"""
Convert CoNLL output of a dependency parser into a latex or graphviz tree.

Dependency parsers that uses the CoNLL parser includes:

- CoreNLP (for multiple languages)
- StanfordNLP (for multiple languages)
- Talismane (for French)
- MindTheGap (for French)
- ...

There are two modes: Latex or Graphviz.  With the **Latex mode**, all the
sentences will be in a file, each on its own page.  The script produces a
`.tex` file, named according to the -o option, which is compiled if the `-c`
switch is set (otherwise, just run `pdflatex|lualatex <file>.tex`).  To
activate this mode, you must use the the `-l` swith or the `-m latex` option:

For example:

    python3 dependency2tree.py -l -o <output.tex> -c <input.conll>

or

    python3 dependency2tree.py -l -o <output.tex> <input.conll>
    pdflatex output.tex # or lualatex

This will produces a `output.pdf` file containing your trees.


In the GraphViz mode (the default mode), each sentence is in its own file.  If
you don't want to compile, you can get graphviz files with:

    python3 dependency2tree.py -o <output.gv> -c <input.conll>

You will get `output-001.gv`, `output-002.gv`, etc. for each sentence. You can
run `dot` to get image files (replace svg by the format you want):

    dot -Tsvg output-001.gv > output-001.svg

If you want to compile automatically with the `-c` swith, just adjust the
output file extension to `svg` (or `png`, etc.) instead of `gv`:

    python3 dependency2tree.py -o <output.svg> -c <input.conll>

This will get you `output-001.svg`, `output-002.svg`, etc.  You can change the
image format (`png`, etc.) with `-f` option:

    python3 dependency2tree.py -o <output.png> -c -f png <input.conll>

"""

# Bruno Oberle, Mozilla Public Licence 2.0

import argparse
import subprocess
import os

MODE_LATEX = 1
MODE_GRAPHVIZ = 2


class GraphvizCompiler:

    def __init__(self, command, img_format="svg"):
        self.command = command
        self.img_format = img_format

    def compile(self, code, output_file):
        cmd = [self.command, '-T%s' % self.img_format]
        print("running command `%s`" % " ".join(cmd))
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)
        res = proc.communicate(input=code.encode())[0] # res is bytes (unless
            # univeral_newlines)
        print("writing %s" % output_file)
        open(output_file, 'wb').write(res)



class Token:

    def __init__(self, index, form, lemma, pos, feats, head, deplabel):
        self.index = index
        self.form = form
        self.lemma = lemma
        self.pos = pos
        self.feats = feats.replace("|", ", ")
        self.head = head
        self.deplabel = deplabel



class Sentence:

    def __init__(self, tokens):
        self.tokens = tokens

    def convert_to_latex(self, include_feats):
        res = "\\begin{center}" \
            + "\\begin{tikzpicture}" \
            + "\\tikzset{level distance=60pt}" \
            + "\\tikzset{every tree node/.style={align=center,anchor=north}}" \
            + "\\Tree "
        children = self.get_children_of(0)
        if len(children) > 1:
            res += "[ "
        for root in children:
            res += self._token2latex(root, include_feats)
        if len(children) > 1:
            res += "] "
        res += "\\end{tikzpicture}" \
            + "\\end{center}\n" \
            + "\\clearpage"
        res = res.replace("_", "-")
        return res

    def _token2latex(self, token, include_feats):
        feats = "\\\\ {\\tiny %s}" % token.feats \
            if include_feats and token.feats else ""
        res = "[.{%s\\\\%s (%s)%s} " % (token.deplabel,
            token.form, token.pos, feats)
        for child in self.get_children_of(token.index):
            res += self._token2latex(child, include_feats)
        res += " ]"
        return res

    def convert_to_graphviz(self, include_feats):
        res = "digraph tree {\n"
        for root in self.get_children_of(0):
            res += self._token2graphviz(root, include_feats)
        return res + "}"

    def _token2graphviz(self, token, include_feats):
        res = 'n%d [label="%s\\n%s (%s)%s"];\n' % (token.index,
            *(s.replace('"', "&quot;") for s in (token.form, token.pos,
            token.deplabel, ("\\n%s" % token.feats) if include_feats and
            token.feats else "")))
        if self.has_children(token.index):
            res += 'n%d -> {%s};\n' % (token.index,
                " ".join("n%d" % c.index for c
                in self.get_children_of(token.index)))
        for child in self.get_children_of(token.index):
            res += self._token2graphviz(child, include_feats)
        return res

    def get_children_of(self, index):
        return [t for t in self.tokens if t.head == index]

    def has_children(self, index):
        for t in self.tokens:
            if t.head == index:
                return True
        return False



class ConllFile:

    def __init__(self, filename, ignore_double_indices=False):
        self.filename = filename
        self.sentences = []
        self.ignore_double_indices = ignore_double_indices

    def read(self):
        tokens = []
        for line in open(self.filename):
            line = line.strip()
            if not line:
                if tokens:
                    self.sentences.append(Sentence(tokens))
                    tokens = []
                continue
            split = line.split("\t")
            if self.ignore_double_indices and "-" in split[0]:
                continue
            # ID FORM LEMMA CPOSTAG POSTAG FEATS HEAD DEPREL PHEAD PDEPREL
            token = Token(
                index=int(split[0]),
                form=split[1],
                lemma=split[2],
                pos=split[3],
                feats=split[5],
                head=int(split[6]),
                deplabel=split[7])
            tokens.append(token)
        if tokens:
            self.sentences.append(Sentence(tokens))

    def write_graphviz(self, output_file, gv_compiler, include_feats):
        self.read()
        count = 1
        for sent in self.sentences:
            code = sent.convert_to_graphviz(include_feats)
            if output_file:
                base, ext = os.path.splitext(output_file)
                filename = base + "-%03d" % count + ext
                count += 1
                if gv_compiler:
                    gv_compiler.compile(code, filename)
                else:
                    print("writing %s" % filename)
                    open(filename, 'w').write(code)
            else:
                print(code)

    def write_latex(self, output_file, command, include_feats):
        self.read()
        code = "\\documentclass[10pt,landscape]{article}\n" \
            + "\\usepackage[a2paper,margin=1cm]{geometry}\n" \
            + "\\usepackage{fontspec}\n" \
            + "\\defaultfontfeatures{Ligatures=TeX}\n" \
            + "\\setmainfont[BoldFont={Gentium Basic-bold}, BoldItalicFont={Gentium Basic-bold-italic}, SmallCapsFont={Linux Libertine Capitals O}]{Gentium}\n" \
            + "\\usepackage{tikz}\n" \
            + "\\usepackage{tikz-qtree}\n" \
            + "\\pagestyle{empty}\n" \
            + "\\begin{document}\n\n"
        for sent in self.sentences:
            code += sent.convert_to_latex(include_feats) + "\n\n"
        code += "\\end{document}\n"
        if output_file:
            print("writing %s" % output_file)
            open(output_file, 'w').write(code)
            if command:
                subprocess.run([command, output_file], check=True)
        else:
            print(code)


def parse_args():
    # definition
    parser = argparse.ArgumentParser(
        prog="dependency2tree.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # arguments (not options)
    parser.add_argument("input_file", default="", help="conll file")
    # options
    parser.add_argument("-o", "--output", dest="output_file",
        default="", help="output file")
    parser.add_argument("-m", "--mode", dest="mode", choices=['latex',
        'graphviz'], default='graphviz', help="default is 'graphviz'")
    parser.add_argument("-l", "--latex", dest="latex_mode", default=False,
        action="store_true", help="shortcut for '-m latex'")
    parser.add_argument("--feats", dest="include_feats", default=False,
        action="store_true", help="include features")
    parser.add_argument("-c", "--compile", dest="compile", default=False,
        action="store_true", help="compile using --cmd")
    parser.add_argument("--ignore-double-indices", dest="ignore_double_indices",
        default=False, action="store_true",
        help="ignore tokens with a hyphen in the index (specific to "
        "some corpora for managing amalgams)")
    parser.add_argument("--cmd", dest="command", default="",
        help="the command use to compile (if --compile); default is "
        "'dot' if --mode is 'graphviz', 'lualatex' if --mode is 'latex'")
    parser.add_argument("-f", "--img-format", dest="img_format", default="svg",
        help="the img format used when compiling with graphviz; default is svg")
    # parsing
    args = parser.parse_args()
    if args.latex_mode:
        args.mode = 'latex'
    args.mode = MODE_LATEX if args.mode == 'latex' else MODE_GRAPHVIZ
    if args.compile and not args.command:
        args.command = 'lualatex' if args.mode == MODE_LATEX else 'dot'
    if args.compile and not args.output_file:
        raise RuntimeError(
            "you need to specify an output file when using the -c switch")
    return args



def main():
    args = parse_args()
    conll_file = ConllFile(
        args.input_file,
        ignore_double_indices=args.ignore_double_indices
    )
    if args.mode == MODE_LATEX:
        conll_file.write_latex(args.output_file, command=args.command,
            include_feats=args.include_feats)
    else:
        if args.compile:
            gv_compiler = GraphvizCompiler(command=args.command,
                img_format=args.img_format)
        else:
            gv_compiler = None
        conll_file.write_graphviz(args.output_file, gv_compiler=gv_compiler,
            include_feats=args.include_feats)



if __name__ == '__main__':
    main()
