from textwrap import dedent
from argparse import ArgumentParser, RawDescriptionHelpFormatter

import subprocess
import pyPdf
import sys
import os
import re
import tempfile
import shutil
import argparse
import struct
import StringIO

viewer = "evince"
texcomp = "pdflatex"

##
# convert millimeters to postscript points
#
def mmToPt(mm):
    return 2.83464567 * mm

##
# create a one-page pdf (blank) with the specified size (postscript points)
#
def create_pdf_empty(width, height):
    output = StringIO.StringIO()

    output.write('%PDF-1.1\n')
    output.write('%\xc3\xad\xc3\xac\xc2\xa6"\n')
    output.write('\n')

    catalog = output.tell()
    output.write('1 0 obj\n')
    output.write('<< /Type /Catalog /Pages 2 0 R >>\n')
    output.write('endobj\n')

    pages = output.tell()
    output.write('2 0 obj\n')
    output.write('<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 %f %f] >>\n' % (width, height))
    output.write('endobj\n')

    page = output.tell()
    output.write('3 0 obj\n')
    output.write('<< /Type /Page /Parent 2 0 R /Resources << >> /Contents [] >>\n')
    output.write('endobj\n')

    xref = output.tell()
    output.write('xref\n')
    output.write('0 4\n')
    output.write('0000000000 65535 f \n')
    for offset in (catalog, pages, page):
        output.write('%010d 00000 n \n' % offset)
    output.write('trailer << /Root 1 0 R /Size 4 >>\n')
    output.write('startxref\n')
    output.write('%d\n' % xref)
    output.write('%%EOF\n')

    return output


##
# create a one-page pdf (A4) with specified content on the page.
#
def create_pdf(content):
    output = StringIO.StringIO()

    output.write('%PDF-1.5\n')
    output.write('%\xc3\xad\xc3\xac\xc2\xa6"\n')

    pages = output.tell()
    output.write('1 0 obj\n')
    output.write('<< /Kids [2 0 R] /Count 1 /Type /Pages >>\n')
    output.write('endobj\n')

    resources = output.tell()
    output.write('3 0 obj\n')
    output.write('<< >>\n')
    output.write('endobj\n')

    data = output.tell()
    output.write('4 0 obj\n')
    output.write('<< /Length %d >>\n' % (4 + len(content)))
    output.write('stream\n')
    output.write('q\n')
    output.write('Q\n')
    output.write(content)
    output.write('\n')
    output.write('endstream\n')
    output.write('endobj\n')

    page = output.tell()
    output.write('2 0 obj\n')
    output.write('<< /Group  << /CS /DeviceRGB /Type /Group /S /Transparency >> /Parent 1 0 R /Resources 3 0 R /MediaBox [0 0 841.889764 595.275591] /Contents 4 0 R /Type /Page >>\n')
    output.write('endobj\n')

    catalog = output.tell()
    output.write('5 0 obj\n')
    output.write('<< /Pages 1 0 R /Type /Catalog >>\n')
    output.write('endobj\n')

    creator = output.tell()
    output.write('6 0 obj\n')
    output.write('<< /Creator (mkbooklet http://github.com/pb-/mkbooklet) /Producer (mkbooklet http://github.com/pb-/mkbooklet) >>\n')
    output.write('endobj\n')

    xref = output.tell()
    output.write('xref\n')
    output.write('0 7\n')
    output.write('0000000000 65535 f \n')
    for offset in (pages, page, resources, data, catalog, creator):
        output.write('%010d 00000 n \n' % offset)
    output.write('trailer\n')
    output.write('\n')
    output.write('<< /Info 6 0 R /Root 5 0 R /Size 7 >>\n')
    output.write('startxref\n')
    output.write('%d\n' % xref)
    output.write('%%EOF')

    return output

##
# generate a page with staple guides suitable for long-arm staplers.
#
def generate_guides_longarm():
    width = 1
    content = '2.83464567 0 0 2.83464567 0 0 cm 0.1 w 1 0 0 1 148.5 21 cm\n'

    for i in range(5):
        if i != 0:
            content += '1 0 0 1 0 42 cm\n'

        content += '-%d 0 m\n' % width
        content += '%d 0 l\n' % (2 * width)
        content += 's\n'

    return create_pdf(content)

