#!/usr/bin/env python2

from __future__ import print_function
from binascii import hexlify, unhexlify
from sys import argv
from struct import unpack

indent = 0
def p(*args):
    print(' ' * indent, *args)

def decode(d):
    assert(len(d) % 4 == 0)
    # list of 4-char strings
    s = [d[4*i:4*i+4] for i in range(len(d) / 4)]
    # list of unsigned 32 bit integers
    u = [unpack('<I', s[i])[0] for i in range(len(s))]
    return s, u

def dump(d):
    s, u = decode(d)
    if len(s) == 0:
        p('<empty>')
    else:
        for i in range(len(s)):
            p(hexlify(s[i]), '%10u' % u[i], repr(s[i]))

def analyze_MPB1(d):
    s, u = decode(d)
    dump(d[:2*4])
    assert(u[0] == 2) # ???
    assert(u[1] == 0) # ???
    analyze_blocks(d[2*4:], ['COMP', 'VERT', 'FRAG', 'GEOM', 'CTRL', 'EVAL', 'BATT'])

# compute shader
def analyze_COMP(d):
    d = analyze_block(d, ['MBS2'])
    assert(d == '')

# vertex shader
def analyze_VERT(d):
    d = analyze_block(d, ['MBS2'])
    assert(d == '')

# fragment shader
def analyze_FRAG(d):
    d = analyze_block(d, ['MBS2'])
    assert(d == '')

mbs2_version = 0

def analyze_MBS2(d):
    global mbs2_version
    s, u = decode(d)
    mbs2_version = u[0]
    dump(d[:1*4])
    d = analyze_block(d[1*4:], ['VEHW'])
    d = analyze_block(d, ['CCOM', 'CVER', 'CFRA'])
    assert(d == '')

# hardware version?
def analyze_VEHW(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 3)
    assert(u[0] == 11) # ???
    assert(u[1] == 0) # ???
    assert(u[2] == 0) # ???

# something compute
def analyze_CCOM(d):
    d = analyze_block(d, ['CMMN'])
    d = analyze_block(d, ['KERN'])
    assert(d == '')

# something vertex
def analyze_CVER(d):
    d = analyze_block(d, ['CMMN'])
    assert(d == '')

# something fragment
def analyze_CFRA(d):
    d = analyze_block(d, ['CMMN'])
    assert(d == '')

def analyze_CMMN(d):
    d = analyze_block(d, ['VELA'])
    # inputs, outputs, uniforms, ???, ???, ???
    for i in range(6):
        d = analyze_block(d, ['SSYM'])
    d = analyze_block(d, ['UBUF'])
    s, u = decode(d)
    count = analyze_blocks(d[1*4:], ['EBIN'])
    assert(count == u[0])

def analyze_VELA(d):
    s, u = decode(d)
    assert(len(u) == 1)
    versions = {1: 100, 2: 300, 4: 310, 8: 320}
    p('#version %u es' % versions[u[0]])

def analyze_SSYM(d):
    s, u = decode(d)
    count = analyze_blocks(d[1*4:], ['SYMB'])
    assert(count == u[0])

# symbol
def analyze_SYMB(d):
    d = analyze_block(d, ['STRI'])
    s, u = decode(d)
    dump(d[:4*4])
    binding = u[3] & 0xffff
    location = u[3] >> 16
    if binding != 0xffff:
        p('layout(binding = %u)' % binding)
    if location != 0xffff:
        p('layout(location = %u)' % location)
    d = analyze_block(d[4*4:], ['TYPE'])
    s, u = decode(d)
    rloc_count = u[0]
    d = d[1*4:]
    for i in range(rloc_count):
        d = analyze_block(d, ['RLOC'])
    s, u = decode(d)
    assert(len(u) == 1)
    assert(u[0] == 0) # ???

# string
def analyze_STRI(d):
    p(d.strip('\x00'))

def analyze_TYPE(d):
    d = analyze_block(d, ['TPGE', 'TPMA', 'TPAR', 'TPST', 'TPIB'])
    assert(d == '')

# basic type
def analyze_TPGE(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 3)
    scalar_type = u[0] & 0xff
    scalar_size = (u[0] >> 8) & 0xff
    precision = 0 # TODO
    aux_qualifier = 0 # TODO
    types = [None,
             ['float', 'vec'],
             ['int', 'ivec'],
             ['uint', 'uvec'],
             ['bool', 'bvec']]
    type_str = types[scalar_type][scalar_size != 1]
    if scalar_size != 1:
        assert(scalar_size >= 2 and scalar_size <= 4)
        type_str += str(scalar_size)
    p(type_str)

# type: array
def analyze_TPAR(d):
    s, u = decode(d)
    p('element count:', u[0])
    d = analyze_block(d[1*4:], ['TYPE'])
    assert(d == '')

