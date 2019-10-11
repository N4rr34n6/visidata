import re
import random

from visidata import asyncthread, warning, option, options, vd
from visidata import BaseSheet, Sheet, Column, Progress

Sheet.addCommand(':', 'split-col', 'addRegexColumns(makeRegexSplitter, sheet, cursorColIndex, cursorCol, input("split regex: ", type="regex-split"))')
Sheet.addCommand(';', 'capture-col', 'addRegexColumns(makeRegexMatcher, sheet, cursorColIndex, cursorCol, input("match regex: ", type="regex-capture"))')
Sheet.addCommand('*', 'addcol-subst', 'addColumn(Column(cursorCol.name + "_re", getter=regexTransform(cursorCol, input("transform column by regex: ", type="regex-subst"))), cursorColIndex+1)')
Sheet.addCommand('g*', 'setcol-subst', 'setSubst([cursorCol], selectedRows)')
Sheet.addCommand('gz*', 'setcol-subst-all', 'setSubst(visibleCols, selectedRows)')

@Sheet.api
def setSubst(sheet, cols, rows):
    if not rows:
        warning('no %s selected' % sheet.rowtype)
        return
    modified = 'column' if len(cols) == 1 else 'columns'
    rex = vd.input("transform %s by regex: " % modified, type="regex-subst")
    setValuesFromRegex(cols, rows, rex)


option('regex_flags', 'I', 'flags to pass to re.compile() [AILMSUX]', replay=True)
option('regex_maxsplit', 0, 'maxsplit to pass to regex.split', replay=True)
option('default_sample_size', 100, 'number of rows to sample for regex.split', replay=True)

def makeRegexSplitter(regex, origcol):
    return lambda row, regex=regex, origcol=origcol, maxsplit=options.regex_maxsplit: regex.split(origcol.getDisplayValue(row), maxsplit=maxsplit)

def makeRegexMatcher(regex, origcol):
    return lambda row, regex=regex, origcol=origcol: regex.search(origcol.getDisplayValue(row)).groups()

@asyncthread
def addRegexColumns(regexMaker, vs, colIndex, origcol, regexstr):
    regex = re.compile(regexstr, vs.regex_flags())

    func = regexMaker(regex, origcol)

    n = options.default_sample_size
    if n and n < len(vs.rows):
        exampleRows = random.sample(vs.rows, max(0, n-1))  # -1 to account for included cursorRow
    else:
        exampleRows = vs.rows

    ncols = 0  # number of new columns added already
    for r in Progress(exampleRows + [vs.cursorRow]):
        for _ in range(len(func(r))-ncols):
            c = Column(origcol.name+'_re'+str(ncols),
                            getter=lambda col,row,i=ncols,func=func: func(row)[i],
                            origCol=origcol)
            vs.addColumn(c, index=colIndex+ncols+1)
            ncols += 1


def regexTransform(origcol, instr):
    i = indexWithEscape(instr, '/')
    if i is None:
        before = instr
        after = ''
    else:
        before = instr[:i]
        after = instr[i+1:]
    return lambda col,row,origcol=origcol,before=before,after=after,flags=origcol.sheet.regex_flags(): re.sub(before, after, origcol.getDisplayValue(row), flags=flags)

def indexWithEscape(s, char, escape_char='\\'):
    i=0
    while i < len(s):
        if s[i] == escape_char:
            i += 1
        elif s[i] == char:
            return i
        i += 1

    return None


@asyncthread
def setValuesFromRegex(cols, rows, rex):
    transforms = [regexTransform(col, rex) for col in cols]
    vd.addUndoSetValues(cols, rows)
    for r in Progress(rows, 'replacing'):
        for col, transform in zip(cols, transforms):
            col.setValueSafe(r, transform(col, r))
    for col in cols:
        col.recalc()


@BaseSheet.api
def regex_flags(sheet):
    'Return flags to pass to regex functions from options'
    return sum(getattr(re, f.upper()) for f in options.regex_flags)