##
# generate a page with staple guides.
# @param a5mode If true, sets the guides further away from the margin
# @param right Set the guides on the right half of the page (as opposed to left)
#
def generate_guides(num, a5mode, right):
    vmargin = 6
    hmargin = 5 if a5mode else 2.5
    if a5mode:
        x = hmargin
    if right:
        x = 148.5 + hmargin
    else:
        x = 148.5 - hmargin

    content = '2.83464567 0 0 2.83464567 0 0 cm 0.1 w 1 0 0 1 %f %d cm\n' % (x, vmargin)

    n = num
    h = 12 # mm
    sp = float(210 - h - 2*vmargin)/(n-1) 

    sign = ' ' if (a5mode or right) else '-'

    for i in range(n):
        if i != 0:
            content += "1 0 0 1 0 %f cm\n" % sp

        # vertical bar
        content += '0 0 m\n'
        content += '0 %d l\n' % h
        content += 's\n'

        content += '0 2 m\n'
        content += '%c2 2 l\n' % sign
        content += 's\n'

        content += '0 10 m\n'
        content += '%c2 10 l\n' % sign
        content += 's\n'

    return create_pdf(content)

##
# obtain the true bounding box for printed data of the given pdf file.
#
def pdfbbox(filename):
    f = pyPdf.PdfFileReader(file(filename, 'rb'))
    pages = f.getNumPages()

    sizes = []

    for i in range(pages):
        p = f.getPage(i)
        sizes.append((int(round(p.mediaBox.getUpperRight_x() - p.mediaBox.getLowerLeft_x())), int(round(p.mediaBox.getUpperRight_y() - p.mediaBox.getLowerLeft_y()))))

    proc = subprocess.Popen(['/usr/bin/gs', '-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=bit', '-sOutputFile=%stdout', filename], stdout=subprocess.PIPE)

    bboxs = []

    for s in sizes:
        (w,h) = s
        bbox = (w-1, h-1, 0, 0)

        row_len = w / 8
        if w % 8 > 0:
            row_len += 1

        fmt = 'b' * row_len

        for y in range(h-1, -1, -1):
            row = proc.stdout.read(row_len)
            row = struct.unpack(fmt, row)
            # use low resolution for x-positions. this is
            # substantially faster and comes with an error
            # of at most 8pt \approx 2.8mm
            for x in range(0, w / 8):
                if row[x] != 0:
                    bbox = (
                        min(bbox[0], x * 8),
                        min(bbox[1], y),
                        max(bbox[2], x * 8 + 8),
                        max(bbox[3], y + 2),
                    )

        if bbox[0] < bbox[2] and bbox[1] < bbox[3]:
            bboxs.append(tuple(bbox))

    return bboxs


##
# compute the page sequence for signature binding
# @param pages number of pages in total
# @param max_sig_sheets maximum number of sheets per signature
#
def make_sig_sequence(pages, max_sig_sheets=5):
    def pg(k,n,o):
        return '{}' if k > n else str(k+o)

    sequence = []
    max_sig_size = max_sig_sheets * 4
    sigs = pages // max_sig_size + min(1, pages % max_sig_size)
    for s in range(sigs):
        off = s * max_sig_size
        sig_size = min(max_sig_size, pages - off)
        sig_sheets = sig_size // 4 + min(1, sig_size % 4)

        print s, off, sig_size, sig_sheets

        for ss in range(sig_sheets):
            sequence.append(pg(sig_sheets*4 - 2*ss, sig_size, off))
            sequence.append(pg(2*ss+1, sig_size, off))
            sequence.append(pg(2*ss+2, sig_size, off))
            sequence.append(pg(sig_sheets*4 - 2*ss - 1, sig_size, off))

    return ','.join(sequence)



def median(l):
    l.sort()
    return l[len(l)/2]