# type: matrix
def analyze_TPMA(d):
    s, u = decode(d)
    dim = u[0] & 0xffff
    layout = u[0] >> 16
    p('layout(%s)' % ['column_major', 'row_major'][layout])
    p('mat%dx?' % dim)
    p(hex(u[1]))
    d = analyze_block(d[2*4:], ['TPGE'])
    assert(d == '')

# type: buffer
def analyze_TPIB(d):
    s, u = decode(d)
    layout = u[0] & 0xff
    unknown = u[0] >> 8
    p('layout(%s)' % ['unknown (0)', 'unknown (1)', 'unknown (2)', 'unknown (3)',
                  'shared', 'packed', 'std140', 'std430'][layout])
    p(hex(unknown))
    p('total size:', u[1])
    p('element count:', u[2])
    count = analyze_blocks(d[3*4:], ['TPSE'])
    assert(count == u[2])

# type: struct
def analyze_TPST(d):
    s, u = decode(d)
    p('total size:', u[0])
    p('element count:', u[1])
    d = analyze_block(d[2*4:], ['STRI'])
    count = analyze_blocks(d, ['TPSE'])
    assert(count == u[1])

# type: struct element
def analyze_TPSE(d):
    d = analyze_block(d, ['STRI'])
    s, u = decode(d)
    p('offset in struct:', u[0])
    p(hex(u[1]), hex(u[2])) # ???
    d = analyze_block(d[3*4:], ['TYPE'])
    assert(d == '')

def analyze_EBIN(d):
    s, u = decode(d)
    dump(d[:4*4])
    assert(u[0] == 0) # ???
    assert(u[1] == 0xffffffff) # ???
    rloc_count = u[2]
    assert(u[3] == 0) # ???
    d = d[4*4:]
    for i in range(rloc_count):
        d = analyze_block(d, ['RLOC'])
    s, u = decode(d)
    assert(u[0] == 0xffffffff) # ???
    d = analyze_block(d[1*4:], ['FSHA'])
    if mbs2_version == 13:
        d = analyze_block(d, ['STRI'])
    d = analyze_block(d, ['BFRE'])
    d = analyze_block(d, ['OBJC'])
    assert(d == '')

def analyze_OBJC(d):
    s, u = decode(d)
    for i in range(len(s) // 4 + 1):
        line = ''
        for j in range(len(s[4*i:4*i + 4])):
            idx = 4 * i + j
            line += hexlify(s[idx]) + ' '
        p(line)

def analyze_FSHA(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 6)
    assert(u[0] == 0) # ???
    assert(u[1] == 0) # ???

def analyze_BFRE(d):
    if mbs2_version == 18:
        dump(d[:1*4])
        d = d[1*4:]
    d = analyze_block(d, ['SPDc', 'SPDv', 'SPDf'])
    assert(d == '')

# something compute
def analyze_SPDc(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 1)

# something vertex
def analyze_SPDv(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 1)

# something fragment
def analyze_SPDf(d):
    s, u = decode(d)
    dump(d)
    assert(len(u) == 2)

def analyze_KERN(d):
    d = analyze_block(d, ['STRI'])
    s, u = decode(d)
    dump(d[:3*4])
    assert(u[0] == 0) # ???
    assert(u[1] == 0) # ???
    assert(u[2] == 0) # ???
    d = analyze_block(d[3*4:], ['KWGS'])
    assert(d == '')

# kernel work group size
def analyze_KWGS(d):
    s, u = decode(d)
    assert(len(u) == 3)
    p('layout(local_size_x = %d,' % u[0])
    p('       local_size_y = %d,' % u[1])
    p('       local_size_z = %d) in;' % u[2])

def analyze_BATT(d):
    s, u = decode(d)
    str_count = u[0]
    d = d[1*4:]
    for i in range(str_count):
        d = analyze_block(d, ['STRI'])
        s, u = decode(d)
        dump(d[:1*4])
        d = d[1*4:]

def analyze_block(d, expected):
    global indent
    assert(len(d) >= 8)
    s, u = decode(d)
    sig = s[0]
    length = u[1]
    p(sig, '(%u bytes payload)' % length)
    assert(sig in expected)
    indent += 4
    assert(length % 4 == 0)
    assert(length + 2*4 <= len(d))
    payload = d[2*4:2*4+length]
    if ('analyze_' + sig) in globals():
        eval('analyze_' + sig)(payload)
    else:
        dump(payload)
    indent -= 4
    return d[2*4 + length:]

def analyze_blocks(d, expected):
    count = 0
    while len(d) > 0:
        count += 1
        s, u = decode(d)
        d = analyze_block(d, expected)
    return count


if __name__ == '__main__':
    path = argv[1]
    with open(path, 'rb') as f:
        d = f.read()
    if path.endswith('.hex'):
        d = ''.join(d.split('\n'))
        d = unhexlify(d)
        d = analyze_block(d, ['MPB1'])
    else:
        d = analyze_block(d, ['MBS2'])
    assert(d == '')
