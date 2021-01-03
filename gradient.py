#!/usr/bin/env python3

import tinycss2
from collections import namedtuple

# extract palettes: https://colorpalettefromimage.com/
# extract gradient: https://slaton.info/projects/fastled-gradient-tool/index.html
# generating gradient: https://cssgradient.io/

hv = """
    rgba(128,0,128,1) 0%, rgba(79,43,154,1) 17%, rgba(218,7,218,1) 73%, rgba(128,0,128,1) 100%
    """
emp = """
    rgba(255,0,255,1) 0%, rgba(202,2,43,1) 49%, rgba(89,31,40,1) 100%
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
    return f'{color.o}, 0x{color.r:02x}, 0x{color.g:02x}, 0x{color.b:02x},\n'

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
        #assert False, "Must start and end the same"
        pass
    
    result_str = '{\n'
    for c in colors:
        result_str += "    " + convert_to_c_array(c)

    # remove the last comma
    result_str = (result_str[:-2])
    result_str += '\n};\n'
    return result_str

print(convert_css_into_c_array(hv))
print(convert_css_into_c_array(emp))

pass
