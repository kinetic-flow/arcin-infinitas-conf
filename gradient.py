#!/usr/bin/env python3

import tinycss2
from collections import namedtuple

# extract palettes: https://colorpalettefromimage.com/
# generating gradient: https://cssgradient.io/

happysky = """
    rgba(255,255,255,1) 0%, rgba(230,239,245,1) 10%, rgba(74,190,255,1) 23%, rgba(32,105,173,1) 40%, rgba(74,190,255,1) 70%, rgba(255,255,255,1) 90%, rgba(255,255,255,1) 100%
    """

lincle = """
    rgba(52,177,224,1) 0%, rgba(96,199,234,1) 3%, rgba(185,229,239,1) 8%, rgba(211,238,240,1) 15%, rgba(210,53,0,1) 28%, rgba(210,53,0,1) 43%, rgba(210,53,0,1) 61%, rgba(211,238,240,1) 70%, rgba(207,237,240,1) 77%, rgba(196,232,239,1) 83%, rgba(141,211,233,1) 93%, rgba(52,177,224,1) 100%
    """

Color = namedtuple('Color', 'r g b a o')

def split_into_elements(full_text):
    s = full_text.replace('\n', '')
    s = s.replace(' ', '')
    return s.split('%,')

def strip_chars(color):
    # rgba(230,239,245,1)15
    s = color.replace('%', '')
    s = s.replace('rgba(', '')
    s = s.replace(')', ',')
    sz = s.split(',')

    c = Color(int(sz[0]), int(sz[1]), int(sz[2]), int(sz[3]), int(int(sz[4]) / 100 * 255))
    return c

def convert_to_c_array(color):
    return f'{color.o}, 0x{color.r:x}, 0x{color.g:x}, 0x{color.b:x},\n'

def convert_css_into_c_array(css):
    elements = split_into_elements(css)
    colors = [strip_chars(c) for c in elements]
    if colors[0].o != 0:
        assert False, "Must begin with 0"
    if colors[-1].o != 255:
        assert False, "Must end with 255"
    if ((colors[0].r != colors[-1].r) or
       (colors[0].g != colors[-1].g) or
       (colors[0].b != colors[-1].b)):
        assert False, "Must start and end the same"
    
    result_str = '{\n'
    for c in colors:
        result_str += "    " + convert_to_c_array(c)

    # remove the last comma
    result_str = (result_str[:-2])
    result_str += '\n};\n'
    return result_str

print(convert_css_into_c_array(happysky))
print(convert_css_into_c_array(lincle))

pass
