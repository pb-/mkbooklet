from itertools import chain, count, repeat


def signature_sequence(pages):
    sheets = -(-pages // 4)
    empty_pages = (4 - pages % 4) % 4

    forward = chain(iter(xrange(pages)), repeat(None))
    backward = chain(repeat(None, empty_pages), count(pages - 1, -1))

    for _ in xrange(sheets):
        yield next(backward)
        yield next(forward)
        yield next(forward)
        yield next(backward)


def signatures_sequence(total_pages, sheets_per_signature):
    pages_per_signature = sheets_per_signature * 4

    for start in xrange(0, total_pages, pages_per_signature):
        pages = min(total_pages - start, pages_per_signature)
        for page in signature_sequence(pages):
            yield None if page is None else start + page


def format_signatures_sequence(total_pages, sheets_per_signature):
    return ','.join(
        map(lambda x: '{}' if x is None else str(x + 1),
            signatures_sequence(total_pages, sheets_per_signature)))