class Mkbooklet(object):
    a4lheight = 595
    a4lwidth = 841
    a5height = 595
    a5width = 419

    def parse_args(self, args):
        epilog = dedent("""\
            Inner and outer margins have the following meanings.

            +---------------+
            |###############|
            |#    @@:@@    #|
            |# P1 @@:@@ P2 #|
            |#    @@:@@    #|
            |###############|
            +---------------+

            '#' is the outer margin (both dimensions) along the outline of
                the phyiscal paper.
            '@' is the inner fold margin (horizontally) between the actual
                content and the center of the paper indicated by ':'.
        """)

        parser = ArgumentParser(
            description='Prepare PDF files for booklet printing.',
            formatter_class=RawDescriptionHelpFormatter, epilog=epilog)

        a = parser.add_argument

        a('--version', action='version', version='%(prog)s 1.0.0')
        a('-5', '--a5', action='store_true',
          help='produce single A5 pages instead of 2-up A4')
        a('-C', '--croponly', action='store_true',
          help='only crop the input file, do not create a booklet')
        a('-S', '--signature', dest='signature', type=int,
          help='use at most given number of sheets for one signature instead '
               'of producing one big signature')
        a('-b', '--bbox', help='use given bounding box, specified as either '
                               'x1,y1,x2,y2 or x,y+w,h')
        a('-c', '--nocrop', action='store_true',
          help='do not crop the input file')
        a('-e', '--extrapages', dest='epages', default=0, type=int,
          help='add given number of extra blank pages at '
               'the end of the document')
        a('-g', '--noguides', action='store_true',
          help='do not apply any guides on the first page')
        a('-i', '--inner-margins', dest='imargins', default='default',
          type=str, help='use given value (unit: millimeters) for the minimal '
                         'inner (fold)margins, see below')
        a('-l', '--longarm', action='store_true',
          help='generate staple guides for long-arm staplers')
        a('-o', '--outer-margins', dest='margins', default='default', type=str,
          help='use given value (unit: millimeters) for the minimal '
               'outer margins, see below')
        a('-p', '--bboxpage', dest='bboxpage', type=int,
          help='use given page number to obtain the bounding box')
        a('-s', '--smartbbox', action='store_true',
          help='use the median algorithm when obtaining the bbox')
        a('filename')

        self.args = parser.parse_args()
        self.pdf_in = os.path.abspath(self.args.filename)

        self.args.margins = 6 if self.args.margins == 'default' else int(self.args.margins)
        if self.args.imargins == 'default':
            if self.args.a5:
                self.args.imargins = 16
            else:
                self.args.imargins = 22
        else:
            self.args.imargins = int(self.args.imargins)

        if not self.args.a5:
            self.args.imargins = 2 * (self.args.imargins - self.args.margins)

        self.args.margins = int(round(mmToPt(self.args.margins)))
        self.args.imargins = int(round(mmToPt(self.args.imargins)))

    def setup_tmpdir(self):
        self.tmpdir = tempfile.mkdtemp(prefix='mkbooklet-')
        os.chdir(self.tmpdir)

    def cleanup_tmpdir(self):
        shutil.rmtree(self.tmpdir)

    def crop(self):
        if not self.args.bbox:
            # determine actual (printed) bounding box
            bbox = pdfbbox(self.pdf_in)

            if self.args.bboxpage:
                bbox = bbox[self.args.bboxpage-1]
            elif self.args.smartbbox:
                bboxs = [None] * 4
                for i in range(4):
                    bboxs[i] = median(map(lambda x: x[i], bbox))
                bbox = tuple(bboxs)
            else:
                bbox = reduce(lambda x, y: (min(x[0], y[0]), min(x[1], y[1]), max(x[2], y[2]), max(x[3], y[3])), bbox)
        else:
            # x1,y1,x2,y2
            # x,y+w,h
            m = re.match('^(\\d+),(\\d+)(,|\\+)(\\d+),(\\d+)$', self.args.bbox)
            if not m:
                print 'Invalid bbox format, use x1,y1,x2,y2 or x,y+w,h'
                self.tearDown()
                sys.exit(-1)
            else:
                bbox = (int(m.group(1)), int(m.group(2)), int(m.group(4)), int(m.group(5)))
                if m.group(3) == '+':
                    bbox = (bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3])

        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        if not self.args.a5:
            maxw = (self.a4lwidth - self.args.imargins - 4 * self.args.margins) / 2
            maxh = self.a4lheight - 2 * self.args.margins
            s = float(maxw) / w
            if s * h > maxh:
                # exceeds height, scaling will free up more horizontal space. make sure we use this space where it makes sense (i.e., on the folding edge)
                s = float(maxh) / h
                self.args.imargins = int(self.a4lwidth - s * w * 2 - 4 * self.args.margins) 

            sm = int(self.args.margins / s)
            cbox = (bbox[0] - sm, bbox[1] - sm, bbox[2] + sm, bbox[3] + sm)
        else:
            s_full = float(self.a5width) / w
            if s_full * h > self.a5height:
                s_full = float(self.a5height) / h

            self.s_page = 1
            if s_full * w > self.a5width - self.args.imargins - self.args.margins:
                self.s_page = float(self.a5width - self.args.imargins - self.args.margins) / (s_full * w)
            if self.s_page * s_full * h > self.a5height - 2 * self.args.margins:
                self.s_page = float(self.a5height - 2 * self.args.margins) / (s_full * h)
                self.args.imargins = int(self.a5width - self.args.margins - self.s_page * s_full * w)
            cbox = bbox

        # crop crop
        pi = pyPdf.PdfFileReader(file(self.pdf_in, "rb"))
        self.pages = pi.getNumPages()
        po = pyPdf.PdfFileWriter()

        for i in range(self.pages):
            p = pi.getPage(i)

            p.cropBox.lowerLeft = (cbox[0] + p.mediaBox.lowerLeft[0], cbox[1] + p.mediaBox.lowerLeft[1])
            p.cropBox.upperRight = (cbox[2] + p.mediaBox.lowerLeft[0], cbox[3] + p.mediaBox.lowerLeft[1])

            p.bleedBox = p.cropBox
            p.trimBox = p.cropBox
            p.artBox = p.cropBox

            po.addPage(p)

        # extra blank pages
        bi = pyPdf.PdfFileReader(create_pdf_empty(cbox[2]-cbox[0],cbox[3]-cbox[1]))
        for i in range(self.args.epages):
            po.addPage(bi.getPage(0))

        outputStream = file('cropped.pdf', 'wb')
        po.write(outputStream)
        outputStream.close()

        self.pdf_in = 'cropped.pdf'

    def build_booklet(self):
        if not self.args.a5:
            if not self.args.croponly:
                docopt = 'a4paper,landscape'
                if self.args.signature:
                    includepdf = [('pages={%s},nup=2x1,delta=%dpt 0' % (make_sig_sequence(self.pages, self.args.signature), self.args.imargins), self.pdf_in)]
                else:
                    includepdf = [('pages=-,booklet=true,delta=%dpt 0' % self.args.imargins, self.pdf_in)]
            else:
                docopt = 'a4paper'
                includepdf = [('pages=-', 'cropped.pdf')]
        else:
            docopt = 'a5paper'
            includepdf = []
            for p in range(pages + self.args.epages):
                includepdf.append(('pages=%d,offset=%d 0,scale=%f' % ((p+1), (self.args.imargins/2 -self.args.margins/2 if (p%2==0) else self.args.margins/2 - self.args.imargins/2), self.s_page), self.pdf_in))

        tex = file("sig.tex", "w")
        tex.write('\\documentclass[%s]{article}\n' % docopt)
        tex.write('\\usepackage{pdfpages}\n')
        tex.write('\\begin{document}\n')
        for opt, src in includepdf:
            tex.write('\\includepdf[%s]{%s}\n' % (opt, src))
        tex.write('\\end{document}\n')
        tex.close()

        os.system(texcomp + ' sig.tex')

    def add_guides(self):
        pi = pyPdf.PdfFileReader(file("sig.pdf", "rb"))
        po = pyPdf.PdfFileWriter()

        for i in range(pi.getNumPages()):
            p = pi.getPage(i)
            if i == 0:
                if self.args.longarm:
                    grid = pyPdf.PdfFileReader(generate_guides_longarm())
                else:
                    grid = pyPdf.PdfFileReader(generate_guides(5, self.args.a5, bool(self.args.signature)))
                p.mergePage(grid.getPage(0))
            po.addPage(p)

        outputStream = file('sigs.pdf', 'wb')
        po.write(outputStream)
        outputStream.close()

    def run(self, args):
        self.parse_args(args)
        self.setup_tmpdir()

        if not self.args.nocrop:
            self.crop()

        self.build_booklet()

        if not self.args.noguides and not self.args.croponly:
            self.add_guides()
            os.system(viewer + ' sigs.pdf')
        else:
            os.system(viewer + ' sig.pdf')

        self.cleanup_tmpdir()

def run():
    mkbooklet = Mkbooklet()
    mkbooklet.run(sys.argv)
