from struct import unpack
from subprocess import PIPE, Popen

from pyPdf import PdfFileReader


def page_sizes(filename):
    f = PdfFileReader(open(filename, 'rb'))

    for i in range(f.getNumPages()):
        p = f.getPage(i)
        width = p.mediaBox.getUpperRight_x() - p.mediaBox.getLowerLeft_x()
        height = p.mediaBox.getUpperRight_y() - p.mediaBox.getLowerLeft_y()

        yield map(int, map(round, (width, height)))


def bounding_boxes(filename):
    proc = Popen(
        ['gs', '-q', '-dBATCH', '-dNOPAUSE', '-sDEVICE=bit',
         '-sOutputFile=%stdout', filename], stdout=PIPE, shell=True)

    for width, height in page_sizes(filename):
        bbox = (width - 1, height - 1, 0, 0)

        row_len = -(-width // 8)
        fmt = 'b' * row_len

        for y in range(height - 1, -1, -1):
            columns = unpack(fmt, proc.stdout.read(row_len))
            # use low resolution for x-positions. this is
            # substantially faster and comes with an error
            # of at most 8pt \approx 2.8mm
            for x in range(0, row_len):
                if columns[x] != 0:
                    bbox = (
                        min(bbox[0], x * 8),
                        min(bbox[1], y),
                        max(bbox[2], x * 8 + 8),
                        max(bbox[3], y + 2),
                    )

        if bbox[0] < bbox[2] and bbox[1] < bbox[3]:
            yield bbox


def median_bbox(filename):
    return tuple(map(
        lambda l: sorted(l)[len(l) // 2], zip(*bounding_boxes(filename))))


def extrema_bbox(filename):
    return reduce(lambda a, b: (
        min(a[0], b[0]),
        min(a[1], b[1]),
        max(a[2], b[2]),
        max(a[3], b[3])
    ), bounding_boxes(filename))
