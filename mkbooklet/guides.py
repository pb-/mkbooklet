from textwrap import dedent


def generate_longarm():
    width = 1
    content = '2.83464567 0 0 2.83464567 0 0 cm 0.1 w 1 0 0 1 148.5 21 cm\n'

    for i in range(5):
        if i != 0:
            content += '1 0 0 1 0 42 cm\n'

        content += dedent("""\
            -{} 0 m
            {} 0 l
            s
        """).format(width, 2 * width)

    return content


def generate_shortarm(a5mode, right):
    num = 5
    vmargin_mm = 6
    hmargin_mm = 5 if a5mode else 2.5

    if a5mode:
        x = hmargin_mm
    if right:
        x = 148.5 + hmargin_mm
    else:
        x = 148.5 - hmargin_mm

    content = '2.83464567 0 0 2.83464567 0 0 cm 0.1 w 1 0 0 1 {} {} cm\n'\
        .format(x, vmargin_mm)

    height_mm = 12
    sp = float(210 - height_mm - 2 * vmargin_mm) / (num - 1)

    sign = '' if (a5mode or right) else '-'

    for i in range(num):
        if i != 0:
            content += "1 0 0 1 0 %f cm\n" % sp

        content += dedent("""\
            0 0 m
            0 {height} l
            s

            0 2 m
            {sign}2 2 l
            s

            0 10 m
            {sign}2 10 l
            s
        """).format(height=height_mm, sign=sign)

    return content
