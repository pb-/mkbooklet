import os
import re
import sys
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from cStringIO import StringIO
from itertools import cycle
from shutil import rmtree
from tempfile import mkdtemp
from textwrap import dedent

from pyPdf import PdfFileReader, PdfFileWriter

from .boundingbox import bounding_boxes, extrema_bbox, median_bbox
from .geometry import (a4lheight_pt, a4lwidth_pt, a5height_pt, a5width_pt,
                       mm_to_pt)
from .guides import generate_longarm, generate_shortarm
from .pdf import create_pdf
from .signature import format_signatures_sequence


class Mkbooklet(object):
    def parse_args(self):
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
        a('-o', '--outer-margins', dest='margins', default=6, type=int,
          help='use given value (unit: millimeters) for the minimal '
               'outer margins, see below')
        a('-p', '--bboxpage', dest='bboxpage', type=int,
          help='use given page number to obtain the bounding box')
        a('-s', '--smartbbox', action='store_true',
          help='use the median algorithm when obtaining the bbox')
        a('filename')

        self.args = parser.parse_args()
        self.pdf_in = os.path.abspath(self.args.filename)

        if self.args.imargins == 'default':
            if self.args.a5:
                self.args.imargins = 16
            else:
                self.args.imargins = 22
        else:
            self.args.imargins = int(self.args.imargins)

        if not self.args.a5:
            self.args.imargins = 2 * (self.args.imargins - self.args.margins)

        self.args.margins = int(round(mm_to_pt(self.args.margins)))
        self.args.imargins = int(round(mm_to_pt(self.args.imargins)))

    def setup_tmpdir(self):
        self.tmpdir = mkdtemp(prefix='mkbooklet-')
        os.chdir(self.tmpdir)

    def cleanup_tmpdir(self):
        rmtree(self.tmpdir)

    def get_bbox(self):
        if self.args.bbox:
            # x1,y1,x2,y2  or  x,y+w,h
            m = re.match('^(\\d+),(\\d+)(,|\\+)(\\d+),(\\d+)$', self.args.bbox)
            if not m:
                print(
                    'Invalid bbox format, use x1,y1,x2,y2 or x,y+w,h (all pt)')
                self.cleanup_tmpdir()
                sys.exit(-1)
            else:
                bbox = tuple((int(m.group(i)) for i in (1, 2, 4, 5)))
                if m.group(3) == '+':
                    bbox = (
                        bbox[0], bbox[1], bbox[0] + bbox[2], bbox[1] + bbox[3])

                return bbox
        else:
            # determine actual (printed) bounding box
            if self.args.bboxpage:
                return bounding_boxes(self.pdf_in)[self.args.bboxpage - 1]
            elif self.args.smartbbox:
                return median_bbox(self.pdf_in)
            else:
                return extrema_bbox(self.pdf_in)

    def crop(self):
        bbox = self.get_bbox()
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        if not self.args.a5:
            maxw = (
                a4lwidth_pt - self.args.imargins - 4 * self.args.margins) / 2
            maxh = a4lheight_pt - 2 * self.args.margins
            s = float(maxw) / w
            if s * h > maxh:
                # exceeds height, scaling will free up more horizontal space.
                # make sure we use this space where it makes sense (i.e.,
                # on the folding edge)
                s = float(maxh) / h
                self.args.imargins = int(
                    a4lwidth_pt - s * w * 2 - 4 * self.args.margins)

            sm = int(self.args.margins / s)
            cbox = (bbox[0] - sm, bbox[1] - sm, bbox[2] + sm, bbox[3] + sm)
        else:
            s_full = float(a5width_pt) / w
            if s_full * h > a5height_pt:
                s_full = float(a5height_pt) / h

            self.s_page = 1
            if (s_full * w >
                    a5width_pt - self.args.imargins - self.args.margins):
                self.s_page = float(
                    a5width_pt - self.args.imargins - self.args.margins) \
                    / (s_full * w)
            if self.s_page * s_full * h > a5height_pt - 2 * self.args.margins:
                self.s_page = float(
                    a5height_pt - 2 * self.args.margins) / (s_full * h)
                self.args.imargins = int(
                    a5width_pt - self.args.margins - self.s_page * s_full * w)
            cbox = bbox

        # crop crop
        pi = PdfFileReader(open(self.pdf_in, "rb"))
        self.pages = pi.getNumPages()
        po = PdfFileWriter()

        for i in range(self.pages):
            p = pi.getPage(i)

            p.cropBox.lowerLeft = (
                cbox[0] + p.mediaBox.lowerLeft[0],
                cbox[1] + p.mediaBox.lowerLeft[1])
            p.cropBox.upperRight = (
                cbox[2] + p.mediaBox.lowerLeft[0],
                cbox[3] + p.mediaBox.lowerLeft[1])

            p.bleedBox = p.cropBox
            p.trimBox = p.cropBox
            p.artBox = p.cropBox

            po.addPage(p)

        # extra blank pages
        if self.args.epages:
            empty = StringIO()
            create_pdf(empty, cbox[2] - cbox[0], cbox[3] - cbox[1])
            bi = PdfFileReader(empty)
            for i in range(self.args.epages):
                po.addPage(bi.getPage(0))

        with open('cropped.pdf', 'wb') as cropped:
            po.write(cropped)

        self.pdf_in = 'cropped.pdf'

    def build_booklet(self):
        if self.args.a5:
            docopt = 'a5paper'
            includepdf = []
            for p, mul in zip(xrange(self.pages + self.args.epages),
                              cycle((1, -1))):
                page_num = p + 1
                offset = mul * (self.args.imargins - self.args.margins) / 2
                includepdf.append(
                    ('pages=%d,offset=%d 0,scale=%f' % (
                        page_num, offset, self.s_page), self.pdf_in))
        else:
            if self.args.croponly:
                docopt = 'a4paper'
                includepdf = [('pages=-', 'cropped.pdf')]
            else:
                docopt = 'a4paper,landscape'
                if self.args.signature:
                    seq = format_signatures_sequence(
                        self.pages, self.args.signature)
                    includepdf = [('pages={%s},nup=2x1,delta=%dpt 0' % (
                        seq, self.args.imargins), self.pdf_in)]
                else:
                    includepdf = [
                        ('pages=-,booklet=true,delta=%dpt 0' %
                            self.args.imargins, self.pdf_in)]

        with open('sig.tex', 'w') as tex:
            tex.write('\\documentclass[%s]{article}\n' % docopt)
            tex.write('\\usepackage{pdfpages}\n')
            tex.write('\\begin{document}\n')
            for opt, src in includepdf:
                tex.write('\\includepdf[%s]{%s}\n' % (opt, src))
            tex.write('\\end{document}\n')

        texcomp = os.getenv('MKB_TEXCOMP') or 'pdflatex'
        os.system('{} sig.tex'.format(texcomp))

    def add_guides(self):
        pdf_in = PdfFileReader(open('sig.pdf', 'rb'))
        pdf_out = PdfFileWriter()

        for i in xrange(pdf_in.getNumPages()):
            page = pdf_in.getPage(i)
            if not i:
                guides = StringIO()

                if self.args.longarm:
                    create_pdf(
                        guides, a4lwidth_pt, a4lheight_pt, generate_longarm())
                else:
                    if self.args.a5:
                        w, h = a5width_pt, a5height_pt
                    else:
                        w, h = a4lwidth_pt, a4lheight_pt
                    create_pdf(guides, w, h, generate_shortarm(
                        self.args.a5, bool(self.args.signature)))

                pdf_guides = PdfFileReader(guides)
                page.mergePage(pdf_guides.getPage(0))
            pdf_out.addPage(page)

        pdf_out.write(open('sigs.pdf', 'wb'))

    @staticmethod
    def open_booklet(filename):
        os.system('xdg-open {}'.format(filename))

    def run(self):
        self.parse_args()
        self.setup_tmpdir()

        if not self.args.nocrop:
            self.crop()

        self.build_booklet()

        if not self.args.noguides and not self.args.croponly:
            self.add_guides()
            self.open_booklet('sigs.pdf')
        else:
            self.open_booklet('sig.pdf')

        self.cleanup_tmpdir()


def run():
    mkbooklet = Mkbooklet()
    mkbooklet.run()
