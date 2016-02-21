from contextlib import contextmanager
from textwrap import dedent


class PDF(object):
    def __init__(self, fileobj):
        self.fileobj = fileobj
        self.positions = []

        self.fileobj.write('%PDF-1.1\n')
        self.fileobj.write('%\xff\xff\xff\xff\n')

    @classmethod
    @contextmanager
    def create(cls, fileobj):
        f = cls(fileobj)
        yield f
        f.finish()

    def add_raw_object(self, data):
        self.positions.append(self.fileobj.tell())
        self.fileobj.write(data)

    def finish(self):
        start = self.fileobj.tell()
        self.fileobj.write('xref\n')
        self.fileobj.write('0 {}\n'.format(len(self.positions) + 1))
        self.fileobj.write('0000000000 65535 f \n')

        for position in self.positions:
            self.fileobj.write('{:010} 00000 n \n'.format(position))

        self.fileobj.write(dedent("""\
            trailer
            <<
                /Root 1 0 R
                /Size {}
            >>
            startxref
            {}
            %%EOF
        """).format(len(self.positions) + 1, start))


def create_pdf(fileobj, width, height, content=None):
    with PDF.create(fileobj) as pdf:
        pdf.add_raw_object(dedent("""\
            1 0 obj
            <<
                /Type /Catalog
                /Pages 2 0 R
            >>
            endobj
        """))

        pdf.add_raw_object(dedent("""\
            2 0 obj
            <<
                /Type /Pages
                /Kids [3 0 R]
                /Count 1
                /MediaBox [0 0 {} {}]
            >>
            endobj
        """).format(width, height))

        pdf.add_raw_object(dedent("""\
            3 0 obj
            <<
                /Type /Page
                /Parent 2 0 R
                /Resources << >>
                /Contents {}
            >>
            endobj
        """).format('4 0 R' if content else '[]'))

        if not content:
            return

        pdf.add_raw_object(dedent("""\
            4 0 obj
            <<
                /Length {}
            >>
            stream
            {}
            endstream
            endobj
        """).format(len(content), content))
